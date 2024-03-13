from opentelemetry.instrumentation.requests import RequestsInstrumentor

from opentelemetry_wrapper.config.otel_headers import OTEL_WRAPPER_DISABLED
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_decorator import instrument_decorate
from opentelemetry_wrapper.dependencies.opentelemetry.tracers import init_meter_provider


@instrument_decorate
def instrument_requests():
    """
    this function is idempotent; calling it multiple times has no additional side effects

    :return:
    """

    # no-op
    if OTEL_WRAPPER_DISABLED:
        return

    # init metrics
    init_meter_provider()

    _instrumentor = RequestsInstrumentor()
    if not _instrumentor.is_instrumented_by_opentelemetry:
        _instrumentor.instrument()
