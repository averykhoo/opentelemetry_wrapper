"""
v1's resource detectors (OTW-9, workstream 6; AC-14, AC-15, AC-16): the pod-name table, the Kubernetes detector over
a faked filesystem and environment, the process detector with scrubbed arguments, guards, precedence through
`configure`, and `process.pid` / `service.instance.id` in a forked worker (Linux only)
"""
import base64
import json
import os
import socket
import sys
import time
import warnings

import pytest

from opentelemetry_wrapper.v1 import _resources
from opentelemetry_wrapper.v1._resources import ForkAwareResource
from opentelemetry_wrapper.v1._resources import KubernetesResourceDetector
from opentelemetry_wrapper.v1._resources import WrapperProcessResourceDetector
from opentelemetry_wrapper.v1._resources import detect_resource
from opentelemetry_wrapper.v1._resources import parse_downward_file
from opentelemetry_wrapper.v1._resources import pod_name_shape
from opentelemetry_wrapper.v1._resources import python_environment
from tests.v0._harness import scenario
from tests.v1._prelude import PRELUDE

IN_K8S = {'KUBERNETES_SERVICE_HOST': '10.0.0.1'}
LABEL = 'opentelemetry_wrapper.instance.label'


def _attrs(resource):
    return dict(resource.attributes)


# ----------------------------------------------------------------------------------------------------------------------
# AC-14: the pod-name table (a pure function)
# ----------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize('pod, kind, candidate, attributes', [
    ('web-5d8f7c9b4d-x2x2z', 'deployment', 'web', {'k8s.deployment.name': 'web',
                                                   'k8s.replicaset.name': 'web-5d8f7c9b4d'}),
    ('my-api-server-7c9b4d-x2x2z', 'deployment', 'my-api-server', {'k8s.deployment.name': 'my-api-server',
                                                                   'k8s.replicaset.name': 'my-api-server-7c9b4d'}),
    ('report-29123456-x2x2z', 'cronjob', 'report', {'k8s.cronjob.name': 'report',
                                                    'k8s.job.name': 'report-29123456'}),
    ('db-0', 'statefulset', 'db', {'k8s.statefulset.name': 'db'}),
    ('my-db-12', 'statefulset', 'my-db', {'k8s.statefulset.name': 'my-db'}),
    ('agent-x2x2z', None, 'agent', {}),  # DaemonSet or Job: a candidate only, no k8s.*.name
    ('standalone', None, None, {}),  # anything else: no workload at all
    ('web-5d8f7c9b4d-x2x2', None, None, {}),  # a truncated generated name is not a Deployment pod
    ('web-aeiou-x2x2z', None, 'web-aeiou', {}),  # vowels are outside the generated alphabet: not a ReplicaSet hash
    ('', None, None, {}),
])
def test_pod_name_table(pod, kind, candidate, attributes):
    shape = pod_name_shape(pod)
    assert (shape.kind, shape.candidate, dict(shape.attributes)) == (kind, candidate, attributes)


@pytest.mark.parametrize('pod', ['a-b', '-x2x2z', 'x2x2z', 'a-0', '-5d8f7c9b4d-x2x2z', 'web-aeiou-x2x2z'])
def test_pod_names_are_never_stripped_to_empty(pod):
    shape = pod_name_shape(pod)
    assert shape.candidate != ''
    assert all(value for _, value in shape.attributes)


# ----------------------------------------------------------------------------------------------------------------------
# AC-14: the Kubernetes detector over a faked filesystem and environment
# ----------------------------------------------------------------------------------------------------------------------

def _jwt(claims):
    def b64(data):
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b'=').decode()

    return f'{b64({"alg": "none"})}.{b64(claims)}.sig'


def _sa(root, *, namespace=None, token=None):
    sa = root / 'var/run/secrets/kubernetes.io/serviceaccount'
    sa.mkdir(parents=True, exist_ok=True)
    if namespace is not None:
        (sa / 'namespace').write_text(namespace)
    if token is not None:
        (sa / 'token').write_text(token)


