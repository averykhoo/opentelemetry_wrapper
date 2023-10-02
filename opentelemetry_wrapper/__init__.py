"""
a wrapper around `opentelemetry` and `opentelemetry-instrumentation-*` to make life a bit easier
"""

__version__ = '0.1.2'

from opentelemetry_wrapper.config.otel_headers import OTEL_WRAPPER_DISABLED
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_dataclasses import instrument_dataclasses
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_decorator import instrument_decorate
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_fastapi import instrument_fastapi
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_fastapi import instrument_fastapi_app
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_logging import instrument_logging
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_requests import instrument_requests
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_sqlalchemy import instrument_sqlalchemy


@instrument_decorate
def instrument_all(dataclasses: bool = True,
                   logging: bool = True,
                   fastapi: bool = True,
                   requests: bool = True,
                   sqlalchemy: bool = False,  # too noisy for a default
                   log_json: bool = True,
                   ):
    # no-op
    if OTEL_WRAPPER_DISABLED:
        return

    if dataclasses:
        instrument_dataclasses()
    if logging:
        instrument_logging(print_json=log_json)
    if fastapi:
        instrument_fastapi()
    if requests:
        instrument_requests()
    if sqlalchemy:
        instrument_sqlalchemy()


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
