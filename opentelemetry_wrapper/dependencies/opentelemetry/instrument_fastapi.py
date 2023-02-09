from typing import TypeVar

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.trace import Span
from starlette.datastructures import Headers
from starlette.types import Scope

from opentelemetry_wrapper.config.otel_headers import OTEL_HEADER_ATTRIBUTES
from opentelemetry_wrapper.config.otel_headers import OTEL_WRAPPER_DISABLED
from opentelemetry_wrapper.dependencies.fastapi.fastapi_typedef import is_fastapi_app
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_decorator import instrument_decorate

FastApiType = TypeVar('FastApiType', bound=type)


def request_hook(span: Span, scope: Scope) -> None:
    """
    add span attributes from headers
    note: RFC 7230 says header keys and values should be ASCII
    """
    headers = dict(Headers(scope=scope))  # keys are lowercase latin-1 (ascii)
    for header_name in OTEL_HEADER_ATTRIBUTES:
        header_value = headers.get(header_name.lower())
        if isinstance(header_value, (bool, str, bytes, int, float)):
            span.set_attribute(header_name, header_value)


@instrument_decorate
def instrument_fastapi_app(app):
    """
    instrument a FastAPI app
    also instruments logging and requests (if requests exists)
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
