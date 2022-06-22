from functools import lru_cache
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.resources import SERVICE_NAME
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace import Tracer
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.export import ConsoleSpanExporter

from opentelemetry_wrapper.config import __service_name__


@lru_cache  # only run once
def init_tracer():
    if __service_name__:
        tp = TracerProvider(resource=Resource.create({SERVICE_NAME: __service_name__}))
    else:
        tp = TracerProvider()

    # noinspection PyProtectedMember
    trace._set_tracer_provider(tp, log=False)  # try to set, but don't warn otherwise
    if trace.get_tracer_provider() is tp:  # if we succeeded in setting it, set it up
        def format_span(span: ReadableSpan) -> str:
            return f'{span.to_json(indent=None)}\n'

        tp.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter(formatter=format_span)))


def get_tracer(instrumenting_module_name: str,
               instrumenting_library_version: Optional[str] = None,
               ) -> Tracer:
    init_tracer()
    return trace.get_tracer(instrumenting_module_name=instrumenting_module_name,
                            instrumenting_library_version=instrumenting_library_version)
