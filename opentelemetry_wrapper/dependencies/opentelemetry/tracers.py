import json
from functools import lru_cache
from typing import Optional

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
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
def init_tracer_provider():
    if OTEL_SERVICE_NAMESPACE:
        tp = TracerProvider(resource=Resource.create({SERVICE_NAME:      OTEL_SERVICE_NAME,
                                                      SERVICE_NAMESPACE: OTEL_SERVICE_NAMESPACE}))
    else:
        tp = TracerProvider(resource=Resource.create({SERVICE_NAME: OTEL_SERVICE_NAME}))

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
