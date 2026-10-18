"""
environment variables: the disabled switch (DEC-24, DEC-5), the effective settings (explicit > env > default, DEC-27),
and v0's old names, read for one release with a startup warning (DEC-52, DEC-59)

the OTLP exporters and the SDK read most standard variables themselves (endpoints, headers, timeouts, sampler,
`OTEL_SERVICE_NAME`, `OTEL_RESOURCE_ATTRIBUTES`); we only read what decides which exporters to build (DEC-28)
"""
import os
from dataclasses import dataclass
from dataclasses import fields
from typing import Any
from typing import Dict
from typing import List
from typing import Mapping
from typing import Optional
from typing import Tuple
from urllib.parse import urlsplit

SIGNALS = ('traces', 'metrics', 'logs')
EXPORTER_CHOICES = ('otlp', 'console', 'none')


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
    prometheus_path: str = '/metrics'  # used by workstream 9
    header_attributes: Tuple[str, ...] = ('x-userinfo',)  # used by workstream 5

    def without_log_level(self) -> 'Settings':
        return Settings(**{**asdict_shallow(self), 'log_level': ''})

    def redacted(self) -> Dict[str, Any]:
        """a read-only view's content: header values are secrets (v0 logged its auth header)"""
        out = asdict_shallow(self)
        out['otlp_headers'] = tuple((k, '[REDACTED]') for k, _ in self.otlp_headers)
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


def _endpoint_set(signal: str, explicit_endpoint: Optional[str], environ: Mapping[str, str]) -> bool:
    return bool(explicit_endpoint
                or _env('OTEL_EXPORTER_OTLP_ENDPOINT', environ)
                or _env(f'OTEL_EXPORTER_OTLP_{signal.upper()}_ENDPOINT', environ))


def resolve(explicit: Mapping[str, Any], environ: Optional[Mapping[str, str]] = None
            ) -> Tuple[Settings, List[str]]:
    """the effective settings (explicit > env > default) and the startup warnings to emit once state is consistent"""
    environ = os.environ if environ is None else environ
    notes: List[str] = []
    values: Dict[str, Any] = {}

    for name in explicit:
        if name not in CONFIGURE_OPTIONS:
            raise TypeError(f'otel.configure() got an unexpected keyword argument {name!r}')

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
    endpoints = [('otel.configure(otlp_endpoint=...)', explicit.get('otlp_endpoint'))]
    endpoints += [(name, _env(name, environ)) for name in
                  ('OTEL_EXPORTER_OTLP_ENDPOINT', *(f'OTEL_EXPORTER_OTLP_{s.upper()}_ENDPOINT' for s in SIGNALS))]
    for name, endpoint in endpoints:
        if endpoint and _looks_like_grpc(endpoint):
            notes.append(f'{name}={endpoint!r} looks like a gRPC endpoint (port 4317 or grpc://), but only OTLP '
                         f'over HTTP is exported: use port 4318 and http:// or https://')

    # explicit > env > default
    values['service_name'] = explicit.get('service_name')  # env OTEL_SERVICE_NAME is read by the SDK's resource
    attributes = dict(explicit.get('resource_attributes') or {})
    if v0_namespace is not None and 'service.namespace' not in attributes:
        if 'service.namespace=' not in (_env('OTEL_RESOURCE_ATTRIBUTES', environ) or ''):
            attributes['service.namespace'] = v0_namespace
    values['resource_attributes'] = tuple(sorted(attributes.items()))
    values['otlp_endpoint'] = explicit.get('otlp_endpoint') or None
    for signal in SIGNALS:
        option = f'{signal}_exporter'
        chosen = explicit.get(option)
        if chosen is None:
            chosen = _env(f'OTEL_{signal.upper()}_EXPORTER', environ)
        if chosen is None:
            chosen = 'otlp' if _endpoint_set(signal, values['otlp_endpoint'], environ) else 'none'
        names = _split(chosen) if isinstance(chosen, str) else tuple(chosen)
        unknown = [n for n in names if n not in EXPORTER_CHOICES]
        if unknown:
            notes.append(f'{option} {unknown!r} not supported (choose from {", ".join(EXPORTER_CHOICES)}); ignored')
        names = tuple(n for n in names if n in EXPORTER_CHOICES and n != 'none')
        values[option] = tuple(sorted(set(names)))
    headers = explicit.get('otlp_headers')
    if headers is not None:
        values['otlp_headers'] = tuple(sorted(dict(headers).items()))
    elif v0_headers is not None:
        separator = environ.get('OTEL_EXPORTER_OTLP_HEADER_SEPARATOR') or '\t'
        values['otlp_headers'] = _parse_v0_headers(v0_headers, separator)
    values['log_level'] = (explicit.get('log_level') or _env('OTEL_WRAPPER_LOG_LEVEL', environ) or 'info').lower()
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
    values['prometheus_path'] = path.strip()
    header_attributes = explicit.get('header_attributes')
    if header_attributes is None:
        raw = _env('OTEL_WRAPPER_HEADER_ATTRIBUTES', environ) or v0_header_attributes
        header_attributes = _split(raw) if raw is not None else ('x-userinfo',)
    elif isinstance(header_attributes, str):
        header_attributes = _split(header_attributes)
    values['header_attributes'] = tuple(h.lower() for h in header_attributes)
    return Settings(**values), notes


def _looks_like_grpc(endpoint: str) -> bool:
    try:
        parts = urlsplit(endpoint if '://' in endpoint else f'http://{endpoint}')
        return parts.scheme.casefold() == 'grpc' or parts.port == 4317
    except ValueError:
        return False


__all__ = ('Settings', 'disabled', 'resolve', 'CONFIGURE_OPTIONS', 'SIGNALS')
