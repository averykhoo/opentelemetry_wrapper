from opentelemetry.instrumentation.requests import RequestsInstrumentor

from opentelemetry_wrapper.config.otel_headers import OTEL_WRAPPER_DISABLED
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_decorator import instrument_decorate


@instrument_decorate
def instrument_requests():
    """
    this function is idempotent; calling it multiple times has no additional side effects

    :return:
    """

    # no-op
    if OTEL_WRAPPER_DISABLED:
        return

    _instrumentor = RequestsInstrumentor()
    if not _instrumentor.is_instrumented_by_opentelemetry:
        _instrumentor.instrument()
