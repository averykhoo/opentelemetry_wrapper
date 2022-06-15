from opentelemetry.instrumentation.requests import RequestsInstrumentor

from otel_instrumentation.instrument_decorator import instrument_decorate


@instrument_decorate
def instrument_requests():
    """
    this function is idempotent; calling it multiple times has no additional side effects

    :return:
    """
    _instrumentor = RequestsInstrumentor()
    if not _instrumentor.is_instrumented_by_opentelemetry:
        _instrumentor.instrument()
