import json
import logging
from functools import lru_cache
from typing import List
from typing import Optional
from typing import Set

from opentelemetry import metrics
from opentelemetry import trace
# noinspection PyProtectedMember
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
# noinspection PyProtectedMember
from opentelemetry.sdk._logs import LoggerProvider
# noinspection PyProtectedMember
from opentelemetry.sdk._logs import LoggingHandler
# noinspection PyProtectedMember
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
# noinspection PyProtectedMember
from opentelemetry.sdk.metrics._internal.export import ConsoleMetricExporter
# noinspection PyProtectedMember
from opentelemetry.sdk.metrics._internal.export import MetricReader
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.resources import SERVICE_NAME
from opentelemetry.sdk.resources import SERVICE_NAMESPACE
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.export import ConsoleSpanExporter
from prometheus_client import start_http_server

from opentelemetry_wrapper.config.otel_headers import OTEL_EXPORTER_OTLP_ENDPOINT
from opentelemetry_wrapper.config.otel_headers import OTEL_EXPORTER_OTLP_HEADER
from opentelemetry_wrapper.config.otel_headers import OTEL_EXPORTER_OTLP_INSECURE
from opentelemetry_wrapper.config.otel_headers import OTEL_EXPORTER_PROMETHEUS_PORT
from opentelemetry_wrapper.config.otel_headers import OTEL_LOG_LEVEL
from opentelemetry_wrapper.config.otel_headers import OTEL_SERVICE_NAME
from opentelemetry_wrapper.config.otel_headers import OTEL_SERVICE_NAMESPACE


@lru_cache  # only run once
def get_otel_resource():
    if OTEL_SERVICE_NAMESPACE:
        return Resource.create({SERVICE_NAME:      OTEL_SERVICE_NAME,
                                SERVICE_NAMESPACE: OTEL_SERVICE_NAMESPACE})
    else:
        return Resource.create({SERVICE_NAME: OTEL_SERVICE_NAME})


@lru_cache  # only run once
def init_tracer_provider():
    # based on https://opentelemetry.io/docs/languages/python/exporters/#usage
    tp = TracerProvider(resource=get_otel_resource())

    # noinspection PyProtectedMember
    trace._set_tracer_provider(tp, log=False)  # try to set, but don't warn otherwise
    if trace.get_tracer_provider() is tp:  # if we succeeded in setting it, set it up
        def format_span(span: ReadableSpan) -> str:
            # noinspection PyTypeChecker
            span_json_str = span.to_json(indent=None)

            # add duration in seconds
            if span.start_time and span.end_time:
                span_json_obj = json.loads(span_json_str)
                span_json_obj['duration_ns'] = span.end_time - span.start_time
                span_json_str = json.dumps(span_json_obj, indent=None)

            return f'{span_json_str}\n'

        tp.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter(formatter=format_span)))

        if OTEL_EXPORTER_OTLP_ENDPOINT:
            tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=OTEL_EXPORTER_OTLP_ENDPOINT,
                                                                      headers=OTEL_EXPORTER_OTLP_HEADER,
                                                                      insecure=OTEL_EXPORTER_OTLP_INSECURE)))


def get_tracer(instrumenting_module_name: str,
               instrumenting_library_version: Optional[str] = None,
               ) -> trace.Tracer:
    init_tracer_provider()
    return trace.get_tracer(instrumenting_module_name=instrumenting_module_name,
                            instrumenting_library_version=instrumenting_library_version)


@lru_cache  # only run once
def init_meter_provider(*, print_to_console: bool = False):
    """

    :param print_to_console: WARNING THIS IS A BAD IDEA USE ONLY FOR DEBUGGING
    :return:
    """
    # based on https://opentelemetry.io/docs/languages/python/exporters/#usage

    metric_readers: List[MetricReader] = []
    if print_to_console:
        metric_readers.append(PeriodicExportingMetricReader(ConsoleMetricExporter()))

    if OTEL_EXPORTER_OTLP_ENDPOINT:
        metric_readers.append(PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=OTEL_EXPORTER_OTLP_ENDPOINT,
                                                                               headers=OTEL_EXPORTER_OTLP_HEADER,
                                                                               insecure=OTEL_EXPORTER_OTLP_INSECURE)))

    # https://opentelemetry.io/docs/languages/python/exporters/#prometheus-dependencies
    if OTEL_EXPORTER_PROMETHEUS_PORT is not None:
        # noinspection PyBroadException
        try:
            start_http_server(port=OTEL_EXPORTER_PROMETHEUS_PORT, addr="localhost")
        except Exception:
            logging.exception(f'failed to start prometheus server at port {OTEL_EXPORTER_PROMETHEUS_PORT}')

    # always include prometheus metric reader since we might use the endpoint instead of the port
    metric_readers.append(PrometheusMetricReader())
    mp = MeterProvider(resource=get_otel_resource(), metric_readers=metric_readers)

    # metrics.set_meter_provider(provider)
    # noinspection PyUnresolvedReferences,PyProtectedMember
    metrics._internal._set_meter_provider(mp, log=False)  # try to set, but don't warn otherwise


# write IDs as 0xBEEF instead of BEEF, so it matches the trace json exactly
LOGGING_FORMAT_VERBOSE = (
    '%(asctime)s '
    '%(levelname)-8s '
    '[%(name)s] '
    '[%(filename)s:%(funcName)s:%(lineno)d] '
    '[trace_id=0x%(otelTraceID)s span_id=0x%(otelSpanID)s resource.service.name=%(otelServiceName)s] '
    '- %(message)s'
)

_OUR_ROOT_HANDLERS: Set[logging.Handler] = set()


@lru_cache  # only run once
def get_otel_log_handler(*,
                         level: int = OTEL_LOG_LEVEL,
                         ) -> LoggingHandler:
    # based on https://github.com/mhausenblas/ref.otel.help/blob/main/how-to/logs-collection/yoda/main.py
    lp = LoggerProvider(resource=get_otel_resource())
    if OTEL_EXPORTER_OTLP_ENDPOINT:
        lp.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter(endpoint=OTEL_EXPORTER_OTLP_ENDPOINT,
                                                                            headers=OTEL_EXPORTER_OTLP_HEADER,
                                                                            insecure=OTEL_EXPORTER_OTLP_INSECURE)))
    return LoggingHandler(level=level, logger_provider=lp)
