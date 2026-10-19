"""
v1 logging (OTW-11, workstream 8): two handlers on the root logger. OTLP log records carry the current span's ids and
the extras (AC-18, DEC-32), the stderr JSON line carries the same ids and a per-record local timestamp (AC-18,
DEC-34), logging anything writes exactly one JSON line and never raises (AC-31), the line is scrubbed (AC-13), and
instrumenting twice leaves two handlers (AC-6)

global OpenTelemetry and `logging` state cannot be reset, so every test reads a scenario run in its own interpreter
"""
import json
import re

import pytest

from tests.v0._harness import scenario
from tests.v1._prelude import PRELUDE

ZERO_TRACE = '0x' + '0' * 32
ZERO_SPAN = '0x' + '0' * 16

LOG_PRELUDE = PRELUDE + r'''
import logging
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter
logs = InMemoryLogRecordExporter()
_config.add_log_sink(logs)  # v1's test sink: every log record that would be exported, scrubbed


def exported():
    out = []
    for item in logs.get_finished_logs():
        record = item.log_record
        out.append({'body': record.body, 'trace_id': f'0x{record.trace_id:032x}',
                    'span_id': f'0x{record.span_id:016x}', 'trace_flags': int(record.trace_flags or 0),
                    'attributes': dict(record.attributes or {})})
    logs.clear()
    return out


def spans():
    out = [{'name': s.name, 'trace_id': f'0x{s.context.trace_id:032x}', 'span_id': f'0x{s.context.span_id:016x}'}
           for s in exporter.get_finished_spans()]
    exporter.clear()
    return out


def ours():
    return [getattr(h, '_opentelemetry_wrapper', None) for h in logging.getLogger().handlers
            if getattr(h, '_opentelemetry_wrapper', None)]
'''

MAIN = scenario(__name__, 'v1_logging_main', LOG_PRELUDE + r'''
class Seen(logging.Handler):
    """an app's own handler on the root logger: it must see the record unchanged by ours"""
    def __init__(self):
        super().__init__()
        self.keys = []

    def emit(self, record):
        self.keys.append(sorted(k for k in vars(record) if k.startswith('otel')))


before = len(logging.getLogger().handlers)
otel.instrument(logging)
otel.instrument(logging)
otel.instrument()
emit('added', len(logging.getLogger().handlers) - before)
emit('ours', ours())
seen = Seen()
logging.getLogger().addHandler(seen)


@otel
def work():
    logging.getLogger('app.work').warning('inside a span %s', 'with-arg', extra={'order_id': 7})


work()
logging.info('outside any span')
logging.getLogger('uvicorn.access').info('GET /hello 200')
logging.getLogger('uvicorn.access.child').info('GET /child 200')
logging.getLogger('uvicorn.error').info('uvicorn error log')
logging.warning('auth', extra={'password': 'hunter2'})
logging.warning('Authorization: Bearer abcdefghijklmnopqrstuvwxyz0123456789')
emit('spans', spans())
emit('exported', exported())
emit('seen_keys', seen.keys)
''', env={'OTEL_SERVICE_NAME': 'logging-test-service'})

SAMPLED_OUT = scenario(__name__, 'v1_logging_sampled_out', LOG_PRELUDE + r'''
otel.instrument(logging)
with otel('dropped'):
    logging.warning('inside a dropped span')
emit('spans', spans())
emit('exported', exported())
''', env={'OTEL_TRACES_SAMPLER': 'always_off'})

FORMAT_OFF = scenario(__name__, 'v1_logging_format_off', LOG_PRELUDE + r'''
otel.instrument(logging)
otel.instrument(logging)
emit('ours', ours())
logging.warning('only over OTLP')
emit('exported', exported())
''', env={'OTEL_WRAPPER_LOG_FORMAT': 'off'})

# the same moments in winter and in summer, in a zone west of UTC with daylight saving (the rule is spelled out, so
# glibc and the MSVC runtime agree), and in one east of UTC without
TZ_BODY = LOG_PRELUDE + r'''
otel.instrument(logging)
root = logging.getLogger()
for when, created in (('winter', 1736942400.0), ('summer', 1752580800.0)):  # 2025-01-15 / 2025-07-15, 12:00 UTC
    root.handle(logging.makeLogRecord({'msg': when, 'levelno': logging.WARNING, 'levelname': 'WARNING',
                                       'created': created}))
'''
TZ_WEST_DST = scenario(__name__, 'v1_logging_tz_west_dst', TZ_BODY, env={'TZ': 'EST+5EDT,M3.2.0,M11.1.0'})
TZ_EAST = scenario(__name__, 'v1_logging_tz_east', TZ_BODY, env={'TZ': 'XYZ-8'})