def _detect(root, environ=None):
    detector = KubernetesResourceDetector(root=root, environ={**IN_K8S, **(environ or {})})
    resource = detector.detect()
    return _attrs(resource), detector.problems


def test_outside_kubernetes_the_resource_is_empty(tmp_path):
    _sa(tmp_path, namespace='prod')
    detector = KubernetesResourceDetector(root=tmp_path, environ={'HOSTNAME': 'web-5d8f7c9b4d-x2x2z'})
    assert _attrs(detector.detect()) == {}


def test_namespace_and_pod_from_the_service_account_files_and_hostname(tmp_path):
    _sa(tmp_path, namespace='prod')
    attrs, problems = _detect(tmp_path, {'HOSTNAME': 'web-5d8f7c9b4d-x2x2z'})
    assert attrs['k8s.namespace.name'] == 'prod'
    assert attrs['k8s.pod.name'] == 'web-5d8f7c9b4d-x2x2z'
    assert attrs['k8s.deployment.name'] == 'web' and attrs['k8s.replicaset.name'] == 'web-5d8f7c9b4d'
    assert attrs['service.name'] == 'web' and attrs['service.namespace'] == 'prod'
    assert attrs[LABEL] == 'prod/web/web-5d8f7c9b4d-x2x2z'
    assert 'service.instance.id' not in attrs  # the SDK's per-process UUID stays (DEC-29)
    assert problems == []


def test_pod_name_falls_back_to_etc_hostname(tmp_path):
    (tmp_path / 'etc').mkdir()
    (tmp_path / 'etc/hostname').write_text('db-0\n')
    attrs, _ = _detect(tmp_path)
    assert attrs['k8s.pod.name'] == 'db-0' and attrs['service.name'] == 'db'
    assert attrs['k8s.statefulset.name'] == 'db'


def test_the_bound_token_payload_beats_the_hostname_and_gives_the_uid(tmp_path):
    token = _jwt({'kubernetes.io': {'namespace': 'from-token', 'pod': {'name': 'api-5d8f7c9b4d-x2x2z', 'uid': 'u-1'}}})
    _sa(tmp_path, token=token)  # no namespace file: the token has it
    attrs, problems = _detect(tmp_path, {'HOSTNAME': 'node-name-under-host-network'})
    assert attrs['k8s.pod.name'] == 'api-5d8f7c9b4d-x2x2z' and attrs['k8s.pod.uid'] == 'u-1'
    assert attrs['k8s.namespace.name'] == 'from-token' and attrs['service.name'] == 'api'
    assert problems == []


def test_a_downward_api_env_var_in_otel_resource_attributes_feeds_the_derivation(tmp_path):
    attrs, _ = _detect(tmp_path, {
        'HOSTNAME': 'node-1',
        'OTEL_RESOURCE_ATTRIBUTES': ('k8s.pod.name=web-5d8f7c9b4d-x2x2z,k8s.namespace.name=team%2Da,'
                                     'k8s.container.name=app')})
    assert attrs['service.name'] == 'web' and attrs['k8s.namespace.name'] == 'team-a'
    assert attrs['k8s.container.name'] == 'app'


def test_an_unrecognised_pod_name_never_becomes_the_service_name(tmp_path):
    attrs, _ = _detect(tmp_path, {'HOSTNAME': 'standalone'})
    assert 'service.name' not in attrs  # left to the next rule (unknown_service:...)
    assert attrs['k8s.pod.name'] == 'standalone'
    assert attrs[LABEL] == '//standalone'  # the whole pod name is fine in the label


def test_an_ambiguous_shape_is_only_a_service_name_candidate(tmp_path):
    attrs, _ = _detect(tmp_path, {'HOSTNAME': 'agent-x2x2z'})
    assert attrs['service.name'] == 'agent'
    assert not [k for k in attrs if k.startswith('k8s.') and k.endswith('.name') and k != 'k8s.pod.name']


PODINFO_LABELS = (
    'app.kubernetes.io/instance="checkout-prod"\n'
    'app.kubernetes.io/name="checkout"\n'
    'app.kubernetes.io/version="1.2.3"\n'
)


