from opentelemetry.instrumentation.requests import RequestsInstrumentor

from otel_instrumentation.instrument_decorator import instrument_decorate


@instrument_decorate
def instrument_requests(*, force_reinstrumentation: bool = True):
    _instrumentor = RequestsInstrumentor()
    if _instrumentor.is_instrumented_by_opentelemetry:
        if force_reinstrumentation:
            _instrumentor.uninstrument()
        else:
            return
    _instrumentor.instrument()
