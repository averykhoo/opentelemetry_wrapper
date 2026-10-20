"""
helpers imported by the scenario scripts that `_harness.py` runs in a fresh interpreter

keep this free of pytest imports: it runs in the child process, which only has the repo root on `sys.path`
"""
import json
import sys

RESULT_MARKER = '@@RESULT@@ '

# spans that the wrapper's own entry points emit for themselves, left out of `take` unless asked for: v0's did, e.g.
# `<opentelemetry_wrapper.(v0 module)>.instrument_logging`; v1's emit none (AC-22)
LIBRARY_SPAN_PREFIX = '<opentelemetry_wrapper.'


def emit(key, value):
    """report a value back to the test (printed to stdout with a marker, so other stdout noise is ignored)"""
    # one write, newline included: `print` writes the text and the newline separately, and a span exporter's thread
    # writing to stdout between the two put its span on the same line as the result
    sys.stdout.write(RESULT_MARKER + json.dumps({'key': key, 'value': value}, default=repr) + '\n')
    sys.stdout.flush()


def setup_spans():
    """capture every span the wrapper finishes, in memory (v1's test sink, OTW-3)"""
    from tests import impl
    return impl.span_exporter()


def setup_global_spans():
    """
    capture finished spans in memory from the global SDK tracer provider, whatever installed it: for code that sets up
    OpenTelemetry without the wrapper, or whose spans the wrapper's test sink does not see
    """
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        raise RuntimeError(f'no SDK tracer provider is installed yet (got {type(provider).__name__})')
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return exporter


def span_record(span, names_by_id):
    return {
        'name':       span.name,
        'status':     span.status.status_code.name,
        'kind':       span.kind.name,
        'scope':      span.instrumentation_scope.name if span.instrumentation_scope else None,
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
