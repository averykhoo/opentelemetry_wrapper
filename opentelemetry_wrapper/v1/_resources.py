"""
resource detectors (OTW-9, workstream 6): everything that describes *the process*, computed once at startup

- `KubernetesResourceDetector`: namespace, pod and workload from inside the pod, never from the Kubernetes API (DEC-12)
- `WrapperProcessResourceDetector`: the SDK's process detector, corrected (`sys.orig_argv`, scrubbed), plus the Python
  environment and our readable `opentelemetry_wrapper.instance.label` outside Kubernetes (DEC-29, DEC-30, DEC-4)
- `detect_resource`: runs both, each guarded (a detector never crashes `configure`); the caller merges the result per
  DEC-33 (detectors < OTEL_SERVICE_NAME / OTEL_RESOURCE_ATTRIBUTES < explicit arguments)
- `ForkAwareResource`: keeps `process.pid` / `process.parent_pid` true in a forked worker (public API only)

both detectors are `ResourceDetector`s with no-argument constructors, so they also work in plain OpenTelemetry
(`OTEL_EXPERIMENTAL_RESOURCE_DETECTORS`) once registered under the `opentelemetry_resource_detector` entry-point group;
they take an injectable filesystem `root` and `environ` so tests can fake `/var/run/secrets/...` and `/etc/hostname`
"""
import ast
import base64
import getpass
import json
import os
import re
import socket
import sys
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Mapping
from typing import NamedTuple
from typing import Optional
from typing import Tuple
from urllib.parse import unquote

from opentelemetry.sdk.resources import ProcessResourceDetector
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.resources import ResourceDetector

__all__ = ['KubernetesResourceDetector', 'WrapperProcessResourceDetector', 'ForkAwareResource', 'PodShape',
           'pod_name_shape', 'parse_downward_file', 'python_environment', 'detect_resource']

LABEL = 'opentelemetry_wrapper.instance.label'
ENV_PREFIX = 'opentelemetry_wrapper.python.environment'
PODINFO_DIR_ENV = 'OTEL_WRAPPER_PODINFO_DIR'
CAPTURE_ARGS_ENV = 'OTEL_WRAPPER_CAPTURE_COMMAND_ARGS'
ANNOTATION_PREFIX = 'resource.opentelemetry.io/'
SERVICE_ACCOUNT_DIR = 'var/run/secrets/kubernetes.io/serviceaccount'

# ----------------------------------------------------------------------------------------------------------------------
# pod names
# ----------------------------------------------------------------------------------------------------------------------

_SAFE = '[bcdfghjklmnpqrstvwxz2456789]'  # the alphabet Kubernetes' generated name parts use
_CRONJOB = re.compile(rf'^(?P<name>.+)-(?P<job>\d{{8,}})-{_SAFE}{{5}}$')
_DEPLOYMENT = re.compile(rf'^(?P<name>.+)-(?P<rs>{_SAFE}{{5,10}})-{_SAFE}{{5}}$')
_STATEFULSET = re.compile(r'^(?P<name>.+)-\d+$')
_AMBIGUOUS = re.compile(rf'^(?P<name>.+)-{_SAFE}{{5}}$')


class PodShape(NamedTuple):
    """what a pod name says: `kind` is set only for an unambiguous shape; `candidate` is the workload name to offer as
    a `service.name` candidate (for the ambiguous DaemonSet-or-Job shape too); `attributes` are the `k8s.*` ones"""
    kind: Optional[str]
    candidate: Optional[str]
    attributes: Tuple[Tuple[str, str], ...]


def pod_name_shape(pod_name: str) -> PodShape:
    """pure: the workload a pod name belongs to, by its generated-name shape; never strips to an empty name"""
    pod_name = pod_name.strip()
    if m := _CRONJOB.match(pod_name):
        name = m['name']
        return PodShape('cronjob', name, (('k8s.cronjob.name', name), ('k8s.job.name', f'{name}-{m["job"]}')))
    if m := _DEPLOYMENT.match(pod_name):
        name = m['name']
        return PodShape('deployment', name, (('k8s.deployment.name', name),
                                             ('k8s.replicaset.name', f'{name}-{m["rs"]}')))
    if m := _STATEFULSET.match(pod_name):
        return PodShape('statefulset', m['name'], (('k8s.statefulset.name', m['name']),))
    if m := _AMBIGUOUS.match(pod_name):
        return PodShape(None, m['name'], ())  # DaemonSet or Job: a service.name candidate only
    return PodShape(None, None, ())  # anything else (a truncated Deployment name too): no service.name


# ----------------------------------------------------------------------------------------------------------------------
# small readers
# ----------------------------------------------------------------------------------------------------------------------

