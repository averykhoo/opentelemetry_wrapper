from functools import lru_cache
from typing import Optional

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.resources import SERVICE_NAME
from opentelemetry.sdk.resources import SERVICE_NAMESPACE
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace import Tracer
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.export import ConsoleSpanExporter

from opentelemetry_wrapper.config.config import OTEL_EXPORTER_OTLP_ENDPOINT
from opentelemetry_wrapper.config.config import OTEL_SERVICE_NAME
from opentelemetry_wrapper.config.config import OTEL_SERVICE_NAMESPACE


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
            return f'{span.to_json(indent=None)}\n'

        tp.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter(formatter=format_span)))

        if OTEL_EXPORTER_OTLP_ENDPOINT:
            tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(OTEL_EXPORTER_OTLP_ENDPOINT)))


def get_tracer(instrumenting_module_name: str,
               instrumenting_library_version: Optional[str] = None,
               ) -> Tracer:
    init_tracer_provider()
    return trace.get_tracer(instrumenting_module_name=instrumenting_module_name,
                            instrumenting_library_version=instrumenting_library_version)
