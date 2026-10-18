"""
a wrapper around `opentelemetry` and `opentelemetry-instrumentation-*` to make life a bit easier
"""

__version__ = '0.1.25'

import importlib
import threading
from typing import Any
from typing import List

from opentelemetry_wrapper.v1 import OtelWrapperWarning  # noqa: F401
from opentelemetry_wrapper.v1 import otel  # noqa: F401

# the root is v1 (DEC-80, DEC-46). v0's names still resolve from here, lazily: the first access imports v0, and so runs
# v0's import-time setup (its tracer provider and so on), which importing this root never does

# in the order v0's root imported them: v0's own modules import names back from this root (`instrument_sqlalchemy.py`
# wants `instrument_decorate`), so each name is bound here as soon as its module is imported
_V0_SOURCES = (
    ('opentelemetry_wrapper.v0.config.otel_headers', (
        'OTEL_EXPORTER_OTLP_ENDPOINT', 'OTEL_EXPORTER_OTLP_HEADER', 'OTEL_EXPORTER_OTLP_INSECURE',
        'OTEL_EXPORTER_PROMETHEUS_ENDPOINT', 'OTEL_EXPORTER_PROMETHEUS_PORT', 'OTEL_HEADER_ATTRIBUTES',
        'OTEL_LOG_LEVEL', 'OTEL_SERVICE_NAME', 'OTEL_SERVICE_NAMESPACE', 'OTEL_WRAPPER_DISABLED')),
    ('opentelemetry_wrapper.v0.dependencies.opentelemetry.instrument_dataclasses', ('instrument_dataclasses',)),
    ('opentelemetry_wrapper.v0.dependencies.opentelemetry.instrument_decorator', ('instrument_decorate',)),
    ('opentelemetry_wrapper.v0.dependencies.opentelemetry.instrument_fastapi', ('instrument_fastapi_app',)),
    ('opentelemetry_wrapper.v0.dependencies.opentelemetry.instrument_logging', ('instrument_logging',)),
    ('opentelemetry_wrapper.v0.dependencies.opentelemetry.instrument_requests', ('instrument_requests',)),
    ('opentelemetry_wrapper.v0.dependencies.opentelemetry.instrument_sqlalchemy',
     ('instrument_sqlalchemy', 'instrument_sqlalchemy_engine')),
    ('opentelemetry_wrapper.v0.dependencies.opentelemetry.instrument_system_metrics', ('instrument_system_metrics',)),
    ('opentelemetry_wrapper.v0._root', ('instrument_all',)),
)
_V0_NAMES = tuple(sorted(name for _, names in _V0_SOURCES for name in names))

_v0_lock = threading.RLock()
_v0_loading = False
_v0_loaded = False


def _load_v0() -> None:
    global _v0_loading, _v0_loaded
    with _v0_lock:
        if _v0_loaded or _v0_loading:  # loading: a v0 module is asking this root for a name that is not bound yet
            return
        _v0_loading = True
        try:
            for module_name, names in _V0_SOURCES:
                module = importlib.import_module(module_name)
                for name in names:
                    globals()[name] = getattr(module, name)
            _v0_loaded = True
        finally:
            _v0_loading = False


def __getattr__(name: str) -> Any:  # PEP 562: only for names that are not bound yet
    if name in _V0_NAMES:
        _load_v0()
        try:
            return globals()[name]
        except KeyError:
            pass
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


def __dir__() -> List[str]:
    return sorted(set(globals()) | set(_V0_NAMES))


__all__ = ('__version__', 'otel', 'OtelWrapperWarning') + _V0_NAMES