def _read(path: Path) -> Optional[str]:
    """the text of a file, `None` for one that is missing or unreadable (normal outside a pod: silent)"""
    try:
        return path.read_text(encoding='utf-8').strip()
    except (OSError, ValueError):
        return None


def parse_downward_file(text: str) -> Dict[str, str]:
    """a Downward API `labels` / `annotations` file: one `key="value"` per line, the value in Go's `strconv.Quote`
    form (a Python string literal for valid UTF-8), the raw text where it is not"""
    out: Dict[str, str] = {}
    for line in text.splitlines():
        key, sep, raw = line.partition('=')
        key = key.strip()
        if not sep or not key:
            continue
        raw = raw.strip()
        try:
            value = ast.literal_eval(raw)
            if not isinstance(value, str):
                value = raw
        except (ValueError, SyntaxError, MemoryError, RecursionError):
            value = raw
        out[key] = value
    return out


def _env_attributes(environ: Mapping[str, str]) -> Dict[str, str]:
    """`OTEL_RESOURCE_ATTRIBUTES`, where a Downward API env var can hand us `k8s.pod.name` and the like"""
    out: Dict[str, str] = {}
    for item in (environ.get('OTEL_RESOURCE_ATTRIBUTES') or '').split(','):
        key, sep, value = item.partition('=')
        if sep and key.strip():
            out[key.strip()] = unquote(value.strip())
    return out


def _token_claims(token: str) -> Dict[str, Any]:
    payload = token.split('.')[1]
    claims = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))
    return claims.get('kubernetes.io') or {}


def _truthy(value: Optional[str], default: bool) -> bool:
    if value is None or not value.strip():
        return default
    return value.strip().casefold() not in ('false', '0', 'no', 'off')


def _in_kubernetes(environ: Mapping[str, str]) -> bool:
    return bool((environ.get('KUBERNETES_SERVICE_HOST') or '').strip())


# ----------------------------------------------------------------------------------------------------------------------
# kubernetes
# ----------------------------------------------------------------------------------------------------------------------

class KubernetesResourceDetector(ResourceDetector):
    """
    namespace, pod and workload from inside the pod, and `service.name` / `service.namespace` / `service.version` by
    semconv's derivation (first value found wins). Reads the service-account files, the hostname, a Downward API volume
    (`OTEL_WRAPPER_PODINFO_DIR`, default `/etc/podinfo`) and `OTEL_RESOURCE_ATTRIBUTES`; never calls the Kubernetes
    API.
    Outside Kubernetes (`KUBERNETES_SERVICE_HOST` unset) the resource is empty.
    """

    def __init__(self, raise_on_error: bool = False, root: Any = '/',
                 environ: Optional[Mapping[str, str]] = None) -> None:
        super().__init__(raise_on_error=raise_on_error)
        self._root = Path(root)
        self._environ = os.environ if environ is None else environ
        self.problems: List[str] = []

    def is_process_dependent(self) -> bool:
        return False

    def _attempt(self, what: str, step: Callable[[], Any], default: Any) -> Any:
        try:
            return step()
        except Exception as e:  # noqa: a bad file must cost one fact, not the rest of the resource
            self.problems.append(f'the Kubernetes resource detector could not read {what}: {type(e).__name__}: {e}')
            return default

    def _podinfo(self, name: str) -> Dict[str, str]:
        directory = (self._environ.get(PODINFO_DIR_ENV) or '').strip() or '/etc/podinfo'
        # a faked root keeps the same path under it
        base = Path(directory) if self._root == Path('/') else self._root / directory.lstrip('/\\')
        text = _read(base / name)
        return parse_downward_file(text) if text else {}

    def detect(self) -> Resource:
        if not _in_kubernetes(self._environ):
            return Resource.get_empty()
        sa = self._root / SERVICE_ACCOUNT_DIR
        env_attrs = _env_attributes(self._environ)
        claims: Dict[str, Any] = {}
        token = _read(sa / 'token')
        if token:
            claims = self._attempt('the service-account token', lambda: _token_claims(token), {})
        pod_claims = claims.get('pod') or {}

        namespace = (env_attrs.get('k8s.namespace.name') or _read(sa / 'namespace')
                     or claims.get('namespace') or '')
        pod_name = (env_attrs.get('k8s.pod.name') or pod_claims.get('name')
                    or (self._environ.get('HOSTNAME') or '').strip() or _read(self._root / 'etc/hostname') or '')
        pod_uid = env_attrs.get('k8s.pod.uid') or pod_claims.get('uid') or ''
        labels = self._attempt('the Downward API labels', lambda: self._podinfo('labels'), {})
        annotations = self._attempt('the Downward API annotations', lambda: self._podinfo('annotations'), {})
        shape = self._attempt('the pod name', lambda: pod_name_shape(pod_name), PodShape(None, None, ()))

        attrs: Dict[str, Any] = {}
        for key, value in (('k8s.namespace.name', namespace), ('k8s.pod.name', pod_name), ('k8s.pod.uid', pod_uid),
                           ('k8s.container.name', env_attrs.get('k8s.container.name', ''))):
            if value:
                attrs[key] = value
        attrs.update(shape.attributes)

        def annotated(name: str) -> str:
            return annotations.get(ANNOTATION_PREFIX + name) or ''

        service_name = (annotated('service.name') or labels.get('app.kubernetes.io/instance')
                        or labels.get('app.kubernetes.io/name') or shape.candidate or '')
        service_namespace = annotated('service.namespace') or namespace
        service_version = annotated('service.version') or labels.get('app.kubernetes.io/version') or ''
        for key, value in (('service.name', service_name), ('service.namespace', service_namespace),
                           ('service.version', service_version),
                           ('service.instance.id', annotated('service.instance.id'))):
            if value:
                attrs[key] = value
        attrs[LABEL] = f'{namespace}/{shape.candidate or ""}/{pod_name}'
        return Resource(attrs)


