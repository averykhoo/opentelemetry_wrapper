"""
environment variables: the disabled switch (DEC-24, DEC-5), the effective settings (explicit > env > default, DEC-27),
and v0's old names, read for one release with a startup warning (DEC-52, DEC-59)

the OTLP exporters and the SDK read most standard variables themselves (endpoints, headers, timeouts, sampler,
`OTEL_SERVICE_NAME`, `OTEL_RESOURCE_ATTRIBUTES`); we only read what decides which exporters to build (DEC-28)
"""
import logging
import os
import re
from dataclasses import dataclass
from dataclasses import fields
from typing import Any
from typing import Dict
from typing import List
from typing import Mapping
from typing import Optional
from typing import Tuple
from urllib.parse import unquote
from urllib.parse import urlsplit

SIGNALS = ('traces', 'metrics', 'logs')
# DEC-2, confirmed 2026-10-18: credentials and session handles; personal data (`email`, `name`) is recorded
DEFAULT_HEADER_ATTRIBUTES_EXCLUDE = ('*token*', 'at_hash', 'c_hash', 'nonce', 'session_state', 'sid')
# v0's hardcoded list (`instrument_requests.py`); x-process-time-seconds is what v0's example app sets
DEFAULT_RESPONSE_HEADER_ATTRIBUTES = ('x-kong-proxy-latency', 'x-kong-upstream-latency',
                                      'x-envoy-upstream-service-time',  # upstream latency
                                      'x-authz-response-time-seconds', 'x-process-time-seconds')
EXPORTER_CHOICES = ('otlp', 'console', 'none')
PROMETHEUS_DEFAULT_PORT = 9464  # the spec's default for OTEL_EXPORTER_PROMETHEUS_PORT


def _env(name: str, environ: Mapping[str, str]) -> Optional[str]:
    value = environ.get(name)
    if value is None or not value.strip():
        return None
    return value.strip()


def disabled(environ: Optional[Mapping[str, str]] = None) -> bool:
    """`OTEL_WRAPPER_DISABLED=true` or the standard `OTEL_SDK_DISABLED=true` (read every time: cheap, and a test may
    set it after import)"""
    environ = os.environ if environ is None else environ
    return (environ.get('OTEL_WRAPPER_DISABLED', '').strip().casefold() == 'true'
            or environ.get('OTEL_SDK_DISABLED', '').strip().casefold() == 'true')


