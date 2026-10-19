"""
AC-8, DEC-38's "proven safe is one command": the plain `tests/v0` tests pass under `OTW_IMPL=v1`

(with it, the tests of the scenario harness features this run leans on: a scenario's own budget and pool, the
environment built in pytest's thread, results read whatever else the child prints, a report that names what failed)

the gate and CI run the suite under the default, `OTW_IMPL=v0`, so this runs `pytest tests/v0` once more, under v1,
in a child interpreter, started at collection with the other scenarios so it overlaps them. under `OTW_IMPL=v1` the
outer run already holds those tests, so it is skipped (and not started)

the child is a whole suite, not one small script: it takes about 40 s alone, and it shares the machine with the outer
run's scenarios while starting its own, so it gets its own budget rather than the harness default, and a small pool
"""
import re
import threading

import pytest

from tests import impl
from tests.v0 import _child
from tests.v0 import _harness
from tests.v0._harness import Result
from tests.v0._harness import SCENARIO_TIMEOUT_SECONDS
from tests.v0._harness import scenario

NESTED_SUITE_TIMEOUT_SECONDS = 900
# the nested run's own pool is small: tests/v0 has few scenarios (about 40 s alone even with 2 at a time), and with two
# full pools, two suites at once ran this 16 GB machine out of memory, and sqlalchemy scenarios died at start-up
# with 0xC000070A and no output
NESTED_SUITE_WORKERS = max(2, _harness.scenario_workers() // 4)

V0_SUITE_UNDER_V1 = None
if impl.IMPL == 'v0':
    V0_SUITE_UNDER_V1 = scenario(__name__, 'v0_suite_under_v1', r'''
import sys
import pytest
sys.exit(pytest.main(['-q', '-p', 'no:cacheprovider', '-rfEs', 'tests/v0']))
''', env={'OTW_IMPL': 'v1', 'OTW_SCENARIO_WORKERS': str(NESTED_SUITE_WORKERS)}, timeout=NESTED_SUITE_TIMEOUT_SECONDS)


# a scenario's own budget is the one its run gets (the harness default would let this one sleep for 120 s)
OWN_BUDGET = scenario(__name__, 'harness_own_budget', r'''
import time
time.sleep(60)
''', timeout=5)


def _counts(summary: str) -> dict:
    return {word: int(n) for n, word in re.findall(r'(\d+) (passed|failed|errors?|skipped|xfailed|xpassed)', summary)}


def failure_report(result: Result, limit: int = 12000) -> str:
    """
    what went wrong in the nested run, whatever its size: `Result.describe()` keeps only the tail of stdout, which
    holds the skip lines and the summary, never the names of the failed tests or their tracebacks
    """
    lines = result.stdout.splitlines()
    named = [line for line in lines if line.startswith(('FAILED ', 'ERROR ', 'XPASS '))]
    details, inside = [], False
    for line in lines:
        if re.match(r'^=+ (FAILURES|ERRORS) =+$', line):
            inside = True
        elif re.match(r'^=+ ', line):
            inside = False
        if inside:
            details.append(line)
    detail_text = '\n'.join(details)
    if len(detail_text) > limit:
        detail_text = detail_text[:limit] + f'\n... ({len(detail_text) - limit} more chars)'
    summary = next((line for line in reversed(lines) if line.strip()), '')
    return (f'command: {result.args}\nexit code: {result.returncode}\nsummary: {summary}\n'
            f'--- failed / errored / xpassed ---\n' + '\n'.join(named) + '\n'
            f'--- tracebacks ---\n{detail_text}\n'
            f'--- stderr (last 4000 chars) ---\n{result.stderr[-4000:]}')


def test_the_nested_suite_has_its_own_budget_and_a_small_pool():
    assert NESTED_SUITE_TIMEOUT_SECONDS >= 5 * SCENARIO_TIMEOUT_SECONDS
    assert NESTED_SUITE_WORKERS <= max(2, _harness.scenario_workers() // 2)
    if V0_SUITE_UNDER_V1 is not None:
        assert V0_SUITE_UNDER_V1.timeout == NESTED_SUITE_TIMEOUT_SECONDS
        assert V0_SUITE_UNDER_V1.env['OTW_SCENARIO_WORKERS'] == str(NESTED_SUITE_WORKERS)


def test_the_scenario_pool_size_can_be_set(monkeypatch):
    monkeypatch.setenv('OTW_SCENARIO_WORKERS', '3')
    assert _harness.scenario_workers() == 3
    monkeypatch.delenv('OTW_SCENARIO_WORKERS')
    assert 2 <= _harness.scenario_workers() <= 8


def test_a_scenario_runs_within_its_own_budget():
    result = OWN_BUDGET.result()
    assert result.returncode == -1, result.describe()
    assert result.stderr.startswith('TIMEOUT after 5s'), result.describe()


def test_a_scenario_builds_its_environment_in_the_calling_thread(monkeypatch):
    # pytest rewrites PYTEST_CURRENT_TEST in os.environ around every test; a worker thread copying os.environ at that
    # moment raised KeyError (seen with three suites running at once)
    built_in = []
    real_clean_env = _harness.clean_env

    def recording_clean_env(overrides=None):
        built_in.append(threading.current_thread())
        return real_clean_env(overrides)

    monkeypatch.setattr(_harness, 'clean_env', recording_clean_env)
    s = _harness.Scenario(__name__, 'harness_env_thread', code='pass\n')  # not registered: run here and now
    assert s.result().returncode == 0, s.result().describe()
    assert built_in == [threading.current_thread()]


def test_a_result_sharing_its_line_with_other_output_is_still_read():
    # seen under load: fastapi_main.py's console span exporter wrote a span between a result and its newline
    span = '{"name": "GET /hello", "context": {}}'
    stdout = f'{span}\n{_child.RESULT_MARKER}{{"key": "a", "value": [1, 2]}}{span}\n{span}{_child.RESULT_MARKER}' \
             f'{{"key": "b", "value": "x"}}\n'
    assert _harness.parse_results(stdout) == {'a': [1, 2], 'b': 'x'}


def test_emit_writes_a_result_and_its_newline_at_once(monkeypatch):
    writes = []

    class Out:
        def write(self, text):
            writes.append(text)

        def flush(self):
            pass

    monkeypatch.setattr(_child.sys, 'stdout', Out())
    _child.emit('k', {'v': 1})
    assert writes == [_child.RESULT_MARKER + '{"key": "k", "value": {"v": 1}}\n']


def test_failure_report_names_the_failed_tests_ahead_of_the_skip_lines():
    stdout = '\n'.join([
        '..F..s',
        '=================================== FAILURES ===================================',
        '___________________________________ test_x ___________________________________',
        'E   assert 1 == 2',
        '=========================== short test summary info ============================',
        'FAILED tests/v0/test_a.py::test_x - assert 1 == 2',
        *[f'SKIPPED [1] tests/v0/test_b.py:{n}: v0_specific: pins a v0 detail, and OTW_IMPL=v1' for n in range(200)],
        '1 failed, 4 passed, 200 skipped in 9.00s',
    ])
    result = Result(['python', 'x.py'], 1, stdout, '')
    assert 'test_x' not in result.describe()  # the reason for the report: the tail is all skip lines
    report = failure_report(result)
    assert 'FAILED tests/v0/test_a.py::test_x - assert 1 == 2' in report
    assert 'E   assert 1 == 2' in report
    assert 'summary: 1 failed, 4 passed, 200 skipped in 9.00s' in report
    assert 'SKIPPED' not in report


@pytest.mark.criterion('AC-8')
@pytest.mark.skipif(impl.IMPL != 'v0', reason='under OTW_IMPL=v1 this run holds tests/v0 itself')
def test_plain_v0_tests_pass_under_v1():
    result = V0_SUITE_UNDER_V1.result()
    report = failure_report(result)
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    summary = lines[-1] if lines else ''
    assert result.returncode == 0, report  # a failure, an error, a strict xfail that passed, or the budget ran out
    counts = _counts(summary)
    assert counts.get('passed', 0) > 0, report
    assert not {'failed', 'error', 'errors', 'xpassed'} & set(counts), report
    # it really ran v1: the v0_specific tests were skipped as v0-only (tests/conftest.py)
    assert 'v0_specific: pins a v0 detail, and OTW_IMPL=v1' in result.stdout, report
