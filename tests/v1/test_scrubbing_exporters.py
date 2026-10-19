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

from opentelemetry_wrapper.v1 import _warnings
from opentelemetry_wrapper.v1 import scrubbing
from opentelemetry_wrapper.v1.scrubbing import (FAILED, NOTES_ATTRIBUTE, REDACTED, Scrubber, ScrubbingLogExporter,
                                                ScrubbingSpanExporter, scrub_argv, scrub_mapping, scrub_text)

REPO_ROOT = Path(__file__).resolve().parents[2]
JWT = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc123'
SECRETS = ('hunter2', JWT, 's3cret')


@pytest.fixture(autouse=True)
def _fresh_reporting(monkeypatch):
    monkeypatch.setattr(_warnings, '_reported', set())
    monkeypatch.delenv(_warnings.DEBUG_ENV_VAR, raising=False)


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
            raise ZeroDivisionError(f'never shown: {text}')  # the value in the message: a reporter must withhold it
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
    assert report['error.type'] == 'builtins.ZeroDivisionError' and 'traceback' not in report
    assert 'hunter2' not in err and 'boom' not in err and 'never shown' not in err


def _scrub_twice_and_read_reports(capsys):
    s = _failing_scrubber()
    s.scrub_attributes({'a': 'boom hunter2'})
    s.scrub_attributes({'a': 'boom hunter2'})
    err = capsys.readouterr().err
    return err, [json.loads(line) for line in err.splitlines()]


@pytest.mark.criterion('AC-13')
@pytest.mark.criterion('AC-22')
def test_a_scrubbing_failure_is_reported_by_the_wrappers_one_reporter_with_the_same_record(capsys):  # OTW-23
    _err, [record] = _scrub_twice_and_read_reports(capsys)
    _warnings.report('elsewhere', ZeroDivisionError('x'))
    [other] = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    # one record shape for every swallowed failure (DEC-75), plus the failed value's shape (DEC-94)
    assert record.keys() == other.keys() | {'value.type', 'value.length', 'value.path'}
    assert record['opentelemetry_wrapper'] == other['opentelemetry_wrapper'] == 'internal error, swallowed'
    assert record['site'] == 'scrubbing.scrub_mapping' and record['error.type'] == 'builtins.ZeroDivisionError'
    assert record['message'] == _warnings.WITHHELD  # it may hold the value that failed to scrub (DEC-74)
    assert (record['value.type'], record['value.length'], record['value.path']) == ('builtins.str', 12, 'a')


@pytest.mark.criterion('AC-22')
@pytest.mark.parametrize('value', ['false', '0', 'FALSE', 'no', 'off', ' ', ''])
def test_debug_variable_off_values_give_once_per_site_and_no_traceback(capsys, monkeypatch, value):  # OTW-23
    monkeypatch.setenv(_warnings.DEBUG_ENV_VAR, value)
    err, records = _scrub_twice_and_read_reports(capsys)
    assert len(records) == 1, err
    assert 'traceback' not in records[0] and 'hint' in records[0]


@pytest.mark.criterion('AC-13')
@pytest.mark.criterion('AC-22')
@pytest.mark.parametrize('value', ['true', '1', 'TRUE', ' True '])
def test_debug_variable_reports_every_failure_with_its_traceback_and_no_message(capsys, monkeypatch, value):
    monkeypatch.setenv(_warnings.DEBUG_ENV_VAR, value)
    err, records = _scrub_twice_and_read_reports(capsys)
    assert len(records) == 2, err
    assert all('ZeroDivisionError' in r['traceback'] and 'in sub' in r['traceback'] for r in records), err
    assert 'hunter2' not in err and 'boom' not in err  # the value, not even in the traceback (only its source line)


@pytest.mark.criterion('AC-22')
@pytest.mark.parametrize('value, on', [('true', True), ('1', True), ('TRUE', True), (' 1 ', True), ('false', False),
                                       ('0', False), ('', False), ('yes', False), ('2', False)])
def test_the_debug_variable_has_one_truthiness_rule(monkeypatch, value, on):  # OTW-23
    monkeypatch.setenv(_warnings.DEBUG_ENV_VAR, value)
    assert _warnings._debug() is on
    assert not hasattr(scrubbing, 'DEBUG_ENV') and not hasattr(scrubbing, 'report_failure')  # no second reader


def _chained_failing_scrubber(trigger='boom'):
    """a scrubber whose value matcher raises on `trigger` with a chain (a context, then a cause), every message the
    value"""
    s = Scrubber()
    real = s._m.sub

    def look_up_the_value(text):
        return {}[f'context message: {text}']

    def parse_the_value(text):
        try:
            look_up_the_value(text)
        except KeyError:
            raise ValueError(f'cause message: {text}')  # chained implicitly, as __context__

    def sub(text):
        if trigger not in text:
            return real(text)
        try:
            parse_the_value(text)
        except ValueError as e:
            raise ZeroDivisionError(f'outer message: {text}') from e

    s._m.sub = sub
    return s


