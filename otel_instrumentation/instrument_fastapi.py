from functools import wraps

import fastapi
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

from otel_instrumentation.instrument_decorator import instrument_decorate
from otel_instrumentation.instrument_logging import instrument_logging


@instrument_decorate
def instrument_fastapi_app(app: fastapi.FastAPI) -> fastapi.FastAPI:
    """
    instrument a FastAPI app
    also instruments logging and requests (if requests exists)
    this function is idempotent; calling it multiple times has no additional side effects
    """
    # first instrument logging, if not already instrumented
    instrument_logging(force_reinstrumentation=False)

    # instrument the app
    if not getattr(app, '_is_instrumented_by_opentelemetry', None):
        FastAPIInstrumentor.instrument_app(app)

    # instrument requests as well
    if not RequestsInstrumentor().is_instrumented_by_opentelemetry:
        RequestsInstrumentor().instrument()

    # return app
    return app


_WRAPPED = None


@instrument_decorate
def instrument_fastapi():
    """
    this function is idempotent; calling it multiple times has no additional side effects

    :return:
    """
    global _WRAPPED
    if _WRAPPED is None:
        _WRAPPED = fastapi.FastAPI

        @wraps(fastapi.FastAPI)
        def wrapped(*args, **kwargs):
            _app = _WRAPPED(*args, **kwargs)
            return instrument_fastapi_app(_app)

        fastapi.FastAPI = wrapped
