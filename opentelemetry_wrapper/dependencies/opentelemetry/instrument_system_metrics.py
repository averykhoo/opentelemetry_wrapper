from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor

from opentelemetry_wrapper.config.otel_headers import OTEL_WRAPPER_DISABLED
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_decorator import instrument_decorate
from opentelemetry_wrapper.dependencies.opentelemetry.otel_providers import init_meter_provider


@instrument_decorate
def instrument_system_metrics():
    if OTEL_WRAPPER_DISABLED:
        return
    init_meter_provider()
    SystemMetricsInstrumentor().instrument()
