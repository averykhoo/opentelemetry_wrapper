import json
from functools import lru_cache
from typing import Optional

from opentelemetry import metrics
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.resources import SERVICE_NAME
from opentelemetry.sdk.resources import SERVICE_NAMESPACE
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.export import ConsoleSpanExporter

from opentelemetry_wrapper.config.otel_headers import OTEL_EXPORTER_OTLP_ENDPOINT
from opentelemetry_wrapper.config.otel_headers import OTEL_EXPORTER_OTLP_HEADER
from opentelemetry_wrapper.config.otel_headers import OTEL_EXPORTER_OTLP_INSECURE
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
def init_meter_provider():
    # based on https://opentelemetry.io/docs/languages/python/exporters/#usage

    if OTEL_EXPORTER_OTLP_ENDPOINT:
        reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=OTEL_EXPORTER_OTLP_ENDPOINT,
                                                                  headers=OTEL_EXPORTER_OTLP_HEADER,
                                                                  insecure=OTEL_EXPORTER_OTLP_INSECURE))
        mp = MeterProvider(resource=get_otel_resource(),
                           metric_readers=[reader])

        # noinspection PyUnresolvedReferences,PyProtectedMember
        metrics._set_meter_provider(mp, log=False)  # try to set, but don't warn otherwise
