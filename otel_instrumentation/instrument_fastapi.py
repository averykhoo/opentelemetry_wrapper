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
    """
    # first instrument logging, if not already instrumented
    instrument_logging(force_reinstrumentation=False)

    # instrument the app
    FastAPIInstrumentor.instrument_app(app)

    # instrument requests as well
    if not RequestsInstrumentor().is_instrumented_by_opentelemetry:
        RequestsInstrumentor().instrument()

    # return app
    return app


@instrument_decorate
def instrument_fastapi():
    raise NotImplementedError  # todo
