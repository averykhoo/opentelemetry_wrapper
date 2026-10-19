"""
the scrubbing exporter wrappers, fail-closed behaviour and the module-level helpers (OTW-8; AC-13, AC-15 via
`scrub_argv`). the rule examples themselves are in test_scrubbing_rules.py. every secret here is obviously fake
"""
import json
import logging
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from opentelemetry._logs import LogRecord
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter, SimpleLogRecordProcessor
from opentelemetry.sdk.trace import ReadableSpan, SpanLimits, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Link

from opentelemetry_wrapper.v1 import scrubbing
from opentelemetry_wrapper.v1.scrubbing import (FAILED, NOTES_ATTRIBUTE, REDACTED, Scrubber, ScrubbingLogExporter,
                                                ScrubbingSpanExporter, scrub_argv, scrub_mapping, scrub_text)

REPO_ROOT = Path(__file__).resolve().parents[2]
JWT = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc123'
SECRETS = ('hunter2', JWT, 's3cret')


@pytest.fixture(autouse=True)
def _fresh_reporting(monkeypatch):
    monkeypatch.setattr(scrubbing, '_reported', set())
    monkeypatch.delenv(scrubbing.DEBUG_ENV, raising=False)


def _tracer(exporter, processor=SimpleSpanProcessor, **provider_kw):
    provider = TracerProvider(**provider_kw)
    provider.add_span_processor(processor(exporter))
    return provider, provider.get_tracer('test')


def _failing_scrubber(trigger='boom'):
    """a scrubber whose value matcher raises on any text containing `trigger`"""
    s = Scrubber()
    real = s._m.sub

    def sub(text):
        if trigger in text:
            raise ZeroDivisionError('never shown')
        return real(text)

    s._m.sub = sub
    return s


# ----------------------------------------------------------------------------------------------- spans
@pytest.mark.criterion('AC-13')
def test_span_attributes_events_and_links_are_scrubbed_into_the_in_memory_exporter():
    memory = InMemorySpanExporter()
    provider, tracer = _tracer(ScrubbingSpanExporter(memory))
    with tracer.start_as_current_span('linked') as other:
        pass
    link = Link(other.get_span_context(), {'client_secret': 's3cret', 'ok': 'fine'})
    with tracer.start_as_current_span('s', links=[link]) as span:
        span.set_attribute('db.password', 'hunter2')
        span.set_attribute('db.url', 'postgresql://app:hunter2@db/x')
        span.set_attribute('http.method', 'GET')
        span.add_event('e', {'log.message': f'Bearer {JWT}', 'n': 1})
    provider.shutdown()
    got = memory.get_finished_spans()[-1]
    assert got.attributes['db.password'] == REDACTED
    assert got.attributes['db.url'] == f'postgresql://app:{REDACTED}@db/x'
    assert got.attributes['http.method'] == 'GET'
    assert got.events[0].attributes == {'log.message': f'Bearer {REDACTED}', 'n': 1}
    assert dict(got.links[0].attributes) == {'client_secret': REDACTED, 'ok': 'fine'}
    assert got.links[0].context == other.get_span_context()
    assert got.attributes[NOTES_ATTRIBUTE] == (
        'db.password:key.password', 'db.url:value.url_userinfo', 'events[0].log.message:value.bearer',
        'links[0].client_secret:key.secret')
    assert got.name == 's' and got.context == span.get_span_context() and got.end_time == span.end_time
    dumped = got.to_json()
    assert not any(secret in dumped for secret in SECRETS)


def test_a_clean_span_is_passed_through_as_the_same_object():
    memory = InMemorySpanExporter()
    span = ReadableSpan('clean', attributes={'http.method': 'GET'})
    ScrubbingSpanExporter(memory).export([span])
    assert memory.get_finished_spans()[0] is span


