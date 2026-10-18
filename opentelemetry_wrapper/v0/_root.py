"""
what the package root defined itself in v0 (DEC-80): moved here, unchanged, so the root can be v1 and still serve
`opentelemetry_wrapper.instrument_all` (the root's `__getattr__` loads this module on first use of a v0 name)
"""
import logging as builtins_logging
from multiprocessing import current_process
from threading import current_thread

from opentelemetry_wrapper import __version__
from opentelemetry_wrapper.v0.config.otel_headers import OTEL_EXPORTER_OTLP_ENDPOINT
from opentelemetry_wrapper.v0.config.otel_headers import OTEL_EXPORTER_OTLP_HEADER
from opentelemetry_wrapper.v0.config.otel_headers import OTEL_EXPORTER_OTLP_INSECURE
from opentelemetry_wrapper.v0.config.otel_headers import OTEL_EXPORTER_PROMETHEUS_ENDPOINT
from opentelemetry_wrapper.v0.config.otel_headers import OTEL_EXPORTER_PROMETHEUS_PORT
from opentelemetry_wrapper.v0.config.otel_headers import OTEL_HEADER_ATTRIBUTES
from opentelemetry_wrapper.v0.config.otel_headers import OTEL_LOG_LEVEL
from opentelemetry_wrapper.v0.config.otel_headers import OTEL_WRAPPER_DISABLED
from opentelemetry_wrapper.v0.dependencies.opentelemetry.instrument_dataclasses import instrument_dataclasses
from opentelemetry_wrapper.v0.dependencies.opentelemetry.instrument_decorator import instrument_decorate
from opentelemetry_wrapper.v0.dependencies.opentelemetry.instrument_logging import instrument_logging
from opentelemetry_wrapper.v0.dependencies.opentelemetry.instrument_requests import instrument_requests
from opentelemetry_wrapper.v0.dependencies.opentelemetry.instrument_sqlalchemy import instrument_sqlalchemy
from opentelemetry_wrapper.v0.dependencies.opentelemetry.instrument_system_metrics import instrument_system_metrics

_CONFIG_HAS_BEEN_LOGGED = False


def instrument_all(dataclasses: bool = True,
                   logging: bool = True,
                   requests: bool = True,
                   sqlalchemy: bool = False,  # too noisy for a default
                   system_metrics: bool = True,
                   log_json: bool = True,
                   clobber_other_log_handlers: bool = False,
                   ):
    # no-op
    if OTEL_WRAPPER_DISABLED:
        return

    if dataclasses:
        instrument_dataclasses()
    if logging:
        instrument_logging(print_json=log_json, clobber_other_log_handlers=clobber_other_log_handlers)
    if requests:
        instrument_requests()
    if sqlalchemy:
        instrument_sqlalchemy()
    if system_metrics:
        instrument_system_metrics()

    # log current config
    global _CONFIG_HAS_BEEN_LOGGED
    if not _CONFIG_HAS_BEEN_LOGGED:
        _CONFIG_HAS_BEEN_LOGGED = True
        if current_process().name == 'MainProcess' and current_thread().name == 'MainThread':
            logger = builtins_logging.getLogger('opentelemetry_wrapper')
            logger.info({
                'opentelemetry_wrapper.__version__': __version__,
                # 'OTEL_WRAPPER_DISABLED': OTEL_WRAPPER_DISABLED, # must be true
                # 'OTEL_SERVICE_NAME OTEL_SERVICE_NAME, # already logged
                # 'OTEL_SERVICE_NAMESPACE OTEL_SERVICE_NAMESPACE, # already logged
                'OTEL_EXPORTER_OTLP_ENDPOINT':       OTEL_EXPORTER_OTLP_ENDPOINT,
                'OTEL_EXPORTER_OTLP_HEADER':         OTEL_EXPORTER_OTLP_HEADER,
                'OTEL_EXPORTER_OTLP_INSECURE':       OTEL_EXPORTER_OTLP_INSECURE,
                'OTEL_LOG_LEVEL':                    OTEL_LOG_LEVEL,
                'OTEL_HEADER_ATTRIBUTES':            OTEL_HEADER_ATTRIBUTES,
                'OTEL_EXPORTER_PROMETHEUS_PORT':     OTEL_EXPORTER_PROMETHEUS_PORT,
                'OTEL_EXPORTER_PROMETHEUS_ENDPOINT': OTEL_EXPORTER_PROMETHEUS_ENDPOINT,
            })


# the span's `code.namespace` stays what it was when the root defined this function
instrument_all.__module__ = 'opentelemetry_wrapper'
instrument_all = instrument_decorate(instrument_all)  # type: ignore[assignment]