def _podinfo(root, labels=None, annotations=None, directory='etc/podinfo'):
    path = root / directory
    path.mkdir(parents=True, exist_ok=True)
    if labels is not None:
        (path / 'labels').write_text(labels, encoding='utf-8')
    if annotations is not None:
        (path / 'annotations').write_text(annotations, encoding='utf-8')


def test_service_name_follows_the_derivation_order(tmp_path):
    env = {'HOSTNAME': 'web-5d8f7c9b4d-x2x2z'}
    attrs, _ = _detect(tmp_path, env)
    assert attrs['service.name'] == 'web'  # workload name

    _podinfo(tmp_path, labels='app.kubernetes.io/name="checkout"\n')
    assert _detect(tmp_path, env)[0]['service.name'] == 'checkout'  # name label beats the workload

    _podinfo(tmp_path, labels=PODINFO_LABELS)
    attrs, _ = _detect(tmp_path, env)
    assert attrs['service.name'] == 'checkout-prod'  # instance label beats the name label
    assert attrs['service.version'] == '1.2.3'

    _podinfo(tmp_path, labels=PODINFO_LABELS, annotations=(
        'resource.opentelemetry.io/service.name="from-annotation"\n'
        'resource.opentelemetry.io/service.namespace="ns-annotation"\n'
        'resource.opentelemetry.io/service.version="9.9"\n'
        'resource.opentelemetry.io/service.instance.id="fixed-id"\n'))
    attrs, _ = _detect(tmp_path, {**env})
    assert (attrs['service.name'], attrs['service.namespace'], attrs['service.version']) == (
        'from-annotation', 'ns-annotation', '9.9')
    assert attrs['service.instance.id'] == 'fixed-id'  # only the annotation sets it


def test_downward_api_values_are_unescaped():
    text = ('a.b/note="line1\\nline2 \\"quoted\\" caf\\u00e9"\n'
            'plain="x"\n'
            'raw=unquoted value\n'
            'bad="unterminated\n'
            'not a line\n'
            '="no key"\n')
    parsed = parse_downward_file(text)
    assert parsed['a.b/note'] == 'line1\nline2 "quoted" café'
    assert parsed['plain'] == 'x'
    assert parsed['raw'] == 'unquoted value' and parsed['bad'] == '"unterminated'
    assert set(parsed) == {'a.b/note', 'plain', 'raw', 'bad'}


def test_annotations_with_escaped_values_reach_the_resource(tmp_path):
    _podinfo(tmp_path, annotations='resource.opentelemetry.io/service.name="svc \\"x\\" \\u00e9"\n')
    assert _detect(tmp_path, {'HOSTNAME': 'standalone'})[0]['service.name'] == 'svc "x" é'


def test_the_podinfo_dir_is_configurable(tmp_path):
    _podinfo(tmp_path, labels='app.kubernetes.io/name="elsewhere"\n', directory='mnt/info')
    attrs, _ = _detect(tmp_path, {'HOSTNAME': 'standalone', 'OTEL_WRAPPER_PODINFO_DIR': '/mnt/info'})
    assert attrs['service.name'] == 'elsewhere'


def test_a_missing_volume_is_silent(tmp_path):
    _sa(tmp_path, namespace='prod')
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        attrs, problems = _detect(tmp_path, {'HOSTNAME': 'web-5d8f7c9b4d-x2x2z'})
    assert problems == [] and attrs['service.name'] == 'web'


def test_with_no_service_account_at_all_the_hostname_still_works(tmp_path):
    attrs, problems = _detect(tmp_path, {'HOSTNAME': 'web-5d8f7c9b4d-x2x2z'})  # automountServiceAccountToken: false
    assert 'k8s.namespace.name' not in attrs and attrs['k8s.pod.name'] == 'web-5d8f7c9b4d-x2x2z'
    assert problems == []


def test_a_broken_token_costs_one_note_and_nothing_else(tmp_path):
    _sa(tmp_path, namespace='prod', token='not.a-jwt.at-all')
    attrs, problems = _detect(tmp_path, {'HOSTNAME': 'web-5d8f7c9b4d-x2x2z'})
    assert attrs['service.name'] == 'web' and attrs['k8s.namespace.name'] == 'prod'
    assert len(problems) == 1 and 'token' in problems[0]