def test_dropped_counts_survive_scrubbing():
    memory = InMemorySpanExporter()
    provider, tracer = _tracer(ScrubbingSpanExporter(memory), span_limits=SpanLimits(max_attributes=2, max_events=1))
    with tracer.start_as_current_span('s') as span:
        span.set_attributes({'a': 1, 'b': 2, 'password': 'hunter2'})  # the oldest is evicted
        span.add_event('one', {'token': 'x'})
        span.add_event('two')
    provider.shutdown()
    got = memory.get_finished_spans()[0]
    assert got.dropped_attributes == span.dropped_attributes == 1
    assert got.dropped_events == span.dropped_events == 1
    assert got.attributes['password'] == REDACTED and 'hunter2' not in got.to_json()


def test_scrubbing_runs_on_the_exporter_thread_not_the_callers():
    seen = []

    class Recording(Scrubber):
        def scrub_attributes(self, attrs, path=''):
            seen.append(threading.get_ident())
            return super().scrub_attributes(attrs, path)

    memory = InMemorySpanExporter()
    provider, tracer = _tracer(ScrubbingSpanExporter(memory, Recording()), processor=BatchSpanProcessor)
    with tracer.start_as_current_span('s') as span:
        span.set_attribute('password', 'hunter2')
    provider.shutdown()
    assert seen and threading.get_ident() not in seen
    assert memory.get_finished_spans()[0].attributes['password'] == REDACTED


def test_the_wrapper_delegates_to_the_inner_exporter():
    memory = InMemorySpanExporter()
    wrapper = ScrubbingSpanExporter(memory)
    assert wrapper.get_finished_spans() == () and wrapper.inner is memory
    assert wrapper.force_flush() is True
    wrapper.shutdown()
    assert memory._stopped


# ----------------------------------------------------------------------------------------------- logs
def _logger(exporter):
    provider = LoggerProvider()
    provider.add_log_record_processor(SimpleLogRecordProcessor(exporter))
    return provider, provider.get_logger('test')


@pytest.mark.criterion('AC-13')
def test_log_attributes_and_body_are_scrubbed():
    memory = InMemoryLogRecordExporter()
    provider, logger = _logger(ScrubbingLogExporter(memory))
    logger.emit(LogRecord(body='connecting with password=hunter2', attributes={'api_key': 'abc', 'user': 'bob'}))
    logger.emit(LogRecord(body={'msg': 'ok', 'auth': {'authorization': 'Basic dXNlcjpwYXNz'}}))
    logger.emit(LogRecord(body='nothing to see', attributes={'user': 'bob'}))
    provider.shutdown()
    first, second, third = (r.log_record for r in memory.get_finished_logs())
    assert first.body == f'connecting with password={REDACTED}'
    assert first.attributes['api_key'] == REDACTED and first.attributes['user'] == 'bob'
    assert first.attributes[NOTES_ATTRIBUTE] == ('api_key:key.key', 'body:value.inline_kv')
    assert second.body == {'msg': 'ok', 'auth': {'authorization': REDACTED}}
    assert second.attributes[NOTES_ATTRIBUTE] == ('body.auth.authorization:key.authorization',)
    assert third.body == 'nothing to see' and NOTES_ATTRIBUTE not in third.attributes


@pytest.mark.filterwarnings('ignore::DeprecationWarning')
@pytest.mark.criterion('AC-13')
def test_stdlib_logging_through_the_otel_handler_is_scrubbed():
    from opentelemetry.sdk._logs import LoggingHandler
    memory = InMemoryLogRecordExporter()
    provider, _ = _logger(ScrubbingLogExporter(memory))
    log = logging.getLogger('otw8.test')
    handler = LoggingHandler(logger_provider=provider)
    log.addHandler(handler)
    try:
        log.warning('retry with api_key=abc123', extra={'db.password': 'hunter2'})
    finally:
        log.removeHandler(handler)
    provider.shutdown()
    rec = memory.get_finished_logs()[0].log_record
    assert rec.body == f'retry with api_key={REDACTED}' and rec.attributes['db.password'] == REDACTED


