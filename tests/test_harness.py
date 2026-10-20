"""
the scenario harness itself (`tests/v0/_harness.py`, `tests/v0/_child.py`): a scenario's own budget, the pool size,
the environment built in pytest's thread, and results read whatever else the child prints
"""
import threading

from tests.v0 import _child
from tests.v0 import _harness
from tests.v0._harness import scenario

# a scenario's own budget is the one its run gets (the harness default would let this one sleep for 120 s)
OWN_BUDGET = scenario(__name__, 'harness_own_budget', r'''
import time
time.sleep(60)
''', timeout=5)


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


def test_a_child_gets_a_clean_environment(monkeypatch):
    monkeypatch.setenv('OTEL_SERVICE_NAME', 'leaked')
    monkeypatch.setenv('LOGFIRE_TOKEN', 'leaked')
    env = _harness.clean_env({'OTEL_SERVICE_NAME': 'chosen', 'PYTHONUTF8': None})
    assert env['OTEL_SERVICE_NAME'] == 'chosen'
    assert 'LOGFIRE_TOKEN' not in env
    assert 'PYTHONUTF8' not in env
    assert env['PYTHONPATH'] == str(_harness.REPO_ROOT)


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
