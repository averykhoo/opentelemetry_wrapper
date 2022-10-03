from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import Span
from starlette.datastructures import Headers
from starlette.types import Scope

from opentelemetry_wrapper.instrument_decorator import instrument_decorate

try:
    from fastapi import FastAPI
except ImportError:
    from typing import Any as FastAPI

_HEADER_ATTRIBUTES = (
    # 'user-agent',
    # 'cookie',

    # headers set in cookiecutter's OPA file
    'x-pf-number',
    'x-client-id',
    'x-preferred-username',
    # 'x-full-name',
    # 'x-given-name',
    # 'x-family-name',
    'x-resource-access',
    # 'x-realm-roles',
    # 'x-groups',

    # headers set by Kong
    # 'authorization',
    # 'x-userinfo',
    # 'x-request-id',

    #  headers set by K8s
    # 'x-real-ip',
    # 'x-forwarded-for',
    # 'x-original-forwarded-for',
)


def request_hook(span: Span, scope: Scope) -> None:
    """
    add span attributes from headers
    note: RFC 7230 says header keys and values should be ASCII
    """
    headers = dict(Headers(scope=scope))  # keys are lowercase latin-1 (ascii)
    for header_name in _HEADER_ATTRIBUTES:
        header_value = headers.get(header_name.lower())
        if isinstance(header_value, (bool, str, bytes, int, float)):
            span.set_attribute(header_name, header_value)


@instrument_decorate
def instrument_fastapi_app(app: FastAPI) -> FastAPI:
    """
    instrument a FastAPI app
    also instruments logging and requests (if requests exists)
    this function is idempotent; calling it multiple times has no additional side effects
    """

    if not getattr(app, '_is_instrumented_by_opentelemetry', None):
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
    _instrumentor = FastAPIInstrumentor()
    if not _instrumentor.is_instrumented_by_opentelemetry:
        _instrumentor.instrument(server_request_hook=request_hook,
                                 client_request_hook=request_hook,
                                 )