@dataclass(frozen=True)
class Settings:
    """the effective configuration, normalised, so two calls with the same meaning compare equal"""
    service_name: Optional[str] = None
    resource_attributes: Tuple[Tuple[str, Any], ...] = ()  # explicit, plus v0's OTEL_SERVICE_NAMESPACE
    traces_exporter: Tuple[str, ...] = ()
    metrics_exporter: Tuple[str, ...] = ()
    logs_exporter: Tuple[str, ...] = ()
    otlp_endpoint: Optional[str] = None  # explicit only; per-signal and env endpoints are read by the exporters
    otlp_headers: Tuple[Tuple[str, str], ...] = ()  # explicit, or v0's OTEL_EXPORTER_OTLP_HEADER
    log_level: str = 'info'
    log_format: str = 'json'
    prometheus_path: str = '/metrics'  # the FastAPI route (workstream 9); '' adds none
    prometheus_host: str = 'localhost'  # the standalone Prometheus server's interface (OTEL_EXPORTER_PROMETHEUS_HOST)
    prometheus_port: Optional[int] = None  # the standalone Prometheus server's port; None: no server
    header_attributes: Tuple[str, ...] = ('x-userinfo',)  # request headers to decode onto the server span (OTW-7)
    header_attributes_exclude: Tuple[str, ...] = DEFAULT_HEADER_ATTRIBUTES_EXCLUDE  # claim denylist (DEC-2)
    response_header_attributes: Tuple[str, ...] = DEFAULT_RESPONSE_HEADER_ATTRIBUTES  # `requests` client spans
    fastapi_asgi_spans: bool = False  # FastAPI's per-request ASGI `http send` / `http receive` spans (DEC-93)

    def without_log_level(self) -> 'Settings':
        return Settings(**{**asdict_shallow(self), 'log_level': ''})

    def redacted(self, sdk_env: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        """a read-only view's content: header values are secrets (v0 logged its auth header). `sdk_env` (from
        `sdk_env_settings`) fills in what the SDK reads from the environment itself, so the view shows the service
        name, resource attributes, endpoint and headers in use, not only the explicit ones"""
        out = asdict_shallow(self)
        headers = self.otlp_headers
        if sdk_env is not None:  # explicit (and v0's names, already in these fields) beat the environment
            out['service_name'] = self.service_name or sdk_env['service_name']
            attributes = {**dict(sdk_env['resource_attributes']), **dict(self.resource_attributes)}
            out['resource_attributes'] = tuple(sorted(attributes.items()))
            out['otlp_endpoint'] = self.otlp_endpoint or sdk_env['otlp_endpoint']
            headers = headers or sdk_env['otlp_headers']
        out['otlp_headers'] = tuple((k, '[REDACTED]') for k, _ in headers)
        return out


def asdict_shallow(settings: Settings) -> Dict[str, Any]:
    return {f.name: getattr(settings, f.name) for f in fields(settings)}


CONFIGURE_OPTIONS = tuple(f.name for f in fields(Settings))


def _split(value: str) -> Tuple[str, ...]:
    return tuple(part.strip() for part in value.split(',') if part.strip())


def _parse_v0_headers(value: str, separator: str) -> Tuple[Tuple[str, str], ...]:
    out = []
    for item in value.split(separator):
        if not item.strip():
            continue
        sep = '=' if '=' in item else ':'
        key, _, val = item.partition(sep)
        out.append((key.strip(), val.strip()))
    return tuple(out)


def _pairs(value: Optional[str], lower_keys: bool = False) -> Dict[str, str]:
    """`key=value` pairs, comma-separated, values URL-encoded: how the SDK reads OTEL_RESOURCE_ATTRIBUTES and
    OTEL_EXPORTER_OTLP_HEADERS (header names lowercased, as the exporters do); a pair without `=` is skipped"""
    out: Dict[str, str] = {}
    for item in (value or '').split(','):
        key, sep, val = item.partition('=')
        key = unquote(key).strip()
        if sep and key:
            out[key.lower() if lower_keys else key] = unquote(val.strip())
    return out


def sdk_env_settings(environ: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    """what the SDK reads from the environment itself (the resource, the OTLP exporters), for `otel.config`: the
    wrapper leaves these to the SDK, so `resolve` only holds the explicit values (DEC-28). per-signal endpoints and
    headers (OTEL_EXPORTER_OTLP_<SIGNAL>_*) are not in the view"""
    environ = os.environ if environ is None else environ
    attributes = _pairs(_env('OTEL_RESOURCE_ATTRIBUTES', environ))
    service_name = _env('OTEL_SERVICE_NAME', environ) or (attributes.get('service.name') or '').strip() or None
    headers = _pairs(_env('OTEL_EXPORTER_OTLP_HEADERS', environ), lower_keys=True)
    return {'service_name': service_name,
            'resource_attributes': tuple(sorted(attributes.items())),
            'otlp_endpoint': (_env('OTEL_EXPORTER_OTLP_ENDPOINT', environ) or '').rstrip('/') or None,
            'otlp_headers': tuple(sorted(headers.items()))}


def _endpoint_set(signal: str, explicit_endpoint: Optional[str], environ: Mapping[str, str]) -> bool:
    return bool(explicit_endpoint
                or _env('OTEL_EXPORTER_OTLP_ENDPOINT', environ)
                or _env(f'OTEL_EXPORTER_OTLP_{signal.upper()}_ENDPOINT', environ))


def _is_str(value: Any) -> bool:
    return isinstance(value, str)


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _is_port(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 < value < 65536


def _is_bool(value: Any) -> bool:
    return isinstance(value, bool)


def _is_strings(value: Any) -> bool:
    return isinstance(value, str) or (isinstance(value, (list, tuple, set, frozenset))
                                      and all(isinstance(item, str) for item in value))


_EXPECTED = {  # what `otel.configure(...)` takes, by option: (description, check)
    'service_name': ('a string', _is_str),
    'resource_attributes': ('a mapping', _is_mapping),
    'traces_exporter': ('a string or a list of strings', _is_strings),
    'metrics_exporter': ('a string or a list of strings', _is_strings),
    'logs_exporter': ('a string or a list of strings', _is_strings),
    'otlp_endpoint': ('a string', _is_str),
    'otlp_headers': ('a mapping', _is_mapping),
    'log_level': ('a string', _is_str),
    'log_format': ('a string', _is_str),
    'prometheus_path': ('a string', _is_str),
    'prometheus_host': ('a string', _is_str),
    'prometheus_port': ('a port number (an int from 1 to 65535)', _is_port),
    'header_attributes': ('a string or a list of strings', _is_strings),
    'header_attributes_exclude': ('a string or a list of strings', _is_strings),
    'response_header_attributes': ('a string or a list of strings', _is_strings),
    'fastapi_asgi_spans': ('True or False', _is_bool),
}


def is_log_level(value: Any) -> bool:
    """a name `logging` knows, in any case ('warn', 'WARNING', ...)"""
    return isinstance(value, str) and value.strip().upper() in logging.getLevelNamesMapping()


def clean_explicit(explicit: Mapping[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """the explicit options with the wrong-typed ones dropped (they fall back to the environment, then the default),
    and one warning for each; an option that isn't one of ours at all is a `TypeError`, like any bad keyword"""
    cleaned: Dict[str, Any] = {}
    notes: List[str] = []
    for name, value in explicit.items():
        if name not in CONFIGURE_OPTIONS:
            raise TypeError(f'otel.configure() got an unexpected keyword argument {name!r}')
        description, check = _EXPECTED[name]
        if value is None or check(value):
            cleaned[name] = value
        else:
            notes.append(f'otel.configure({name}=...) expects {description}, not {type(value).__name__}; '
                         f'it is ignored')
    return cleaned, notes


def resolve(explicit: Mapping[str, Any], environ: Optional[Mapping[str, str]] = None
            ) -> Tuple[Settings, List[str]]:
    """the effective settings (explicit > env > default) and the startup warnings to emit once state is consistent;
    never raises for a wrong value, only for an option name that isn't one of ours"""
    environ = os.environ if environ is None else environ
    explicit, notes = clean_explicit(explicit)
    values: Dict[str, Any] = {}

    # v0's old names (DEC-52 / DEC-59), read for one release
    def migrated(old: str, new: str, hint: str = '', superseded: bool = True) -> Optional[str]:
        old_value = _env(old, environ)
        if old_value is None:
            return None
        notes.append(f'{old} is v0\'s name and is read for one release only; use {new} instead{hint}')
        return None if superseded and _env(new, environ) is not None else old_value

    v0_namespace = migrated('OTEL_SERVICE_NAMESPACE', 'OTEL_RESOURCE_ATTRIBUTES=service.namespace=...',
                            superseded=False)
    v0_headers = migrated('OTEL_EXPORTER_OTLP_HEADER', 'OTEL_EXPORTER_OTLP_HEADERS',
                          ' (key=value pairs, comma-separated, values URL-encoded)')
    v0_prometheus_path = migrated('OTEL_EXPORTER_PROMETHEUS_ENDPOINT', 'OTEL_WRAPPER_PROMETHEUS_PATH')
    if (v0_prometheus_path is None and 'OTEL_EXPORTER_PROMETHEUS_ENDPOINT' in environ
            and 'OTEL_WRAPPER_PROMETHEUS_PATH' not in environ):
        v0_prometheus_path = ''  # set but blank: v0's way to turn the route off
        notes.append('OTEL_EXPORTER_PROMETHEUS_ENDPOINT is v0\'s name and is read for one release only; use '
                     'OTEL_WRAPPER_PROMETHEUS_PATH instead (empty for no route)')
    v0_header_attributes = migrated('OTEL_HEADER_ATTRIBUTES', 'OTEL_WRAPPER_HEADER_ATTRIBUTES')
    if _env('OTEL_LOG_LEVEL', environ) is not None and _env('OTEL_WRAPPER_LOG_LEVEL', environ) is None:
        notes.append('OTEL_LOG_LEVEL is not read: it is the OpenTelemetry SDK\'s own variable; '
                     'use OTEL_WRAPPER_LOG_LEVEL for the log level')
    if _env('OTEL_EXPORTER_OTLP_INSECURE', environ) is not None:
        notes.append('OTEL_EXPORTER_OTLP_INSECURE is ignored: only OTLP over HTTP is supported; '
                     'use an http:// or https:// endpoint')
    for name in ('OTEL_EXPORTER_OTLP_PROTOCOL', *(f'OTEL_EXPORTER_OTLP_{s.upper()}_PROTOCOL' for s in SIGNALS)):
        if (_env(name, environ) or '').casefold() == 'grpc':
            notes.append(f'{name}=grpc is not supported: only OTLP over HTTP is exported (port 4318 by default)')
    otlp_endpoint = (explicit.get('otlp_endpoint') or '').strip().rstrip('/') or None  # as `_otlp_kwargs` will use it
    endpoints = [('otel.configure(otlp_endpoint=...)', otlp_endpoint)]
    endpoints += [(name, _env(name, environ)) for name in
                  ('OTEL_EXPORTER_OTLP_ENDPOINT', *(f'OTEL_EXPORTER_OTLP_{s.upper()}_ENDPOINT' for s in SIGNALS))]
    for name, endpoint in endpoints:
        if endpoint and _looks_like_grpc(endpoint):
            notes.append(f'{name}={endpoint!r} looks like a gRPC endpoint (port 4317 or grpc://), but only OTLP '
                         f'over HTTP is exported: use port 4318 and http:// or https://')

    # explicit > env > default
    values['service_name'] = (explicit.get('service_name') or '').strip() or None  # env: read by the SDK's resource
    attributes = dict(explicit.get('resource_attributes') or {})
    if v0_namespace is not None and 'service.namespace' not in attributes:
        if 'service.namespace=' not in (_env('OTEL_RESOURCE_ATTRIBUTES', environ) or ''):
            attributes['service.namespace'] = v0_namespace
    values['resource_attributes'] = tuple(sorted(attributes.items()))
    values['otlp_endpoint'] = otlp_endpoint
    prometheus_chosen = False  # `prometheus` among the metrics exporters: serve on the standard port, 9464, unless set
    for signal in SIGNALS:
        option = f'{signal}_exporter'
        chosen = explicit.get(option)
        if chosen is None:
            chosen = _env(f'OTEL_{signal.upper()}_EXPORTER', environ)
        if chosen is None:
            chosen = 'otlp' if _endpoint_set(signal, values['otlp_endpoint'], environ) else 'none'
        names = _split(chosen) if isinstance(chosen, str) else tuple(chosen)
        if signal == 'metrics' and 'prometheus' in names:  # the standard switch for the standalone scrape server
            prometheus_chosen = True
            names = tuple(n for n in names if n != 'prometheus')
        unknown = [n for n in names if n not in EXPORTER_CHOICES]
        if unknown:
            choices = EXPORTER_CHOICES + (('prometheus',) if signal == 'metrics' else ())
            notes.append(f'{option} {unknown!r} not supported (choose from {", ".join(choices)}); ignored')
        names = tuple(n for n in names if n in EXPORTER_CHOICES and n != 'none')
        values[option] = tuple(sorted(set(names)))
    headers = explicit.get('otlp_headers')
    if headers is not None:
        values['otlp_headers'] = tuple(sorted(dict(headers).items()))
    elif v0_headers is not None:
        separator = environ.get('OTEL_EXPORTER_OTLP_HEADER_SEPARATOR') or '\t'
        values['otlp_headers'] = _parse_v0_headers(v0_headers, separator)
    values['log_level'] = 'info'
    for source, candidate in (('otel.configure(log_level=...)', explicit.get('log_level')),
                              ('OTEL_WRAPPER_LOG_LEVEL', _env('OTEL_WRAPPER_LOG_LEVEL', environ))):
        if candidate is None or not candidate.strip():
            continue
        if is_log_level(candidate):
            values['log_level'] = candidate.strip().lower()
            break
        notes.append(f'{source} {candidate!r} is not a logging level name (debug, info, warning, error, critical); '
                     f'it is ignored')
    log_format = (explicit.get('log_format') or _env('OTEL_WRAPPER_LOG_FORMAT', environ) or 'json').lower()
    if log_format not in ('json', 'off'):
        notes.append(f'log_format {log_format!r} not supported (json or off); using json')
        log_format = 'json'
    values['log_format'] = log_format
    path = explicit.get('prometheus_path')
    if path is None:
        path = environ.get('OTEL_WRAPPER_PROMETHEUS_PATH')
    if path is None:
        path = v0_prometheus_path if v0_prometheus_path is not None else '/metrics'
    values['prometheus_path'] = _prometheus_path(path, notes)
    values['prometheus_host'] = ((explicit.get('prometheus_host') or '').strip()
                                 or _env('OTEL_EXPORTER_PROMETHEUS_HOST', environ) or 'localhost')
    port = explicit.get('prometheus_port')
    if port is None:
        raw_port = _env('OTEL_EXPORTER_PROMETHEUS_PORT', environ)
        if raw_port is not None:
            port = int(raw_port) if re.fullmatch('[0-9]{1,5}', raw_port) else None
            if not _is_port(port):
                notes.append(f'OTEL_EXPORTER_PROMETHEUS_PORT {raw_port!r} is not a port number (1 to 65535); it is '
                             f'ignored, so no Prometheus server is started')
                port = None
        elif prometheus_chosen:
            port = PROMETHEUS_DEFAULT_PORT
    values['prometheus_port'] = port
    header_attributes = explicit.get('header_attributes')
    if header_attributes is None:
        raw = _env('OTEL_WRAPPER_HEADER_ATTRIBUTES', environ) or v0_header_attributes
        header_attributes = _split(raw) if raw is not None else ('x-userinfo',)
    elif isinstance(header_attributes, str):
        header_attributes = _split(header_attributes)
    values['header_attributes'] = tuple(h.lower() for h in header_attributes)
    # DEC-90: the variable adds to the default denylist (a typo in it can't start recording tokens); only an explicit
    # list replaces it, and an explicit [] clears it. a blank variable is unset
    exclude_env = _env('OTEL_WRAPPER_HEADER_ATTRIBUTES_EXCLUDE', environ)
    exclude_default = DEFAULT_HEADER_ATTRIBUTES_EXCLUDE
    if exclude_env is not None:
        exclude_default = tuple(dict.fromkeys(DEFAULT_HEADER_ATTRIBUTES_EXCLUDE + _split(exclude_env)))
    values['header_attributes_exclude'] = _strings(explicit.get('header_attributes_exclude'), None,
                                                   exclude_default, lower=False)
    values['response_header_attributes'] = _strings(explicit.get('response_header_attributes'),
                                                    _env('OTEL_WRAPPER_RESPONSE_HEADER_ATTRIBUTES', environ),
                                                    DEFAULT_RESPONSE_HEADER_ATTRIBUTES, lower=True)
    values['fastapi_asgi_spans'] = _fastapi_asgi_spans(explicit.get('fastapi_asgi_spans'), environ, notes)
    return Settings(**values), notes


FASTAPI_ASGI_SPANS_ENV = 'OTEL_WRAPPER_FASTAPI_ASGI_SPANS'


def _fastapi_asgi_spans(explicit: Optional[bool], environ: Mapping[str, str], notes: List[str]) -> bool:
    """DEC-93: FastAPI's ASGI `http send` / `http receive` child spans are off (noise in most traces) unless asked
    for, for debugging: explicit > `OTEL_WRAPPER_FASTAPI_ASGI_SPANS` (`true` / `false`, any case) > off. upstream
    reads no variable for its `exclude_spans`"""
    if explicit is not None:
        return explicit
    raw = _env(FASTAPI_ASGI_SPANS_ENV, environ)
    if raw is None or raw.casefold() == 'false':
        return False
    if raw.casefold() == 'true':
        return True
    notes.append(f"{FASTAPI_ASGI_SPANS_ENV} {raw!r} is not true or false; it is ignored, so FastAPI's ASGI send and "
                 f"receive spans stay off")
    return False


_PROMETHEUS_PATH = re.compile(r'(/[A-Za-z0-9_-]+)+/?')


def _prometheus_path(path: str, notes: List[str]) -> str:
    """the FastAPI route's path, normalised like v0's (repeated slashes collapsed, a leading slash added); blank
    means no route, and so does a path that isn't plain segments of `[A-Za-z0-9_-]`, with a warning"""
    path = path.strip()
    if not path:
        return ''
    normalised = '/' + re.sub(r'/+', '/', path).lstrip('/')
    if not _PROMETHEUS_PATH.fullmatch(normalised):
        notes.append(f'prometheus_path {path!r} is not a path of plain segments ([A-Za-z0-9_-], like /metrics); no '
                     f'/metrics route is added to FastAPI apps')
        return ''
    if normalised != path:
        notes.append(f'prometheus_path {path!r} is used as {normalised!r}')
    return normalised


def _strings(explicit: Any, env: Optional[str], default: Tuple[str, ...], lower: bool) -> Tuple[str, ...]:
    """a list option: explicit (a string is comma-separated) > env (comma-separated) > default"""
    value: Any = explicit if explicit is not None else env
    if value is None:
        return default
    items = _split(value) if isinstance(value, str) else tuple(v.strip() for v in value if v.strip())
    return tuple(v.lower() for v in items) if lower else items


def _looks_like_grpc(endpoint: str) -> bool:
    try:
        parts = urlsplit(endpoint if '://' in endpoint else f'http://{endpoint}')
        return parts.scheme.casefold() == 'grpc' or parts.port == 4317
    except ValueError:
        return False


__all__ = ('Settings', 'disabled', 'resolve', 'CONFIGURE_OPTIONS', 'SIGNALS')