# v0's log_weird_things.py, plus the cases it doesn't reach
WEIRD = scenario(__name__, 'v1_logging_weird_things', LOG_PRELUDE + r'''
import dataclasses
import enum
from decimal import Decimal
from pydantic import BaseModel, computed_field


class Something(BaseModel):
    colour: str = 'blue'  # not `key`: a message starting `key=` is redacted as a query string (url_query)

    @computed_field  # in model_dump, not in the instance's attributes: the generic encoder would miss it
    @property
    def shade(self) -> str:
        return 'dark ' + self.colour


class Plain:
    def __init__(self):
        self.a = 1
        self.nested = {'b': [1, 2]}


class BadRepr:
    def __repr__(self):
        raise RuntimeError('no repr')

    def __str__(self):
        raise RuntimeError('no str')


@dataclasses.dataclass
class Point:
    x: int
    y: int


class Colour(enum.Enum):
    RED = 'red'


def numbers():
    yield 1


cycle = []
cycle.append(cycle)
otel.instrument(logging)
calls = 0


def log(level, *args, **kwargs):
    global calls
    calls += 1
    logging.log(level, *args, **kwargs)


W, I, E = logging.WARNING, logging.INFO, logging.ERROR
log(W, '')
log(W, None)
log(W, [1, 2, 3])
log(W, {1: 11, None: None, 'a': {'A'}})
log(W, float('nan'))
log(W, float('inf'))
log(W, float('-inf'))
log(I, 1.234 + 4j)  # a complex number
log(I, Decimal('0.11111111111111111111111111111111111111111111111111111111111111111111'))  # over-precise
log(I, logging)  # a module
log(I, print)  # a builtin
log(I, BaseModel)  # a class from a third-party library
log(I, object())  # an anonymous sentinel
log(I, 1, 2, 3, 4, 5, 6, 7)  # surplus positional arguments
log(E, Something)  # a defined class
log(E, Something())  # a pydantic model
log(E, lambda x: x + 1)  # a lambda
log(E, Plain())  # an instance
log(E, BadRepr())  # an object whose repr and str raise
log(E, cycle)  # a list that contains itself
log(E, Point(1, 2))  # a dataclass
log(E, Colour.RED)  # an enum
log(E, numbers())  # a generator: never consumed
log(E, {(1, 2): 'tuple key', Colour.RED: 'enum key'})
log(E, 'with weird extras', extra={'obj': object(), 'bad': BadRepr(), 'point': Point(3, 4)})
emit('calls', calls)
emit('exported', len(exported()))
''')

PYDANTIC_1 = scenario(__name__, 'v1_logging_pydantic_1', LOG_PRELUDE + r'''
import sys
import types
sys.modules['pydantic.version'] = types.SimpleNamespace(VERSION='1.10.13')  # as if the app imported pydantic 1
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    otel.instrument(logging)
    otel.instrument(logging)
emit('warnings', otel_warnings(caught))
''')


def json_lines(result):
    out = []
    for line in result.stderr_lines:  # every stderr line must be a json object
        try:
            out.append(json.loads(line))
        except ValueError:
            pytest.fail(f'not a JSON line: {line!r}\n{result.describe()}')
    return out


@pytest.fixture(scope='module')
def main():
    result = MAIN.result()
    assert result.returncode == 0, result.describe()
    return result


@pytest.fixture(scope='module')
def main_exported(main):
    return {record['body']: record for record in main['exported']}


@pytest.fixture(scope='module')
def main_lines(main):
    return {line['message']: line for line in json_lines(main)}


# ----------------------------------------------------------------------------------------------------------------------
# AC-6: two handlers, not four
# ----------------------------------------------------------------------------------------------------------------------

@pytest.mark.criterion('AC-6')
def test_instrumenting_logging_twice_leaves_two_handlers(main):
    assert main['added'] == 2
    assert sorted(main['ours']) == ['json', 'otlp']


@pytest.mark.criterion('AC-6')
def test_each_log_call_is_exported_once_and_written_once(main, main_exported):
    assert [r['body'] for r in main['exported']].count('inside a span with-arg') == 1
    assert [line['message'] for line in json_lines(main)].count('inside a span with-arg') == 1


# ----------------------------------------------------------------------------------------------------------------------
# AC-18: OTLP log records, inside and outside spans; the same ids on stderr
# ----------------------------------------------------------------------------------------------------------------------

