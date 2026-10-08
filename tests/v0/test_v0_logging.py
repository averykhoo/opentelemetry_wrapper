"""
`instrument_logging`: one-line JSON logs on stderr carrying `otelTraceID` / `otelSpanID` (PLAN.md workstream 7 keeps
this). each scenario runs in a fresh interpreter, since it reconfigures the root logger and the log record factory
"""
import json
import re

import pytest

from tests.v0._harness import scenario

SERVICE_NAME = 'characterization-test-service'

BASIC = scenario(__name__, 'logging_basic', r'''
import logging
from opentelemetry_wrapper import instrument_decorate, instrument_logging
exp = setup_spans()

root = logging.getLogger()
before = list(root.handlers)
instrument_logging()
after_once = list(root.handlers)
instrument_logging()
after_twice = list(root.handlers)
emit('handlers_added_by_first_call', len(after_once) - len(before))
emit('handlers_added_by_second_call', len(after_twice) - len(after_once))
emit('root_level', root.level)
take(exp)

logging.info('outside any span')

@instrument_decorate
def work():
    logging.warning('inside a span %s', 'with-arg')

@instrument_decorate
async def async_work():
    logging.error('inside an async span')

work()
import asyncio
asyncio.run(async_work())
emit('spans', take(exp))

logging.getLogger('some.child.logger').error('from a child logger', extra={'custom_key': 'custom value'})
try:
    1 / 0
except ZeroDivisionError:
    logging.exception('with a traceback')
logging.debug('debug is below the default INFO level')
logging.info('x' * 20000)
''', env={'OTEL_SERVICE_NAME': SERVICE_NAME})

TZ_NEGATIVE = scenario(__name__, 'logging_tz_negative', r'''
import logging
from opentelemetry_wrapper import instrument_logging
instrument_logging()
logging.warning('tz check')
''', env={'TZ': 'EST+5'})  # POSIX-style: UTC-5, no DST rule (honoured by the MSVC runtime on Windows too)

TZ_POSITIVE = scenario(__name__, 'logging_tz_positive', r'''
import logging
from opentelemetry_wrapper import instrument_logging
instrument_logging()
logging.warning('tz check')
''', env={'TZ': 'XYZ-8'})  # UTC+8

TEXT_AND_STREAM = scenario(__name__, 'logging_text_and_stream', r'''
import io, logging
from opentelemetry_wrapper import instrument_decorate, instrument_logging
exp = setup_spans()

instrument_logging(print_json=False)

@instrument_decorate
def work():
    logging.warning('text mode line')

work()
emit('span', take(exp))

buffer = io.StringIO()
instrument_logging(stream=buffer)
logging.warning('sent to the stream')
emit('stream_contents', buffer.getvalue())
''')

CLOBBER = scenario(__name__, 'logging_clobber', r'''
import io, logging
from opentelemetry_wrapper import instrument_logging

noisy = logging.getLogger('noisy')
own_stream = io.StringIO()
noisy.addHandler(logging.StreamHandler(own_stream))
noisy.propagate = False

instrument_logging()
noisy.warning('without clobbering')
instrument_logging(clobber_other_log_handlers=True)
noisy.warning('with clobbering')
emit('own_handler_saw', own_stream.getvalue().splitlines())
emit('noisy_propagate', noisy.propagate)
''')


def json_lines(result):
    out = []
    for line in result.stderr_lines:
        out.append(json.loads(line))  # every stderr line must be a json object
    return out


@pytest.fixture(scope='module')
def basic():
    result = BASIC.result()
    assert result.returncode == 0, result.describe()
    return result


@pytest.fixture(scope='module')
def basic_logs(basic):
    return {log['message'][:40]: log for log in json_lines(basic)}


def test_every_stderr_line_is_one_json_object(basic):
    assert basic.stderr_lines
    for line in basic.stderr_lines:
        assert isinstance(json.loads(line), dict), line


def test_instrument_logging_twice_adds_one_handler(basic):
    assert basic['handlers_added_by_first_call'] == 1
    assert basic['handlers_added_by_second_call'] == 0


def test_each_log_call_is_written_exactly_once(basic):
    messages = [log['message'] for log in json_lines(basic)]
    assert messages.count('outside any span') == 1
    assert messages.count('inside a span with-arg') == 1


def test_default_level_is_info(basic, basic_logs):
    assert basic['root_level'] == 20
    assert not any('debug is below' in key for key in basic_logs)


def test_log_inside_a_span_carries_that_spans_ids(basic, basic_logs):
    spans = {s['name']: s for s in basic['spans']}
    sync_span = spans['<__main__>.work']
    async_span = spans['async <__main__>.async_work']

    log = basic_logs['inside a span with-arg']
    assert log['otelTraceID'] == sync_span['trace_id']
    assert log['otelSpanID'] == sync_span['span_id']

    log = basic_logs['inside an async span']
    assert log['otelTraceID'] == async_span['trace_id']
    assert log['otelSpanID'] == async_span['span_id']


