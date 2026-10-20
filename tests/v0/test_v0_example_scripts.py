"""
the example scripts in the repo root, run unmodified (CLAUDE.md § Gate, outside the gate), on v1 since 1.0.0 (OTW-25)

each script turns on v1's console span exporter (`otel.configure(traces_exporter='console')`), so its spans are
OpenTelemetry's `ConsoleSpanExporter` output on stdout (indented json, one object per span), and
`otel.instrument(logging)` writes one line of json per log on stderr

fastapi_main.py is in test_v0_fastapi.py (it starts uvicorn on :8000 when run as a script, so it is imported there)
"""
import collections
import json

import pytest

from tests.v0._harness import REPO_ROOT
from tests.v0._harness import scenario

EXPERIMENT = scenario(__name__, 'script_experiment_otel_logging', script=REPO_ROOT / 'experiment_otel_logging.py')
SETUP = scenario(__name__, 'script_setup_otel_logging', script=REPO_ROOT / 'setup_otel_logging.py')
WEIRD = scenario(__name__, 'script_log_weird_things', script=REPO_ROOT / 'log_weird_things.py')
SQLALCHEMY = scenario(__name__, 'script_sqlalchemy_example', script=REPO_ROOT / 'sqlalchemy_example.py')

NO_SPAN = '0x' + '0' * 16


def ok(handle):
    result = handle.result()
    assert result.returncode == 0, result.describe()
    return result


def json_objects(text):
    """every json object in `text`, however it is indented (the console exporter writes each span over many lines)"""
    decoder = json.JSONDecoder()
    out, at = [], text.find('{')
    while at >= 0:
        try:
            obj, end = decoder.raw_decode(text, at)
        except json.JSONDecodeError:
            end = at + 1
        else:
            out.append(obj)
        at = text.find('{', end)
    return out


def console_spans(result):
    return [obj for obj in json_objects(result.stdout) if 'context' in obj and 'name' in obj]


def stderr_logs(result):
    return [json.loads(line) for line in result.stderr_lines]  # fails on any line that is not one json object


# ----------------------------------------------------------------------------------------------------------------------
# experiment_otel_logging.py: exit 0 (final assert passes), every log's otelSpanID matches a span
# ----------------------------------------------------------------------------------------------------------------------

def test_experiment_otel_logging_logs_match_spans():
    result = ok(EXPERIMENT)
    spans = {s['context']['span_id']: s for s in console_spans(result)}
    logs = stderr_logs(result)
    assert len(logs) == 7
    for log in logs:
        assert log['otelSpanID'] in spans, log
        assert spans[log['otelSpanID']]['context']['trace_id'] == log['otelTraceID']
    assert {log['funcName'] for log in logs} == {'exponentiate', 'multiply', 'square'}
    assert len({s['context']['trace_id'] for s in spans.values()}) == 1  # one call, one trace, across threads


def test_experiment_otel_logging_span_names():
    spans = console_spans(ok(EXPERIMENT))
    assert collections.Counter(s['name'] for s in spans) == {
        '__main__.bitshift':                 89,
        # `@otel @lru_cache @otel`: the outer `@otel` returns the lru_cache as it is
        '__main__.multiply':                 4,
        '__main__.square':                   2,
        # asgiref's AsyncToSync keeps no `__wrapped__`, so its spans are named after its `__call__`; the `@otel` over
        # `sync_to_async` finds the AsyncToSync already decorated and returns it unchanged: 3 decorators, 2 spans
        'asgiref.sync.AsyncToSync.__call__': 2,
    }
    assert all(s['status']['status_code'] == 'OK' for s in spans)


# ----------------------------------------------------------------------------------------------------------------------
# setup_otel_logging.py: exit 0, 9x A.__new__ and 9x A.__init__ spans, all status OK
# ----------------------------------------------------------------------------------------------------------------------

def test_setup_otel_logging_spans():
    result = ok(SETUP)
    spans = console_spans(result)
    assert collections.Counter(s['name'] for s in spans) == {
        '__main__.A.__new__':      9,
        '__main__.A.__init__':     9,
        '__main__.A.c':            2,
        '__main__.A.c.<locals>.d': 2,
        '__main__.A.e':            2,  # `@otel(properties=True)`
        '__main__.A.b':            1,
        '__main__.A.__call__':     1,
        '__main__.A.__enter__':    1,  # one span from `__enter__` to `__exit__` (DEC-22)
    }
    assert all(s['status']['status_code'] == 'OK' for s in spans)
    span_ids = {s['context']['span_id'] for s in spans}
    logs = stderr_logs(result)
    assert len(logs) == 26
    assert all(log['otelSpanID'] in span_ids for log in logs)  # every log is inside one of the spans


# ----------------------------------------------------------------------------------------------------------------------
# log_weird_things.py: exit 0, every stderr line is valid one-line json
# ----------------------------------------------------------------------------------------------------------------------

@pytest.fixture(scope='module')
def weird_logs():
    result = ok(WEIRD)
    logs = stderr_logs(result)  # json.loads on every line
    assert len(logs) == 18
    return logs


def test_log_weird_things_every_line_is_json(weird_logs):
    assert [log['levelname'] for log in weird_logs] == ['WARNING'] * 7 + ['INFO'] * 8 + ['ERROR'] * 3
    assert all(log['otelSpanID'] == NO_SPAN for log in weird_logs)  # logged outside any span


def test_log_weird_things_encodings(weird_logs):
    msgs = [log['msg'] for log in weird_logs]
    messages = [log['message'] for log in weird_logs]
    assert msgs[:4] == ['', None, [1, 2, 3], {'1': 11, 'null': None, 'a': ['A']}]
    assert messages[3] == "{1: 11, None: None, 'a': {'A'}}"
    assert str(msgs[4]) == 'nan' and msgs[5] == float('inf') and msgs[6] == float('-inf')  # NaN / Infinity in json
    assert msgs[7] == '(1.234+4j)'  # complex -> str
    assert msgs[8] == 0.1111111111111111  # Decimal -> float: precision is lost in `msg`...
    assert messages[8] == '0.' + '1' * 68  # ...but not in `message`
    assert msgs[9] == 'logging'  # modules, functions and classes are named `module.qualname`, never their repr
    assert msgs[10] == 'builtins.print'
    assert msgs[11] == 'pydantic.main.BaseModel'
    assert msgs[12] == 'pydantic.v1.json.pydantic_encoder'
    assert msgs[14] == 1 and messages[14] == 'MSG=1 ARGS=(2, 3, 4, 5, 6, 7)'  # bad format args don't crash
    assert msgs[15] == '__main__.Something'
    assert msgs[16] == {'key': 'value'}  # pydantic model -> dict
    assert msgs[17] == '__main__.<lambda>'


# ----------------------------------------------------------------------------------------------------------------------
# sqlalchemy_example.py: exit 0 and a `SELECT :memory:` span in stdout (`otel.instrument(engine)` traces that engine's
# queries; `connect` spans come from `otel.instrument(sqlalchemy)`, DEC-1)
# ----------------------------------------------------------------------------------------------------------------------

def test_sqlalchemy_example_spans():
    result = ok(SQLALCHEMY)
    assert result.stdout.splitlines()[:3] == ['is_sqlalchemy_engine True', 'is_sqlalchemy_sync_engine True',
                                              'is_sqlalchemy_async_engine False']
    spans = console_spans(result)
    assert [s['name'] for s in spans] == ['SELECT :memory:']
    assert spans[0]['attributes']['db.system'] == 'sqlite'
    assert spans[0]['attributes']['db.statement'] == 'SELECT * FROM sqlite_master'  # no sqlcommenter unless asked