@pytest.mark.criterion('AC-18')
def test_a_log_inside_a_span_is_exported_with_that_spans_ids_and_extras(main, main_exported):
    (span,) = [s for s in main['spans'] if s['name'] == '__main__.work']
    record = main_exported['inside a span with-arg']
    assert record['trace_id'] == span['trace_id'] != ZERO_TRACE
    assert record['span_id'] == span['span_id'] != ZERO_SPAN
    assert record['trace_flags'] & 1  # sampled (the SDK also sets W3C's random-id bit, 0x2)
    assert record['attributes']['order_id'] == 7


def test_exported_log_records_carry_the_stable_code_keys(main_exported):  # DEC-31, DEC-13
    attributes = main_exported['inside a span with-arg']['attributes']
    assert attributes['code.function.name'] == 'work'  # the bare funcName (DEC-13)
    assert attributes['code.file.path'].endswith('scenario_v1_logging_main.py')
    assert isinstance(attributes['code.line.number'], int)


@pytest.mark.criterion('AC-18')
def test_a_log_outside_spans_is_exported_with_zero_ids(main_exported):
    record = main_exported['outside any span']
    assert record['trace_id'] == ZERO_TRACE
    assert record['span_id'] == ZERO_SPAN


@pytest.mark.criterion('AC-18')
def test_the_stderr_line_carries_the_same_ids_as_the_exported_record(main_exported, main_lines):
    for message in ('inside a span with-arg', 'outside any span'):
        line, record = main_lines[message], main_exported[message]
        assert (line['otelTraceID'], line['otelSpanID']) == (record['trace_id'], record['span_id'])
    assert main_lines['inside a span with-arg']['otelTraceSampled'] is True
    assert main_lines['outside any span']['otelTraceSampled'] is False


def test_the_stderr_line_keeps_v0s_fields(main_lines):
    line = main_lines['inside a span with-arg']
    assert line['msg'] == 'inside a span %s'
    assert line['args'] == ['with-arg']
    assert line['name'] == 'app.work'
    assert line['levelname'] == 'WARNING'
    assert line['funcName'] == 'work'
    assert line['order_id'] == 7
    assert line['otelServiceName'] == 'logging-test-service'
    assert re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}[+-]\d\d:\d\d', line['asctime'])


def test_our_keys_never_reach_the_exported_record_or_other_handlers(main, main_exported):
    for record in main_exported.values():
        assert not [k for k in record['attributes'] if k.startswith('otel')], record['attributes']
    assert main['seen_keys'] and all(keys == [] for keys in main['seen_keys'])


@pytest.mark.criterion('AC-18')
def test_a_log_in_a_span_dropped_by_sampling_is_still_exported():  # DEC-32
    result = SAMPLED_OUT.result()
    assert result['spans'] == []
    (record,) = result['exported']
    assert record['body'] == 'inside a dropped span'
    assert not record['trace_flags'] & 1  # not sampled
    assert record['trace_id'] != ZERO_TRACE
    (line,) = json_lines(result)
    assert (line['otelTraceID'], line['otelSpanID']) == (record['trace_id'], record['span_id'])
    assert line['otelTraceSampled'] is False


def test_uvicorn_access_logs_reach_stderr_but_are_not_exported(main_exported, main_lines):
    assert 'GET /hello 200' in main_lines and 'GET /child 200' in main_lines
    assert 'GET /hello 200' not in main_exported and 'GET /child 200' not in main_exported
    assert 'uvicorn error log' in main_exported  # only the access logger and its children


def test_log_format_off_leaves_only_the_otlp_handler():
    result = FORMAT_OFF.result()
    assert result['ours'] == ['otlp']
    assert [r['body'] for r in result['exported']] == ['only over OTLP']
    assert 'only over OTLP' not in result.stderr


def single_tz_lines(handle):
    result = handle.result()
    assert result.returncode == 0, result.describe()
    return {line['message']: line for line in json_lines(result)}


@pytest.mark.criterion('AC-18')
def test_a_negative_utc_offset_and_its_dst_change_are_right_per_record():
    lines = single_tz_lines(TZ_WEST_DST)
    assert lines['winter']['tz_utc_offset_seconds'] == -5 * 3600
    assert lines['winter']['asctime'] == '2025-01-15T07:00:00.000000-05:00'
    assert lines['winter']['tz_name'] == 'EST'
    assert lines['summer']['tz_utc_offset_seconds'] == -4 * 3600
    assert lines['summer']['asctime'] == '2025-07-15T08:00:00.000000-04:00'
    assert lines['summer']['tz_name'] == 'EDT'