# ----------------------------------------------------------------------------------------------------------------------
# process
# ----------------------------------------------------------------------------------------------------------------------

def python_environment(prefix: Optional[str] = None, base_prefix: Optional[str] = None,
                       platform: Optional[str] = None, frozen: Optional[bool] = None,
                       isdir: Callable[[str], bool] = os.path.isdir) -> Dict[str, str]:
    """which Python environment this is (no semconv attribute says): pyodide | frozen | conda | venv | system"""
    prefix = sys.prefix if prefix is None else prefix
    base_prefix = getattr(sys, 'base_prefix', prefix) if base_prefix is None else base_prefix
    platform = sys.platform if platform is None else platform
    frozen = bool(getattr(sys, 'frozen', False)) if frozen is None else frozen
    if platform == 'emscripten':
        kind = 'pyodide'
    elif frozen:
        kind = 'frozen'
    elif isdir(os.path.join(prefix, 'conda-meta')):
        kind = 'conda'
    elif prefix != base_prefix:
        kind = 'venv'
    else:
        kind = 'system'
    out = {ENV_PREFIX: kind}
    name = os.path.basename(prefix.rstrip('/\\'))
    if name:
        out[ENV_PREFIX + '.name'] = name
    if prefix:
        out[ENV_PREFIX + '.path'] = prefix
    return out


def _owner() -> str:
    try:
        return getpass.getuser()
    except Exception:  # an arbitrary UID with no passwd entry (OpenShift): the number is still an identity
        getuid = getattr(os, 'getuid', None)
        return str(getuid()) if getuid else ''


def _host_name(environ: Mapping[str, str]) -> str:
    for name in ('HOSTNAME', 'COMPUTERNAME'):
        value = (environ.get(name) or '').strip()
        if value:
            return value
    return socket.gethostname().strip()


def _main_filename() -> str:
    main = sys.modules.get('__main__')
    path = getattr(main, '__file__', None)
    return Path(path).name if path else ''