# ----------------------------------------------------------------------------------------------- fail closed
@pytest.mark.criterion('AC-13')
def test_a_value_that_fails_to_scrub_is_dropped_with_its_own_placeholder_and_the_rest_exported(capsys):
    memory = InMemorySpanExporter()
    provider, tracer = _tracer(ScrubbingSpanExporter(memory, _failing_scrubber()))
    for _ in range(2):
        with tracer.start_as_current_span('s') as span:
            span.set_attributes({'a': 'boom hunter2', 'password': 'x', 'b': 'fine'})
            span.add_event('e', {'m': 'boom hunter2', 'k': 'fine'})
    provider.shutdown()
    for got in memory.get_finished_spans():
        assert got.attributes['a'] == FAILED != REDACTED
        assert got.attributes['password'] == REDACTED and got.attributes['b'] == 'fine'
        assert got.events[0].attributes == {'m': FAILED, 'k': 'fine'}
        assert got.attributes[NOTES_ATTRIBUTE] == ('a:error.ZeroDivisionError', 'password:key.password',
                                                   'events[0].m:error.ZeroDivisionError')
    err = capsys.readouterr().err
    lines = err.splitlines()
    assert len(lines) == 1, 'once per failure site'
    report = json.loads(lines[0])
    assert report['error'] == 'ZeroDivisionError' and 'traceback' not in report
    assert 'hunter2' not in err and 'boom' not in err and 'never shown' not in err


def test_debug_variable_reports_every_failure_with_its_traceback(capsys, monkeypatch):
    monkeypatch.setenv(scrubbing.DEBUG_ENV, '1')
    s = _failing_scrubber()
    s.scrub_attributes({'a': 'boom'})
    s.scrub_attributes({'a': 'boom'})
    lines = capsys.readouterr().err.splitlines()
    assert len(lines) == 2 and all('ZeroDivisionError' in json.loads(x)['traceback'] for x in lines)


@pytest.mark.criterion('AC-13')
def test_log_body_and_argv_fail_closed(capsys):
    s = _failing_scrubber()
    memory = InMemoryLogRecordExporter()
    provider, logger = _logger(ScrubbingLogExporter(memory, s))
    logger.emit(LogRecord(body='boom', attributes={'user': 'bob', 'a': 'boom'}))
    provider.shutdown()
    rec = memory.get_finished_logs()[0].log_record
    assert rec.body == FAILED and rec.attributes['user'] == 'bob' and rec.attributes['a'] == FAILED
    assert rec.attributes[NOTES_ATTRIBUTE] == ('a:error.ZeroDivisionError', 'body:error.ZeroDivisionError')
    assert s.scrub_argv(['prog', 'boom', 'ok']) == (['prog', FAILED, 'ok'], ['argv[1]:error.ZeroDivisionError'])
    assert s.scrub_text('boom') == (FAILED, ['body:error.ZeroDivisionError'])


def test_a_record_whose_scrubbing_breaks_is_exported_bare_with_a_note(capsys):
    class Broken(Scrubber):
        def scrub_attributes(self, attrs, path=''):
            raise RuntimeError('structural')

    spans, logs = InMemorySpanExporter(), InMemoryLogRecordExporter()
    secret = ReadableSpan('secret', attributes={'password': 'hunter2'}, events=[])
    ScrubbingSpanExporter(spans, Broken()).export([secret])
    got = spans.get_finished_spans()[0]
    assert got.name == 'secret' and dict(got.attributes) == {NOTES_ATTRIBUTE: ('*:error.RuntimeError',)}
    provider, logger = _logger(ScrubbingLogExporter(logs, Broken()))
    logger.emit(LogRecord(body='password=hunter2', attributes={'password': 'hunter2'}))
    provider.shutdown()
    rec = logs.get_finished_logs()[0].log_record
    assert rec.body == FAILED and dict(rec.attributes) == {NOTES_ATTRIBUTE: ('*:error.RuntimeError',)}
    assert 'hunter2' not in capsys.readouterr().err