@pytest.mark.criterion('AC-18')
def test_a_positive_utc_offset():
    lines = single_tz_lines(TZ_EAST)
    for when in ('winter', 'summer'):
        assert lines[when]['tz_utc_offset_seconds'] == 8 * 3600
        assert lines[when]['asctime'].endswith('T20:00:00.000000+08:00')


# ----------------------------------------------------------------------------------------------------------------------
# AC-13: the stderr line is scrubbed before it is written
# ----------------------------------------------------------------------------------------------------------------------

@pytest.mark.criterion('AC-13')
def test_the_stderr_line_is_scrubbed(main, main_lines):
    assert main_lines['auth']['password'] == '[REDACTED]'
    (bearer,) = [line for line in main_lines.values() if line['message'].startswith('Authorization')]
    assert bearer['message'] == 'Authorization: Bearer [REDACTED]'
    assert bearer['msg'] == 'Authorization: Bearer [REDACTED]'
    assert 'hunter2' not in main.stderr
    assert 'abcdefghijklmnopqrstuvwxyz0123456789' not in main.stderr


# ----------------------------------------------------------------------------------------------------------------------
# AC-31: logging anything writes exactly one JSON line and never raises
# ----------------------------------------------------------------------------------------------------------------------

@pytest.fixture(scope='module')
def weird():
    result = WEIRD.result()
    assert result.returncode == 0, result.describe()
    return result


@pytest.fixture(scope='module')
def weird_lines(weird):
    return json_lines(weird)


@pytest.mark.criterion('AC-31')
def test_logging_anything_writes_exactly_one_json_line_per_call(weird, weird_lines):
    assert len(weird.stderr.splitlines()) == len(weird_lines) == weird['calls'] == 25
    assert weird['exported'] == weird['calls']  # and each is exported once, without the stdlib's error traceback


@pytest.mark.criterion('AC-31')
def test_weird_things_are_encoded(weird_lines):
    msgs = [line['msg'] for line in weird_lines]
    messages = [line['message'] for line in weird_lines]
    assert msgs[:4] == ['', None, [1, 2, 3], {'1': 11, 'null': None, 'a': ['A']}]
    assert messages[3] == "{1: 11, None: None, 'a': {'A'}}"
    assert str(msgs[4]) == 'nan' and msgs[5] == float('inf') and msgs[6] == float('-inf')
    assert msgs[7] == '(1.234+4j)'
    assert msgs[8] == 0.1111111111111111 and messages[8] == '0.' + '1' * 68
    assert msgs[9] == 'logging'
    assert msgs[10] == 'builtins.print'
    assert msgs[11] == 'pydantic.main.BaseModel'
    assert msgs[12].startswith('<object object at 0x')
    assert messages[13] == 'MSG=1 ARGS=(2, 3, 4, 5, 6, 7)'
    assert msgs[14] == '__main__.Something'
    assert msgs[15] == {'colour': 'blue', 'shade': 'dark blue'} and messages[15].startswith("colour='blue'")
    assert msgs[16] == '__main__.<lambda>'
    assert msgs[17] == {'a': 1, 'nested': {'b': [1, 2]}}
    assert msgs[18] == {}  # an instance is its attributes; it has none
    assert messages[18].startswith('MSG=<__main__.BadRepr object (repr failed)>')
    nested = msgs[19]  # the cycle is cut where it comes back, as its repr
    assert isinstance(nested, list)
    while isinstance(nested, list):
        (nested,) = nested
    assert nested == '[[...]]'
    assert msgs[20] == {'x': 1, 'y': 2}
    assert msgs[21] == 'red'
    assert msgs[22].startswith('<generator object numbers')
    assert msgs[23] == {'(1, 2)': 'tuple key', 'red': 'enum key'}
    assert weird_lines[24]['point'] == {'x': 3, 'y': 4}
    assert weird_lines[24]['bad'] == {} and weird_lines[24]['obj'].startswith('<object object at 0x')


def test_a_long_string_is_truncated_to_v0s_length():
    from opentelemetry_wrapper.v1._logging import truncate
    out = truncate({'message': 'x' * 20000, 'nested': ['y' * 10001], 'short': 'z'})
    assert len(out['message']) == 10000 and out['message'].endswith('... (TRUNCATED)')
    assert len(out['nested'][0]) == 10000
    assert out['short'] == 'z'


def test_pydantic_1_warns_once_at_instrumentation():  # DEC-35
    warnings = PYDANTIC_1.result()['warnings']
    assert len(warnings) == 1 and 'pydantic 1' in warnings[0]


# ----------------------------------------------------------------------------------------------------------------------
# review findings: extras the SDK rejects, format arguments, pydantic's own types
# ----------------------------------------------------------------------------------------------------------------------

