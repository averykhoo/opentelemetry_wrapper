"""
helpers imported by the scenario scripts that `_harness.py` runs in a fresh interpreter

keep this free of pytest imports: it runs in the child process, which only has the repo root on `sys.path`
"""
import json

RESULT_MARKER = '@@RESULT@@ '

# spans that v0's own entry points emit for themselves (they are all `@instrument_decorate`d), e.g.
# `<opentelemetry_wrapper.v0.dependencies.opentelemetry.instrument_logging>.instrument_logging`
LIBRARY_SPAN_PREFIX = '<opentelemetry_wrapper.'


def emit(key, value):
    """report a value back to the test (printed to stdout with a marker, so other stdout noise is ignored)"""
    print(RESULT_MARKER + json.dumps({'key': key, 'value': value}, default=repr), flush=True)


def setup_spans():
    """
    capture finished spans in memory, using whatever global tracer provider the library under test set up
    v0 installs its own `TracerProvider` the first time anything asks for a tracer
    """
    from opentelemetry import trace
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    from opentelemetry_wrapper.v0.dependencies.opentelemetry.otel_providers import init_tracer_provider

    init_tracer_provider()
    exporter = InMemorySpanExporter()
    trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(exporter))
    return exporter


def span_record(span, names_by_id):
    return {
        'name':       span.name,
        'status':     span.status.status_code.name,
        'kind':       span.kind.name,
        'parent':     names_by_id.get(span.parent.span_id) if span.parent else None,
        'trace_id':   f'0x{span.context.trace_id:032x}',
        'span_id':    f'0x{span.context.span_id:016x}',
        'attributes': dict(span.attributes or {}),
        'events':     [event.name for event in span.events],
    }


def take(exporter, *, include_library_spans=False):
    """return (and clear) finished spans as json-able dicts, oldest first"""
    spans = sorted(exporter.get_finished_spans(), key=lambda s: s.start_time)
    exporter.clear()
    names_by_id = {s.context.span_id: s.name for s in spans}
    out = [span_record(s, names_by_id) for s in spans]
    if not include_library_spans:
        out = [s for s in out if not s['name'].startswith(LIBRARY_SPAN_PREFIX)]
    return out


def names(exporter, **kwargs):
    return [s['name'] for s in take(exporter, **kwargs)]