def test_the_kubernetes_api_is_never_contacted(tmp_path, monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError('network access')

    monkeypatch.setattr(socket, 'create_connection', refuse)
    monkeypatch.setattr(socket.socket, 'connect', refuse)
    _sa(tmp_path, namespace='prod')
    assert _detect(tmp_path, {'HOSTNAME': 'web-5d8f7c9b4d-x2x2z'})[1] == []


# ----------------------------------------------------------------------------------------------------------------------
# AC-15: the process detector, arguments scrubbed
# ----------------------------------------------------------------------------------------------------------------------

def _process(monkeypatch, argv, environ=None):
    monkeypatch.setattr(sys, 'orig_argv', argv, raising=False)
    detector = WrapperProcessResourceDetector(environ=environ or {})
    return _attrs(detector.detect()), detector.problems


def test_command_args_keep_the_interpreter_and_flags_and_redact_secrets(monkeypatch):
    argv = ['/usr/bin/python3.12', '-X', 'utf8', '-m', 'app', '--password', 'hunter2-flag', '--api-key=hunter2-eq',
            '--db-url', 'postgresql://user:hunter2-url@db.example/app', '--workers', '4']
    attrs, problems = _process(monkeypatch, argv)
    args = list(attrs['process.command_args'])
    assert args[:5] == ['/usr/bin/python3.12', '-X', 'utf8', '-m', 'app'] and args[-2:] == ['--workers', '4']
    assert '--password' in args and '--api-key=[REDACTED]' in args  # the flag stays, its value goes
    assert 'postgresql://user:[REDACTED]@db.example/app' in args
    assert 'hunter2' not in json.dumps({k: str(v) for k, v in attrs.items()})  # in no attribute at all
    assert len(args) == len(argv) and attrs['process.args_count'] == len(argv)
    assert attrs['process.command'] == '/usr/bin/python3.12'
    assert 'process.command_line' not in attrs
    assert problems == []


def test_the_next_argument_after_a_secret_flag_is_redacted(monkeypatch):
    attrs, _ = _process(monkeypatch, ['python', 'run.py', '--token', 'abc123xyz', 'file.txt'])
    args = list(attrs['process.command_args'])
    assert 'abc123xyz' not in args and args[:3] == ['python', 'run.py', '--token'] and args[-1] == 'file.txt'


@pytest.mark.parametrize('value', ['false', 'FALSE', '0'])
def test_capture_command_args_false_drops_the_arguments(monkeypatch, value):
    attrs, _ = _process(monkeypatch, ['python', 'x.py', '--password', 'secret'], {
        'OTEL_WRAPPER_CAPTURE_COMMAND_ARGS': value})
    assert 'process.command_args' not in attrs and 'process.command_line' not in attrs
    assert attrs['process.executable.name']  # the rest is intact


def test_executable_name_is_the_base_name(monkeypatch):
    monkeypatch.setattr(sys, 'executable', os.path.join('opt', 'bin', 'python3.12'))
    assert _process(monkeypatch, ['python'])[0]['process.executable.name'] == 'python3.12'
    monkeypatch.setattr(sys, 'executable', '/usr/local/bin/python3.12')
    attrs, _ = _process(monkeypatch, ['python'])
    assert attrs['process.executable.name'] == 'python3.12'
    assert attrs['process.executable.path'] == '/usr/local/bin/python3.12'  # the path, not its directory
    monkeypatch.setattr(sys, 'executable', '')  # e.g. Pyodide
    assert _process(monkeypatch, ['python'])[0]['process.executable.name'] == 'python'


def test_runtime_and_pid_come_from_the_sdk_detector(monkeypatch):
    attrs, _ = _process(monkeypatch, ['python'])
    assert attrs['process.runtime.name'] == sys.implementation.name
    assert attrs['process.pid'] == os.getpid() and attrs['process.runtime.version']
    assert attrs['process.working_directory'] and attrs['host.name']


def test_an_owner_without_a_passwd_entry_falls_back_to_the_numeric_uid(monkeypatch):
    def boom():
        raise KeyError('getpwuid(): uid not found: 1000450000')

    monkeypatch.setattr(_resources.getpass, 'getuser', boom)
    monkeypatch.setattr(os, 'getuid', lambda: 1000450000, raising=False)
    attrs, problems = _process(monkeypatch, ['python'])
    assert attrs['process.owner'] == '1000450000' and problems == []


@pytest.mark.parametrize('kwargs, expected', [
    (dict(platform='emscripten', prefix='/'), 'pyodide'),
    (dict(frozen=True, prefix='/app'), 'frozen'),
    (dict(prefix='/opt/conda/envs/x', isdir=lambda p: p.replace('\\', '/').endswith('/conda-meta')), 'conda'),
    (dict(prefix='/srv/venv', base_prefix='/usr'), 'venv'),
    (dict(prefix='/usr', base_prefix='/usr'), 'system'),
])
def test_python_environment_kinds(kwargs, expected):
    kwargs = {'platform': 'linux', 'frozen': False, 'base_prefix': kwargs.get('prefix'), 'isdir': lambda p: False,
              **kwargs}
    out = python_environment(**kwargs)
    assert out['opentelemetry_wrapper.python.environment'] == expected
    assert out['opentelemetry_wrapper.python.environment.path'] == kwargs['prefix']


def test_python_environment_name_is_the_prefix_base_name():
    out = python_environment(prefix='/opt/conda/envs/my_env', base_prefix='/opt/conda', platform='linux',
                             frozen=False, isdir=lambda p: True)
    assert out['opentelemetry_wrapper.python.environment.name'] == 'my_env'


def test_the_real_environment_is_reported(monkeypatch):
    attrs, _ = _process(monkeypatch, ['python'])
    assert attrs['opentelemetry_wrapper.python.environment'] in ('conda', 'venv', 'system', 'frozen', 'pyodide')
    assert attrs['opentelemetry_wrapper.python.environment.path'] == sys.prefix


def test_a_free_threaded_build_is_marked(monkeypatch):
    monkeypatch.setattr(sys, '_is_gil_enabled', lambda: False, raising=False)
    assert _process(monkeypatch, ['python'])[0]['opentelemetry_wrapper.python.gil'] is False
    monkeypatch.setattr(sys, '_is_gil_enabled', lambda: True, raising=False)
    assert 'opentelemetry_wrapper.python.gil' not in _process(monkeypatch, ['python'])[0]


def test_the_label_outside_kubernetes_is_user_host_and_main_file(monkeypatch):
    monkeypatch.setattr(_resources, '_main_filename', lambda: 'main.py')
    monkeypatch.setattr(_resources, '_owner', lambda: 'avery')
    attrs, _ = _process(monkeypatch, ['python'], {'HOSTNAME': 'box', 'USERDNSDOMAIN': 'corp.example'})
    assert attrs[LABEL] == 'avery@box.corp.example:main.py'


def test_inside_kubernetes_the_process_detector_leaves_the_label_to_the_kubernetes_one(monkeypatch):
    assert LABEL not in _process(monkeypatch, ['python'], IN_K8S)[0]


# ----------------------------------------------------------------------------------------------------------------------
# guards: a detector never crashes, warns once, and the rest survives
# ----------------------------------------------------------------------------------------------------------------------

def test_a_failing_step_inside_a_detector_keeps_the_rest(monkeypatch):
    def boom(self):
        raise RuntimeError('psutil exploded')

    monkeypatch.setattr(WrapperProcessResourceDetector, '_sdk', boom)
    attrs, problems = _process(monkeypatch, ['python', '--password', 'x'])
    assert 'process.pid' not in attrs and attrs['process.command_args'][0] == 'python'
    assert attrs['process.executable.name'] and len(problems) == 1 and 'psutil exploded' in problems[0]


def test_a_failing_detector_adds_one_note_and_leaves_the_others_intact(monkeypatch, tmp_path):
    def boom(self):
        raise RuntimeError('detector bug')

    monkeypatch.setattr(KubernetesResourceDetector, 'detect', boom)
    notes = []
    resource = detect_resource(environ=IN_K8S, root=tmp_path, notes=notes)
    assert len(notes) == 1 and 'KubernetesResourceDetector' in notes[0] and 'detector bug' in notes[0]
    assert resource.attributes['process.pid'] == os.getpid()
    assert resource.attributes['service.name'].startswith('unknown_service:')


def test_service_name_falls_back_to_unknown_service_with_the_executable_name(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, 'executable', '/usr/bin/pypy3')
    resource = detect_resource(environ={}, root=tmp_path)
    assert resource.attributes['service.name'] == 'unknown_service:pypy3'


def test_detection_is_fast():
    start = time.perf_counter()
    detect_resource()
    assert time.perf_counter() - start < 2.0  # well inside get_aggregated_resources' 5 s timeout


# ----------------------------------------------------------------------------------------------------------------------
# AC-16: process.pid follows a fork (the SDK re-runs only its own process-dependent detectors)
# ----------------------------------------------------------------------------------------------------------------------

def test_the_resource_follows_the_pid(monkeypatch):
    resource = ForkAwareResource({'process.pid': os.getpid(), 'process.parent_pid': os.getppid(), 'other': 'kept'})
    monkeypatch.setattr(os, 'getpid', lambda: 424242)
    monkeypatch.setattr(os, 'getppid', lambda: 424241)
    attrs = _attrs(resource)
    assert attrs['process.pid'] == 424242 and attrs['process.parent_pid'] == 424241 and attrs['other'] == 'kept'


def test_a_pid_set_by_hand_is_not_overwritten(monkeypatch):
    resource = ForkAwareResource({'process.pid': 7})
    monkeypatch.setattr(os, 'getpid', lambda: 424242)
    assert _attrs(resource)['process.pid'] == 7


def test_merging_keeps_the_class_so_the_sdk_fork_hook_cannot_lose_the_fix(monkeypatch):
    resource = ForkAwareResource({'process.pid': os.getpid()})
    merged = resource.merge(ForkAwareResource({'service.instance.id': 'new'}))
    assert isinstance(merged, ForkAwareResource)
    monkeypatch.setattr(os, 'getpid', lambda: 424242)
    assert _attrs(merged)['process.pid'] == 424242 and _attrs(merged)['service.instance.id'] == 'new'


PID_CHANGE = scenario(__name__, 'v1_resources_pid_change', PRELUDE + r'''
import os
otel.configure()

@otel
def f():
    pass

real = os.getpid()
os.getpid = lambda: 424242  # what a forked worker would see (no fork on every platform)
f()
(span,) = exporter.get_finished_spans()
emit('pids', [real, span.resource.attributes['process.pid'], 424242])
''')


def test_the_configured_resource_follows_the_pid_into_spans():
    real, seen, fake = PID_CHANGE.result()['pids']
    assert real != fake and seen == fake


FORKED = scenario(__name__, 'v1_resources_fork', PRELUDE + r'''
import json
import os
otel.configure(service_name='forky')

@otel
def f():
    pass

f()
emit('parent', [dict(s.resource.attributes) for s in exporter.get_finished_spans()][0])
exporter.clear()
read_end, write_end = os.pipe()
pid = os.fork()
if pid == 0:
    f()
    (span,) = exporter.get_finished_spans()
    attrs = dict(span.resource.attributes)
    os.write(write_end, json.dumps({'pid': attrs.get('process.pid'), 'own_pid': os.getpid(),
                                    'instance': attrs.get('service.instance.id'),
                                    'service_name': attrs.get('service.name')}).encode())
    os._exit(0)
os.close(write_end)
data = b''
while chunk := os.read(read_end, 4096):
    data += chunk
os.waitpid(pid, 0)
emit('child', json.loads(data))
''') if hasattr(os, 'fork') else None


@pytest.mark.skipif(not hasattr(os, 'fork'), reason='no fork on this platform (Linux CI runs it)')
def test_a_forked_worker_has_its_own_pid_and_instance_id():
    result = FORKED.result()
    parent, child = result['parent'], result['child']
    assert parent['process.pid'] != child['own_pid']
    assert child['pid'] == child['own_pid']  # the master's pid is not inherited
    assert child['instance'] and child['instance'] != parent['service.instance.id']
    assert child['service_name'] == 'forky'


# ----------------------------------------------------------------------------------------------------------------------
# DEC-33: precedence through configure (detectors < env < explicit)
# ----------------------------------------------------------------------------------------------------------------------

_K8S_ENV = {'KUBERNETES_SERVICE_HOST': '10.0.0.1', 'HOSTNAME': 'web-5d8f7c9b4d-x2x2z', 'OTEL_SERVICE_NAME': None,
            'OTEL_RESOURCE_ATTRIBUTES': None, 'OTEL_WRAPPER_PODINFO_DIR': None}
_SPAN_ATTRS = r'''
@otel
def f():
    pass

f()
(span,) = exporter.get_finished_spans()
emit('attrs', {k: v if isinstance(v, (str, int, bool)) else list(v) for k, v in span.resource.attributes.items()})
'''

DERIVED = scenario(__name__, 'v1_resources_derived', PRELUDE + 'otel.configure()\n' + _SPAN_ATTRS, env=_K8S_ENV)
FROM_ENV = scenario(__name__, 'v1_resources_env', PRELUDE + 'otel.configure()\n' + _SPAN_ATTRS,
                    env={**_K8S_ENV, 'OTEL_SERVICE_NAME': 'from-env'})
FROM_ENV_ATTRS = scenario(__name__, 'v1_resources_env_attrs', PRELUDE + 'otel.configure()\n' + _SPAN_ATTRS,
                          env={**_K8S_ENV, 'OTEL_RESOURCE_ATTRIBUTES': 'service.name=from-attrs,team=x'})
EXPLICIT = scenario(__name__, 'v1_resources_explicit',
                    PRELUDE + "otel.configure(service_name='explicit', resource_attributes={'team': 'y'})\n"
                    + _SPAN_ATTRS, env={**_K8S_ENV, 'OTEL_SERVICE_NAME': 'from-env'})
OUTSIDE = scenario(__name__, 'v1_resources_outside', PRELUDE + 'otel.configure()\n' + _SPAN_ATTRS,
                   env={'KUBERNETES_SERVICE_HOST': None, 'OTEL_SERVICE_NAME': None, 'OTEL_RESOURCE_ATTRIBUTES': None})


def test_the_k8s_derivation_names_the_service_through_configure():
    attrs = DERIVED.result()['attrs']
    assert attrs['service.name'] == 'web' and attrs['k8s.deployment.name'] == 'web'
    assert attrs[LABEL] == '/web/web-5d8f7c9b4d-x2x2z'
    assert attrs['telemetry.sdk.name'] == 'opentelemetry' and attrs['service.instance.id']
    assert attrs['process.pid'] and attrs['process.command_args']


def test_otel_service_name_beats_the_k8s_derivation():
    attrs = FROM_ENV.result()['attrs']
    assert attrs['service.name'] == 'from-env' and attrs['k8s.deployment.name'] == 'web'  # only the name is overridden


def test_service_name_in_otel_resource_attributes_beats_the_k8s_derivation():
    attrs = FROM_ENV_ATTRS.result()['attrs']
    assert attrs['service.name'] == 'from-attrs' and attrs['team'] == 'x'


def test_explicit_arguments_beat_the_environment_and_keep_detected_attributes():
    attrs = EXPLICIT.result()['attrs']
    assert attrs['service.name'] == 'explicit' and attrs['team'] == 'y'
    assert attrs['k8s.pod.name'] == 'web-5d8f7c9b4d-x2x2z'  # explicit attributes do not drop the detected ones


def test_outside_kubernetes_the_service_name_is_unknown_service_and_the_label_is_user_at_host():
    attrs = OUTSIDE.result()['attrs']
    assert attrs['service.name'].startswith('unknown_service:') and attrs['service.name'] != 'unknown_service:'
    assert attrs[LABEL]  # <user>@<host>:<main>, whatever this machine has (the format is tested above)
    assert 'k8s.pod.name' not in attrs and attrs['opentelemetry_wrapper.python.environment']