AWKWARD = scenario(__name__, 'v1_logging_awkward', LOG_PRELUDE + r'''
import enum
from pydantic import AnyUrl, SecretBytes, SecretStr


class Level(enum.IntEnum):
    HIGH = 3


otel.instrument(logging)
calls = 0


def log(*args, **kwargs):
    global calls
    calls += 1
    logging.warning(*args, **kwargs)


log('int_float', extra={'coords': [1, 2.5]})  # mixed types in a sequence: the SDK warns and exports None
log('int_str', extra={'mixed': [1, 'a']})
log('tuple_obj', extra={'pair': (1, object())})
log('nested', extra={'deep': {'flags': [True, 1], 2: 'two', '': 'empty', 'levels': [Level.HIGH, 4]}})
log('int_key', extra={1: 'x'})  # a key that is not a str: the SDK's 'invalid key' warning
log('list_none', extra={'ids': [1, None]})
log('Authorization: Bearer %s', 'abcdefghijklmnopqrstuvwxyz0123456789')
log('password=%s user=%s', 'hunter2secret', 'bob')
log('password=%(pw)s', {'pw': 'dictsecret99'})
log('plain %s', 'keepme')
log(SecretStr('hunter2xyz'))
log('pydantic_extras', extra={'sec': SecretStr('hunter2def'), 'raw': SecretBytes(b'hunter2bytes'),
                              'url': AnyUrl('http://example.com/x')})
emit('calls', calls)
emit('exported', exported())
''')


@pytest.fixture(scope='module')
def awkward():
    result = AWKWARD.result()
    assert result.returncode == 0, result.describe()
    return result


@pytest.fixture(scope='module')
def awkward_lines(awkward):
    return {line['message']: line for line in json_lines(awkward)}


@pytest.fixture(scope='module')
def awkward_exported(awkward):
    return {record['body']: record['attributes'] for record in awkward['exported']}


@pytest.mark.criterion('AC-31')
def test_extras_the_sdk_would_reject_still_write_exactly_one_json_line_per_call(awkward, awkward_lines):
    assert len(awkward.stderr.splitlines()) == len(json_lines(awkward)) == len(awkward_lines) == awkward['calls']
    assert 'recursive logging' not in awkward.stderr and 'opentelemetry.attributes' not in awkward.stderr
    assert awkward_lines['int_float']['coords'] == [1, 2.5]  # stderr keeps the values as they are
    assert awkward_lines['int_key']['1'] == 'x'


@pytest.mark.criterion('AC-18')
def test_extras_the_sdk_would_reject_are_exported_as_valid_attributes(awkward, awkward_exported):
    assert len(awkward['exported']) == awkward['calls']
    assert awkward_exported['int_float']['coords'] == ['1', '2.5']  # mixed types: the items as text, never None
    assert awkward_exported['int_str']['mixed'] == ['1', 'a']
    first, second = awkward_exported['tuple_obj']['pair']
    assert first == '1' and second.startswith('<object object at 0x')
    deep = awkward_exported['nested']['deep']
    assert deep['flags'] == ['True', '1'] and deep['2'] == 'two' and deep["''"] == 'empty'
    assert deep['levels'] == [3, 4]  # an IntEnum member is a plain int: one type
    assert awkward_exported['int_key']['1'] == 'x'
    assert awkward_exported['list_none']['ids'] == [1, None]


@pytest.mark.criterion('AC-13')
def test_format_arguments_are_redacted_where_the_message_was(awkward, awkward_lines):
    bearer = awkward_lines['Authorization: Bearer [REDACTED]']
    assert bearer['args'] == ['[REDACTED]']
    assert awkward_lines['password=[REDACTED] user=bob']['args'] == ['[REDACTED]', 'bob']
    assert awkward_lines['password=[REDACTED]']['args'] == {'pw': '[REDACTED]'}
    assert awkward_lines['plain keepme']['args'] == ['keepme']  # nothing redacted: the arguments are kept
    for secret in ('abcdefghijklmnopqrstuvwxyz0123456789', 'hunter2secret', 'dictsecret99'):
        assert secret not in awkward.stderr


@pytest.mark.criterion('AC-13')
def test_pydantic_secrets_are_masked_and_its_urls_are_text_on_stderr(awkward, awkward_lines):  # DEC-35
    assert awkward_lines['**********']['msg'] == '**********'
    line = awkward_lines['pydantic_extras']
    assert line['sec'] == line['raw'] == '**********'
    assert line['url'] == 'http://example.com/x'
    assert 'hunter2' not in awkward.stderr and '_secret_value' not in awkward.stderr
