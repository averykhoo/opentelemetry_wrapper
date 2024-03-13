from typing import TypeVar

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from opentelemetry_wrapper.config.otel_headers import OTEL_WRAPPER_DISABLED
from opentelemetry_wrapper.dependencies.fastapi.fastapi_typedef import is_fastapi_app
from opentelemetry_wrapper.dependencies.fastapi.starlette_request_hook import request_hook
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_decorator import instrument_decorate
from opentelemetry_wrapper.dependencies.opentelemetry.otel_providers import init_meter_provider

FastApiType = TypeVar('FastApiType', bound=type)


@instrument_decorate
def instrument_fastapi_app(app):
    """
    instrument a FastAPI app
    also instruments logging and requests (if `requests` exists)
    this function is idempotent; calling it multiple times has no additional side effects
    """

    # no-op
    if OTEL_WRAPPER_DISABLED:
        return app

    # ensure it's an actual app
    if not is_fastapi_app(app):
        return app

    # avoid double instrumentation
    if getattr(app, '_is_instrumented_by_opentelemetry', None):
        return app

    # init metrics
    init_meter_provider()

    # instrument the app
    FastAPIInstrumentor.instrument_app(app,
                                       server_request_hook=request_hook,
                                       client_request_hook=request_hook,
                                       )
    return app


@instrument_decorate
def instrument_fastapi() -> None:
    """
    this function is idempotent; calling it multiple times has no additional side effects
    """

    # no-op
    if OTEL_WRAPPER_DISABLED:
        return

    _instrumentor = FastAPIInstrumentor()
    if not _instrumentor.is_instrumented_by_opentelemetry:
        _instrumentor.instrument(server_request_hook=request_hook,
                                 client_request_hook=request_hook,
                                 )
