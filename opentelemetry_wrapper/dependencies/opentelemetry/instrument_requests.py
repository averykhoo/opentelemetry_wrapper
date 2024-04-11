from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.trace import Span
from requests import PreparedRequest
from requests import Response

from opentelemetry_wrapper.config.otel_headers import OTEL_WRAPPER_DISABLED
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_decorator import instrument_decorate
from opentelemetry_wrapper.dependencies.opentelemetry.otel_providers import init_meter_provider

# TODO: don't hardcode!
_HEADERS = [  # this should all be lowercase!
    'x-kong-proxy-latency',
    'x-kong-upstream-latency',
    'x-envoy-upstream-service-time',
    'x-authz-response-time-seconds',
    'x-process-time-seconds',  # for testing, defined in fastapi_main.py
]


def response_hook(span: Span, _request: PreparedRequest, result: Response) -> None:
    for header_name in _HEADERS:
        if header_name in result.headers:
            span.set_attribute(f'http.response.header.{header_name}', result.headers[header_name])
    # if 0 < result.status_code < 300:
    #     span.set_status(Status(StatusCode.OK))
    # elif result.status_code >= 400:
    #     span.set_status(Status(StatusCode.ERROR))


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
        _instrumentor.instrument(response_hook=response_hook)
