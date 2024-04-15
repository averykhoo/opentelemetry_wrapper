"""
a wrapper around `opentelemetry` and `opentelemetry-instrumentation-*` to make life a bit easier
"""

__version__ = '0.1.11'

import logging as builtins_logging
from multiprocessing import current_process
from threading import current_thread

from opentelemetry_wrapper.config.otel_headers import OTEL_EXPORTER_OTLP_ENDPOINT
from opentelemetry_wrapper.config.otel_headers import OTEL_EXPORTER_OTLP_HEADER
from opentelemetry_wrapper.config.otel_headers import OTEL_EXPORTER_OTLP_INSECURE
from opentelemetry_wrapper.config.otel_headers import OTEL_EXPORTER_PROMETHEUS_ENDPOINT
from opentelemetry_wrapper.config.otel_headers import OTEL_EXPORTER_PROMETHEUS_PORT
from opentelemetry_wrapper.config.otel_headers import OTEL_HEADER_ATTRIBUTES
from opentelemetry_wrapper.config.otel_headers import OTEL_LOG_LEVEL
from opentelemetry_wrapper.config.otel_headers import OTEL_SERVICE_NAME
from opentelemetry_wrapper.config.otel_headers import OTEL_SERVICE_NAMESPACE
from opentelemetry_wrapper.config.otel_headers import OTEL_WRAPPER_DISABLED
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_dataclasses import instrument_dataclasses
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_decorator import instrument_decorate
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_fastapi import instrument_fastapi_app
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_logging import instrument_logging
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_requests import instrument_requests
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_sqlalchemy import instrument_sqlalchemy
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_system_metrics import instrument_system_metrics

_CONFIG_HAS_BEEN_LOGGED = False


@instrument_decorate
def instrument_all(dataclasses: bool = True,
                   logging: bool = True,
                   requests: bool = True,
                   sqlalchemy: bool = False,  # too noisy for a default
                   log_json: bool = True,
                   system_metrics: bool = True
                   ):
    # no-op
    if OTEL_WRAPPER_DISABLED:
        return

    if dataclasses:
        instrument_dataclasses()
    if logging:
        instrument_logging(print_json=log_json)
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
                'OTEL_WRAPPER_DISABLED':             OTEL_WRAPPER_DISABLED,
                'OTEL_SERVICE_NAME':                 OTEL_SERVICE_NAME,
                'OTEL_SERVICE_NAMESPACE':            OTEL_SERVICE_NAMESPACE,
                'OTEL_EXPORTER_OTLP_ENDPOINT':       OTEL_EXPORTER_OTLP_ENDPOINT,
                'OTEL_EXPORTER_OTLP_HEADER':         OTEL_EXPORTER_OTLP_HEADER,
                'OTEL_EXPORTER_OTLP_INSECURE':       OTEL_EXPORTER_OTLP_INSECURE,
                'OTEL_LOG_LEVEL':                    OTEL_LOG_LEVEL,
                'OTEL_HEADER_ATTRIBUTES':            OTEL_HEADER_ATTRIBUTES,
                'OTEL_EXPORTER_PROMETHEUS_PORT':     OTEL_EXPORTER_PROMETHEUS_PORT,
                'OTEL_EXPORTER_PROMETHEUS_ENDPOINT': OTEL_EXPORTER_PROMETHEUS_ENDPOINT,
            })


__all__ = (
    '__version__',
    'instrument_all',
    'instrument_decorate',
    'instrument_dataclasses',
    'instrument_logging',
    'instrument_fastapi_app',
    'instrument_requests',
    'instrument_sqlalchemy',
)
