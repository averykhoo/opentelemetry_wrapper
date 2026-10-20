"""
a wrapper around `opentelemetry` and `opentelemetry-instrumentation-*` to make life a bit easier
"""

__version__ = '1.0.0'

from opentelemetry_wrapper._v0_aliases import instrument_all  # noqa: F401
from opentelemetry_wrapper._v0_aliases import instrument_dataclasses  # noqa: F401
from opentelemetry_wrapper._v0_aliases import instrument_decorate  # noqa: F401
from opentelemetry_wrapper._v0_aliases import instrument_fastapi_app  # noqa: F401
from opentelemetry_wrapper._v0_aliases import instrument_logging  # noqa: F401
from opentelemetry_wrapper._v0_aliases import instrument_requests  # noqa: F401
from opentelemetry_wrapper._v0_aliases import instrument_sqlalchemy  # noqa: F401
from opentelemetry_wrapper._v0_aliases import instrument_sqlalchemy_engine  # noqa: F401
from opentelemetry_wrapper._v0_aliases import instrument_system_metrics  # noqa: F401
from opentelemetry_wrapper.v1 import OtelWrapperWarning  # noqa: F401
from opentelemetry_wrapper.v1 import otel  # noqa: F401

# the root is v1 (DEC-46). v0 was deleted at 1.0.0 (DEC-96); its functions above are warn-once aliases onto v1 until
# 2.0. v0's configuration values (the `OTEL_*` names it read from the environment at import) are gone: v1 reads the
# environment itself, and warns about the variables it renamed (DEC-52). `root.OTEL_X` gets the pointer below; `from
# opentelemetry_wrapper import OTEL_X` gets Python's plain ImportError (it drops the AttributeError's text)
_REMOVED_V0_VALUES = (
    'OTEL_EXPORTER_OTLP_ENDPOINT', 'OTEL_EXPORTER_OTLP_HEADER', 'OTEL_EXPORTER_OTLP_INSECURE',
    'OTEL_EXPORTER_PROMETHEUS_ENDPOINT', 'OTEL_EXPORTER_PROMETHEUS_PORT', 'OTEL_HEADER_ATTRIBUTES', 'OTEL_LOG_LEVEL',
    'OTEL_SERVICE_NAME', 'OTEL_SERVICE_NAMESPACE', 'OTEL_WRAPPER_DISABLED')


def __getattr__(name: str) -> object:  # PEP 562: only for names that are not bound
    if name in _REMOVED_V0_VALUES:
        raise AttributeError(f'opentelemetry_wrapper.{name} (a v0 configuration value) was removed in 1.0.0: read '
                             f'os.environ[{name!r}] instead; the wrapper reads its environment variables itself')
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


__all__ = ('__version__', 'otel', 'OtelWrapperWarning',
           'instrument_all', 'instrument_dataclasses', 'instrument_decorate', 'instrument_fastapi_app',
           'instrument_logging', 'instrument_requests', 'instrument_sqlalchemy', 'instrument_sqlalchemy_engine',
           'instrument_system_metrics')