class WrapperProcessResourceDetector(ResourceDetector):
    """
    the SDK's `ProcessResourceDetector(include_command_args=True)`, corrected rather than reimplemented:
    `process.command_args` is `sys.orig_argv` (the interpreter, its flags and `-m` included) through `scrub_argv`;
    `process.executable.name` is the base name of `sys.executable` (DEC-4); `process.command_line` is left unset.
    Adds `opentelemetry_wrapper.python.environment*`, `opentelemetry_wrapper.python.gil` on a free-threaded build and,
    outside Kubernetes, `opentelemetry_wrapper.instance.label` (`<user>@<host.domain>:<main.py>`).
    `OTEL_WRAPPER_CAPTURE_COMMAND_ARGS=false` drops the arguments entirely.
    """

    def __init__(self, raise_on_error: bool = False, environ: Optional[Mapping[str, str]] = None) -> None:
        super().__init__(raise_on_error=raise_on_error)
        self._environ = os.environ if environ is None else environ
        self.problems: List[str] = []

    def is_process_dependent(self) -> bool:
        return True

    def _attempt(self, what: str, step: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
        try:
            return step()
        except Exception as e:  # noqa: one failing fact must not cost the rest of the resource
            self.problems.append(f'the process resource detector could not detect {what}: {type(e).__name__}: {e}')
            return {}

    def _sdk(self) -> Dict[str, Any]:
        attrs = dict(ProcessResourceDetector(include_command_args=True).detect().attributes)
        for key in ('process.command_line', 'process.command_args', 'process.executable.name',
                    'process.executable.path', 'process.owner'):
            attrs.pop(key, None)  # ours below: the SDK's are unscrubbed or wrong
        return attrs

    def _command(self) -> Dict[str, Any]:
        argv = list(getattr(sys, 'orig_argv', None) or sys.argv)
        attrs: Dict[str, Any] = {'process.args_count': len(argv)}
        if argv:
            attrs['process.command'] = argv[0]
        if _truthy(self._environ.get(CAPTURE_ARGS_ENV), True):
            from opentelemetry_wrapper.v1.scrubbing import scrub_argv
            attrs['process.command_args'] = list(scrub_argv(argv))
        return attrs

    def _executable(self) -> Dict[str, Any]:
        exe = sys.executable or ''
        attrs: Dict[str, Any] = {'process.executable.name': os.path.basename(exe) or 'python'}
        if exe:
            attrs['process.executable.path'] = exe
        return attrs

    def _misc(self) -> Dict[str, Any]:
        attrs: Dict[str, Any] = {'host.name': _host_name(self._environ)}
        owner = _owner()
        if owner:
            attrs['process.owner'] = owner
        attrs['process.working_directory'] = os.getcwd()
        return attrs

    def _python(self) -> Dict[str, Any]:
        attrs: Dict[str, Any] = dict(python_environment())
        gil = getattr(sys, '_is_gil_enabled', None)  # 3.13+ only
        if callable(gil) and not gil():
            attrs['opentelemetry_wrapper.python.gil'] = False
        return attrs

    def _label(self, host: str, owner: str) -> Dict[str, Any]:
        domain = (self._environ.get('USERDNSDOMAIN') or self._environ.get('USERDOMAIN') or '').strip()
        if domain.casefold() == host.casefold():
            domain = ''
        user = f'{owner}@' if owner else ''
        main = _main_filename()
        return {LABEL: f'{user}{host or "<UNKNOWN_HOST>"}{"." + domain if domain else ""}{":" + main if main else ""}'}

    def detect(self) -> Resource:
        attrs: Dict[str, Any] = {}
        for what, step in (('the runtime', self._sdk), ('the command line', self._command),
                           ('the executable', self._executable), ('the host and owner', self._misc),
                           ('the Python environment', self._python)):
            attrs.update(self._attempt(what, step))
        if not _in_kubernetes(self._environ):
            attrs.update(self._attempt('the instance label', lambda: self._label(
                str(attrs.get('host.name', '')), str(attrs.get('process.owner', '')))))
        return Resource(attrs)


# ----------------------------------------------------------------------------------------------------------------------
# putting it together
# ----------------------------------------------------------------------------------------------------------------------

def detect_resource(environ: Optional[Mapping[str, str]] = None, root: Any = '/',
                    notes: Optional[List[str]] = None) -> Resource:
    """both detectors, each guarded; a failure adds one line to `notes` (for the warnings `configure` emits once) and
    leaves the other detectors' attributes intact. `service.name` falls back to `unknown_service:<executable name>`"""
    notes = [] if notes is None else notes
    environ = os.environ if environ is None else environ
    resource = Resource.get_empty()
    for detector in (WrapperProcessResourceDetector(environ=environ),
                     KubernetesResourceDetector(root=root, environ=environ)):
        try:
            resource = resource.merge(detector.detect())
        except Exception as e:  # noqa: detectors never crash configure (DEC-8)
            notes.append(f'{type(detector).__name__} failed and its attributes are missing: {type(e).__name__}: {e}')
        notes.extend(detector.problems)
    if not resource.attributes.get('service.name'):
        executable = resource.attributes.get('process.executable.name')
        resource = resource.merge(Resource({'service.name': f'unknown_service:{executable}' if executable
                                            else 'unknown_service'}))
    return resource


class ForkAwareResource(Resource):
    """
    a `Resource` whose `process.pid` and `process.parent_pid` follow the process: the SDK re-runs only the
    process-dependent detectors it builds from environment variables after a fork, not ours, so a worker forked after
    `configure` (gunicorn `--preload`) would report the master's pid. A subclass of the public `Resource` read at
    export time, so no provider attribute is written to (`merge` keeps the class: the SDK's fork hook merges into it)
    """

    def __init__(self, attributes: Any, schema_url: Optional[str] = None) -> None:
        super().__init__(attributes, schema_url)
        self._pid = os.getpid()
        self._ppid = os.getppid() if hasattr(os, 'getppid') else None

    @property
    def attributes(self) -> Any:
        pid = os.getpid()
        if pid != self._pid:
            current = dict(self._attributes)
            if current.get('process.pid') == self._pid:
                current['process.pid'] = pid
            if self._ppid is not None and current.get('process.parent_pid') == self._ppid:
                current['process.parent_pid'] = os.getppid()
            self._attributes = Resource(current)._attributes
            self._pid, self._ppid = pid, os.getppid() if hasattr(os, 'getppid') else None
        return self._attributes

    def merge(self, other: Resource) -> Resource:
        merged = super().merge(other)
        return ForkAwareResource(merged.attributes, merged.schema_url)
