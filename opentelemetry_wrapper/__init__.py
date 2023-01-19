"""
a wrapper around `opentelemetry` and `opentelemetry-instrumentation-*` to make life a bit easier
"""

__version__ = '0.0.22'

from opentelemetry_wrapper.config.otel_headers import OTEL_WRAPPER_DISABLED
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_dataclasses import instrument_dataclasses
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_decorator import instrument_decorate
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_fastapi import instrument_fastapi
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_fastapi import instrument_fastapi_app
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_logging import instrument_logging
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_requests import instrument_requests
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_sqlalchemy import instrument_sqlalchemy


@instrument_decorate
def instrument_all():
    # no-op
    if OTEL_WRAPPER_DISABLED:
        return

    # todo: accept kwargs to disable/enable some of these
    instrument_dataclasses()
    instrument_logging()
    instrument_fastapi()
    instrument_requests()
    # instrument_sqlalchemy()


__all__ = (
    '__version__',
    'instrument_all',
    'instrument_decorate',
    'instrument_dataclasses',
    'instrument_logging',
    'instrument_fastapi',
    'instrument_fastapi_app',
    'instrument_requests',
    'instrument_sqlalchemy',
)
