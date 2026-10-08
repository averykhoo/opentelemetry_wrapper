"""
the example scripts in the repo root, run unmodified (HANDOFF.md "How to verify")

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
TYPE_CHECKING = scenario(__name__, 'script_type_checking',
                         script=REPO_ROOT / 'opentelemetry_wrapper' / 'v0' / 'utils' / 'type_checking.py')


def ok(handle):
    result = handle.result()
    assert result.returncode == 0, result.describe()
    return result


def console_spans(result):
    """v0's console exporter prints one json span per line on stdout"""
    return [obj for obj in result.stdout_json_objects() if 'context' in obj and 'name' in obj]


def stderr_logs(result):
    return [json.loads(line) for line in result.stderr_lines]


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


def test_experiment_otel_logging_span_names():
    spans = console_spans(ok(EXPERIMENT))
    assert collections.Counter(s['name'] for s in spans) == {
        'async <__main__>.bitshift':                                                                      89,
        'async @typecheck <__main__>.multiply':                                                           4,
        'async <__main__>.square':                                                                        2,
        'asgiref.sync.AsyncToSync <__main__>.exponentiate':                                               1,
        '<opentelemetry_wrapper.v0.dependencies.opentelemetry.instrument_logging>.instrument_logging':    1,
    }
    assert all(s['status']['status_code'] == 'OK' for s in spans)
    assert all('duration_ns' in s for s in spans)  # v0's console formatter adds this


# ----------------------------------------------------------------------------------------------------------------------
# setup_otel_logging.py: exit 0, 9x A.__new__ and 9x A.__init__ spans, all status OK
# ----------------------------------------------------------------------------------------------------------------------

def test_setup_otel_logging_spans():
    result = ok(SETUP)
    spans = console_spans(result)
    assert collections.Counter(s['name'] for s in spans) == {
        '<__main__>.A.__new__':                                                                               9,
        '<__main__>.A.__init__':                                                                              9,
        '<__main__>.A.c':                                                                                     2,
        '<__main__>.A.c.<locals>.d':                                                                          2,
        'property <__main__>.A.e':                                                                            2,
        '<__main__>.A.b':                                                                                     1,
        '<__main__>.A.__call__':                                                                              1,
        '<__main__>.A.__enter__':                                                                             1,
        '<__main__>.A.__exit__':                                                                              1,
        '<opentelemetry_wrapper.v0.dependencies.opentelemetry.instrument_dataclasses>.instrument_dataclasses': 1,
        '<opentelemetry_wrapper.v0.dependencies.opentelemetry.instrument_logging>.instrument_logging':         1,
    }
    assert all(s['status']['status_code'] == 'OK' for s in spans)
    logs = stderr_logs(result)
    assert len(logs) == 26
    assert all(log['otelSpanID'] != '0x' + '0' * 16 for log in logs)  # every log is inside some span


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


def test_log_weird_things_encodings(weird_logs):
    msgs = [log['msg'] for log in weird_logs]
    messages = [log['message'] for log in weird_logs]
    assert msgs[:4] == ['', None, [1, 2, 3], {'1': 11, 'null': None, 'a': ['A']}]
    assert messages[3] == "{1: 11, None: None, 'a': {'A'}}"
    assert str(msgs[4]) == 'nan' and msgs[5] == float('inf') and msgs[6] == float('-inf')  # NaN / Infinity in json
    assert msgs[7] == '(1.234+4j)'  # complex -> str
    assert msgs[8] == 0.1111111111111111  # Decimal -> float: precision is lost in `msg`...
    assert messages[8] == '0.' + '1' * 68  # ...but not in `message`
    assert msgs[10] == '<builtins>.print'  # functions and classes are named via CodeInfo
    assert msgs[11] == '<pydantic.main>.BaseModel'
    assert msgs[12] == '<pydantic.v1.json>.pydantic_encoder'
    assert messages[14] == 'MSG=1 ARGS=(2, 3, 4, 5, 6, 7)'  # bad format args don't crash
    assert msgs[15] == '<__main__>.Something'
    assert msgs[16] == {'key': 'value'}  # pydantic model -> dict
    assert messages[16] == "key='value'"
    assert msgs[17] == '<__main__>.<lambda>'


# ----------------------------------------------------------------------------------------------------------------------
# sqlalchemy_example.py: exit 0 and connect + SELECT :memory: spans in stdout
# ----------------------------------------------------------------------------------------------------------------------

def test_sqlalchemy_example_spans():
    result = ok(SQLALCHEMY)
    assert result.stdout.splitlines()[:3] == ['is_sqlalchemy_engine True', 'is_sqlalchemy_sync_engine True',
                                              'is_sqlalchemy_async_engine False']
    names = [s['name'] for s in console_spans(result)]
    assert 'connect' in names
    assert 'SELECT :memory:' in names


# ----------------------------------------------------------------------------------------------------------------------
# type_checking.py: same output under pydantic 2 and pydantic 1 (only pydantic 2 is installed; output recorded on
# 2026-10-04, when both matched)
# ----------------------------------------------------------------------------------------------------------------------

def test_type_checking_script_output():
    result = ok(TYPE_CHECKING)
    assert result.stdout.splitlines() == [
        "'asdf'", "'123'", '123', '123.0', '100', '100', '100', 'datetime.date(2024, 1, 1)',
        '4.0', '4', '6.25', '4', '4.0', 'True', '2',
    ]