def test_log_outside_a_span_has_all_zero_ids(basic_logs):
    log = basic_logs['outside any span']
    assert log['otelTraceID'] == '0x' + '0' * 32
    assert log['otelSpanID'] == '0x' + '0' * 16


def test_ids_are_0x_prefixed_lowercase_hex_matching_the_span_json(basic_logs):
    for log in basic_logs.values():
        assert re.fullmatch(r'0x[0-9a-f]{32}', log['otelTraceID'])
        assert re.fullmatch(r'0x[0-9a-f]{16}', log['otelSpanID'])


def test_log_record_fields(basic_logs):
    log = basic_logs['inside a span with-arg']
    assert log['msg'] == 'inside a span %s'
    assert log['args'] == ['with-arg']
    assert log['message'] == 'inside a span with-arg'
    assert log['levelname'] == 'WARNING'
    assert log['name'] == 'root'
    assert log['funcName'] == 'work'
    assert log['filename'] == 'scenario_logging_basic.py'
    assert log['otelServiceName'] == SERVICE_NAME
    assert isinstance(log['tz_utc_offset_seconds'], int)
    assert re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}[+-]\d\d:\d\d', log['asctime'])


def test_extra_fields_and_logger_name(basic_logs):
    log = basic_logs['from a child logger']
    assert log['name'] == 'some.child.logger'
    assert log['custom_key'] == 'custom value'


def test_exception_text_is_included(basic_logs):
    log = basic_logs['with a traceback']
    assert log['levelname'] == 'ERROR'
    assert 'ZeroDivisionError' in log['exc_text']
    assert 'Traceback' in log['exc_text']


def test_long_strings_are_truncated(basic_logs):
    log = basic_logs['x' * 40]
    assert len(log['message']) == 10000
    assert log['message'].endswith('... (TRUNCATED)')
    assert len(log['msg']) == 10000


# ----------------------------------------------------------------------------------------------------------------------
# timezone (HANDOFF.md "Wrong timezone offset for negative offsets")
# ----------------------------------------------------------------------------------------------------------------------

def single_log(scenario_handle):
    result = scenario_handle.result()
    assert result.returncode == 0, result.describe()
    (log,) = json_lines(result)
    return log


def test_positive_utc_offset():
    log = single_log(TZ_POSITIVE)
    assert log['tz_utc_offset_seconds'] == 8 * 3600
    assert log['asctime'].endswith('+08:00')


def test_negative_utc_offset_asctime_is_correct():
    log = single_log(TZ_NEGATIVE)
    assert log['asctime'].endswith('-05:00')
    assert log['tz_name'] == 'EST'


@pytest.mark.xfail(strict=True, reason='HANDOFF.md "Wrong timezone offset for negative offsets": '
                                       'logging_json_formatter.py:99 uses timedelta.seconds (UTC-5 -> 68400)')
def test_negative_utc_offset_seconds():
    assert single_log(TZ_NEGATIVE)['tz_utc_offset_seconds'] == -5 * 3600


# ----------------------------------------------------------------------------------------------------------------------
# other output modes
# ----------------------------------------------------------------------------------------------------------------------

@pytest.fixture(scope='module')
def text_and_stream():
    result = TEXT_AND_STREAM.result()
    assert result.returncode == 0, result.describe()
    return result


def test_text_mode_writes_the_verbose_format_to_stderr(text_and_stream):
    (span,) = text_and_stream['span']
    lines = [line for line in text_and_stream.stderr_lines if 'text mode line' in line]
    assert len(lines) == 1
    match = re.fullmatch(r'\S+ \S+ WARNING  \[root\] \[scenario_logging_text_and_stream\.py:work:\d+\] '
                         r'\[trace_id=(0x[0-9a-f]{32}) span_id=(0x[0-9a-f]{16}) resource\.service\.name=(.+)\] '
                         r'- text mode line', lines[0])
    assert match, lines[0]
    assert match.group(1) == span['trace_id']
    assert match.group(2) == span['span_id']


def test_stream_argument_redirects_json_logs(text_and_stream):
    (line,) = text_and_stream['stream_contents'].splitlines()
    assert json.loads(line)['message'] == 'sent to the stream'
    assert 'sent to the stream' not in text_and_stream.stderr


def test_clobbering_other_handlers():
    result = CLOBBER.result()
    assert result.returncode == 0, result.describe()
    # without clobbering, a logger with its own handler and propagate=False keeps logging only there
    assert result['own_handler_saw'] == ['without clobbering']
    # with clobbering, its handlers are dropped and it propagates to our root json handler
    assert result['noisy_propagate'] is True
    messages = [json.loads(line)['message'] for line in result.stderr_lines]
    assert messages == ['with clobbering']