def test_a_span_that_cannot_be_rebuilt_is_dropped_not_exported_unscrubbed(monkeypatch, capsys):
    memory = InMemorySpanExporter()
    exporter = ScrubbingSpanExporter(memory)

    def broken(*args, **kwargs):
        raise RuntimeError('rebuild failed')

    secret = ReadableSpan('secret', attributes={'password': 'hunter2'})
    clean = ReadableSpan('clean', attributes={'n': 1})
    monkeypatch.setattr(scrubbing, 'ReadableSpan', broken)
    exporter.export([secret, clean])
    assert memory.get_finished_spans() == (clean,)
    sites = [json.loads(x)['site'] for x in capsys.readouterr().err.splitlines()]
    assert sites == ['ScrubbingSpanExporter.export', 'ScrubbingSpanExporter.export.fallback']


# ----------------------------------------------------------------------------------------------- helpers
@pytest.mark.criterion('AC-15')
def test_scrub_argv_covers_ac15():
    argv = ['app', '--db-password=hunter2', '--token', 's3cret', '--db-url', 'postgresql://u:hunter2@h/db',
            '-p', 'keep', '--verbose']
    assert scrub_argv(argv) == ['app', f'--db-password={REDACTED}', '--token', REDACTED, '--db-url',
                                f'postgresql://u:{REDACTED}@h/db', '-p', 'keep', '--verbose']
    assert scrub_argv(('python', '-m', 'app')) == ['python', '-m', 'app']


@pytest.mark.criterion('AC-13')
def test_scrub_mapping_for_the_stderr_json_logs():
    line = {'message': 'login with password=hunter2', 'level': 'INFO', 'extra': {'token': 's3cret', 'n': 1},
            'otelTraceID': '4bf92f3577b34da6a3ce929d0e0e4736'}
    assert scrub_mapping(line) == {'message': f'login with password={REDACTED}', 'level': 'INFO',
                                   'extra': {'token': REDACTED, 'n': 1},
                                   'otelTraceID': '4bf92f3577b34da6a3ce929d0e0e4736'}
    clean = {'message': 'hello'}
    assert scrub_mapping(clean) is clean
    assert scrub_text(f'Traceback ...\nValueError: Bearer {JWT}') == f'Traceback ...\nValueError: Bearer {REDACTED}'


@pytest.mark.criterion('AC-13')
def test_the_exporters_use_the_shared_default_scrubber(monkeypatch):
    custom = Scrubber(allow_keys=['password'])
    monkeypatch.setattr(scrubbing, '_default', custom)
    memory = InMemorySpanExporter()
    ScrubbingSpanExporter(memory).export([ReadableSpan('s', attributes={'password': 'kept'})])
    assert memory.get_finished_spans()[0].attributes['password'] == 'kept'
    assert scrubbing.default_scrubber() is custom


def test_the_notes_attribute_lists_each_redaction_once():
    memory = InMemorySpanExporter()
    ScrubbingSpanExporter(memory).export([ReadableSpan('s', attributes={'m': f'Bearer {JWT} and Bearer {JWT}'})])
    got = memory.get_finished_spans()[0]
    assert got.attributes['m'] == f'Bearer {REDACTED} and Bearer {REDACTED}'
    assert got.attributes[NOTES_ATTRIBUTE] == ('m:value.bearer',)


def test_unknown_engine_name_is_rejected():
    with pytest.raises(ValueError):
        Scrubber(engine='re3')


def test_the_default_path_never_imports_hyperscan():
    code = ('import sys; from opentelemetry_wrapper.v1 import scrubbing as s; '
            "s.scrub_text('password=x ' * 20); s.scrub_argv(['--token', 'x']); s.scrub_mapping({'a': 'b'}); "
            "s.ScrubbingSpanExporter(None); s.ScrubbingLogExporter(None); assert 'hyperscan' not in sys.modules")
    subprocess.run([sys.executable, '-c', code], cwd=REPO_ROOT, check=True)
