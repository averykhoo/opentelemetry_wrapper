import logging

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from opentelemetry_wrapper.config.otel_headers import OTEL_EXPORTER_PROMETHEUS_ENDPOINT
from opentelemetry_wrapper.config.otel_headers import OTEL_WRAPPER_DISABLED
from opentelemetry_wrapper.dependencies.fastapi.fastapi_prometheus import mount_prometheus
from opentelemetry_wrapper.dependencies.fastapi.fastapi_typedef import is_fastapi_app
from opentelemetry_wrapper.dependencies.fastapi.starlette_request_hook import request_hook
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_decorator import instrument_decorate
from opentelemetry_wrapper.dependencies.opentelemetry.otel_providers import init_meter_provider


@instrument_decorate
def instrument_fastapi_app(app):
    """
    instrument a FastAPI app
    also instruments logging and requests (if `requests` exists)
    this function is idempotent; calling it multiple times has no additional side effects
    """

    # no-op
    if OTEL_WRAPPER_DISABLED:
        return app

    # ensure it's an actual app
    if not is_fastapi_app(app):
        return app

    # note: this needs to be done before checking for double-instrumentation
    # the check below sometimes prevents prometheus from being added
    if OTEL_EXPORTER_PROMETHEUS_ENDPOINT:
        # noinspection PyBroadException
        try:
            mount_prometheus(app)
        except Exception:
            logging.exception(f'failed to mount prometheus endpoint: {OTEL_EXPORTER_PROMETHEUS_ENDPOINT}')

    # avoid double instrumentation
    if getattr(app, '_is_instrumented_by_opentelemetry', None):
        return app

    # init metrics
    init_meter_provider()

    # exclude prometheus endpoint
    exclude_url = OTEL_EXPORTER_PROMETHEUS_ENDPOINT.rstrip('/') if OTEL_EXPORTER_PROMETHEUS_ENDPOINT else None

    # instrument the app
    FastAPIInstrumentor.instrument_app(app,
                                       server_request_hook=request_hook,
                                       client_request_hook=request_hook,
                                       excluded_urls=exclude_url,
                                       )
    return app
