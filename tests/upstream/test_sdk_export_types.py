"""
canary: what the scrubbing exporter wrappers (workstream 5b, DEC-58) need from the SDK

they sit between the SDK's processors and the real exporters, and hand each exporter a scrubbed copy of every span
and log record. that needs the `ReadableSpan(...)` constructor kwargs (for spans, events and links), the log record
types and their constructor kwargs, and the names in `opentelemetry.sdk._logs`, which is private-named. all built
with explicit providers, so nothing global is touched
"""
import json
import logging

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

# the span kwargs the wrapper passes; every other field must come through unchanged
SPAN_FIELDS = ('name', 'context', 'parent', 'resource', 'attributes', 'events', 'links', 'kind', 'status',
               'start_time', 'end_time', 'instrumentation_scope')
LOG_RECORD_FIELDS = ('timestamp', 'observed_timestamp', 'context', 'trace_id', 'span_id', 'trace_flags',
                     'severity_text', 'severity_number', 'body', 'attributes', 'event_name', 'exception')


def _finished_span():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer('canary', '1.2.3')
    with tracer.start_as_current_span('linked') as linked:
        pass
    with tracer.start_as_current_span('parent'):
        with tracer.start_as_current_span('child', kind=trace.SpanKind.CLIENT,
                                          links=[trace.Link(linked.get_span_context(), {'link.secret': 'x'})],
                                          attributes={'secret': 'hunter2', 'n': 3}) as span:
            span.add_event('event', {'event.secret': 'y'})
            span.set_status(trace.Status(trace.StatusCode.ERROR, 'boom'))
    return next(s for s in exporter.get_finished_spans() if s.name == 'child')


def test_the_sdk_log_names_the_wrappers_use_exist():
    from opentelemetry.sdk._logs import LoggerProvider  # noqa: F401
    from opentelemetry.sdk._logs import LogRecordProcessor  # noqa: F401
    from opentelemetry.sdk._logs import ReadableLogRecord  # noqa: F401
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor  # noqa: F401
    from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter  # noqa: F401
    from opentelemetry.sdk._logs.export import LogRecordExporter  # noqa: F401
    from opentelemetry.sdk._logs.export import LogRecordExportResult  # noqa: F401
    from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor  # noqa: F401


def test_a_span_copied_with_new_attributes_keeps_everything_else():
    from opentelemetry.sdk.trace import Event
    from opentelemetry.sdk.trace import ReadableSpan

    span = _finished_span()
    copy = ReadableSpan(
        **{field: getattr(span, field) for field in SPAN_FIELDS},
    )
    scrubbed = ReadableSpan(**{
        **{field: getattr(span, field) for field in SPAN_FIELDS},
        'attributes': {'secret': '[REDACTED]', 'n': 3},
        'events':     [Event(e.name, {'event.secret': '[REDACTED]'}, e.timestamp) for e in span.events],
        'links':      [trace.Link(link.context, {'link.secret': '[REDACTED]'}) for link in span.links],
    })

    assert json.loads(copy.to_json()) == json.loads(span.to_json())
    expected = json.loads(span.to_json())
    expected['attributes']['secret'] = '[REDACTED]'
    expected['events'][0]['attributes']['event.secret'] = '[REDACTED]'
    expected['links'][0]['attributes']['link.secret'] = '[REDACTED]'
    assert json.loads(scrubbed.to_json()) == expected
    assert scrubbed.instrumentation_scope == span.instrumentation_scope
    assert scrubbed.status.description == 'boom'

    exporter = InMemorySpanExporter()
    exporter.export([scrubbed])
    assert exporter.get_finished_spans() == (scrubbed,)


def test_a_log_record_copied_with_new_body_and_attributes_keeps_everything_else():
    from opentelemetry._logs import LogRecord
    from opentelemetry.instrumentation.logging.handler import LoggingHandler
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk._logs import ReadableLogRecord
    from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter
    from opentelemetry.sdk._logs.export import LogRecordExporter
    from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor

    class Scrubbing(LogRecordExporter):  # the shape of the wrapper: a `LogRecordExporter` around another
        def __init__(self, inner):
            self.inner = inner

        def export(self, batch):
            out = []
            for record in batch:
                assert isinstance(record, ReadableLogRecord)
                fields = {field: getattr(record.log_record, field) for field in LOG_RECORD_FIELDS}
                fields['body'] = '[REDACTED]'
                fields['attributes'] = {**fields['attributes'], 'password': '[REDACTED]'}
                out.append(ReadableLogRecord(LogRecord(**fields), resource=record.resource,
                                             instrumentation_scope=record.instrumentation_scope))
            return self.inner.export(out)

        def force_flush(self, timeout_millis=30000):
            return self.inner.force_flush(timeout_millis)

        def shutdown(self):
            self.inner.shutdown()

    inner = InMemoryLogRecordExporter()
    provider = LoggerProvider()
    provider.add_log_record_processor(SimpleLogRecordProcessor(Scrubbing(inner)))
    logger = logging.getLogger('tests.upstream.canary')
    logger.propagate = False
    handler = LoggingHandler(logger_provider=provider, log_code_attributes=True)
    logger.addHandler(handler)
    try:
        logger.warning('password is %s', 'hunter2', extra={'password': 'hunter2', 'order_id': 7})
    finally:
        logger.removeHandler(handler)

    [record] = inner.get_finished_logs()
    assert record.log_record.body == '[REDACTED]'
    attributes = dict(record.log_record.attributes)
    assert attributes['password'] == '[REDACTED]'
    assert attributes['order_id'] == 7
    assert {'code.file.path', 'code.function.name', 'code.line.number'} <= set(attributes)  # stable semconv keys
    assert record.log_record.severity_text == 'WARN'
    assert record.log_record.timestamp is not None
    assert record.instrumentation_scope.name == 'tests.upstream.canary'