@pytest.mark.criterion('AC-13')
@pytest.mark.criterion('AC-22')
@pytest.mark.parametrize('debug', [False, True])
def test_a_chained_scrubbing_failure_never_writes_a_message_and_debug_keeps_every_stack(capsys, monkeypatch, debug):
    if debug:  # DEC-94: the message is withheld even in debug, but the chained stacks are kept
        monkeypatch.setenv(_warnings.DEBUG_ENV_VAR, 'true')
    memory = InMemorySpanExporter()
    provider, tracer = _tracer(ScrubbingSpanExporter(memory, _chained_failing_scrubber()))
    with tracer.start_as_current_span('s') as span:
        span.set_attributes({'a': 'boom hunter2', 'b': 'fine'})
    provider.shutdown()
    exported = memory.get_finished_spans()[0]
    assert exported.attributes['a'] == FAILED and exported.attributes['b'] == 'fine'
    err = capsys.readouterr().err
    [record] = [json.loads(line) for line in err.splitlines()]
    for text in (err, exported.to_json()):
        assert 'hunter2' not in text and 'boom' not in text
    assert record['message'] == _warnings.WITHHELD
    assert (record['value.type'], record['value.length'], record['value.path']) == ('builtins.str', 12, 'a')
    if not debug:
        assert 'traceback' not in record
        return
    tb = record['traceback']
    assert all(f'in {frame}' in tb for frame in ('look_up_the_value', 'parse_the_value', 'sub')), tb
    assert 'During handling of the above exception' in tb and 'was the direct cause of the following' in tb, tb
    assert tb.index('builtins.KeyError') < tb.index('builtins.ValueError') < tb.index('builtins.ZeroDivisionError')
    for error_type in ('builtins.KeyError', 'builtins.ValueError', 'builtins.ZeroDivisionError'):
        assert f'{error_type}: {_warnings.WITHHELD}\n' in tb, tb
    assert tb.count(_warnings.WITHHELD) == 3, tb


class _Unsized:
    """its str and repr are the secret, and are recorded if anyone calls them"""

    def __init__(self):
        self.calls = []

    def __repr__(self):
        self.calls.append('repr')
        return 'hunter2'

    def __str__(self):
        self.calls.append('str')
        return 'hunter2'


class _LenRaises(_Unsized):
    def __len__(self):
        self.calls.append('len')
        raise RuntimeError('hunter2')


@pytest.mark.criterion('AC-13')
@pytest.mark.criterion('AC-22')
@pytest.mark.parametrize('make, type_name, length', [
    (lambda: 'boom hunter2', 'builtins.str', 12),
    (lambda: b'hunter2', 'builtins.bytes', 7),
    (_Unsized, f'{__name__}._Unsized', None),
    (_LenRaises, f'{__name__}._LenRaises', None),
], ids=['str', 'bytes', 'unsized', 'len-raises'])
def test_a_scrubbing_failure_report_carries_the_values_type_length_and_path(capsys, make, type_name, length):  # DEC-94
    value = make()

    class Failing(Scrubber):
        def _scrub_any(self, v, path, notes, fail_soft=False):
            if v is value:
                raise ZeroDivisionError('never shown: hunter2')
            return super()._scrub_any(v, path, notes, fail_soft)

    scrubbed, notes = Failing().scrub_attributes({'outer': {'inner': [1, value]}})
    assert scrubbed == {'outer': {'inner': [1, FAILED]}} and notes == ['outer.inner[1]:error.ZeroDivisionError']
    err = capsys.readouterr().err
    [record] = [json.loads(line) for line in err.splitlines()]
    assert record['value.type'] == type_name and record['value.path'] == 'outer.inner[1]'  # named as in the notes
    assert record.get('value.length') == length and ('value.length' in record) == (length is not None)
    assert 'hunter2' not in err and record['message'] == _warnings.WITHHELD
    assert getattr(value, 'calls', []) in ([], ['len'])  # never its str or repr


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
    err = capsys.readouterr().err
    assert 'hunter2' not in err
    records = [json.loads(line) for line in err.splitlines()]
    assert [r['value.path'] for r in records] == ['*', '*']  # the whole record, named '*' as in its note
    span_type, log_type = (r['value.type'] for r in records)
    assert span_type.endswith('.ReadableSpan') and log_type.endswith('LogRecord'), records  # the SDK's record class


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
    assert sites == ['scrubbing.ScrubbingSpanExporter.export', 'scrubbing.ScrubbingSpanExporter.export.fallback']


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
