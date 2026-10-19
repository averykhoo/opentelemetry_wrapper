"""
v1's pytest plugin (AC-5, DEC-10): `otel_spans` / `otel_logs` capture what would be exported, reset per test, and
switch the real exporters off for the tests that request them (or for the whole suite with `otel_capture = true`)

the plugin is tested by running an inner pytest session in a temporary directory, in its own interpreter: it sets
global OpenTelemetry state, which cannot be reset
"""
import pytest
import subprocess
import sys
import textwrap
from pathlib import Path

from tests.v0._harness import clean_env

CONFTEST = '''\
from tests.impl import import_v1
import_v1()
pytest_plugins = ['opentelemetry_wrapper.v1.pytest_plugin']
'''

INNER_TESTS = '''\
import logging

from opentelemetry_wrapper.v1 import _config
from opentelemetry_wrapper.v1 import otel


@otel
def traced_function():
    return 1


def test_a_requested_fixture_captures_a_span_and_switches_exporters_off(otel_spans):
    assert traced_function() == 1
    spans = otel_spans.get_finished_spans()
    assert len(spans) == 1, [s.name for s in spans]
    assert spans[0].name.endswith('traced_function')
    assert _config._exporters_enabled is False


def test_the_fixture_starts_empty_in_the_next_test(otel_spans):
    assert otel_spans.get_finished_spans() == ()


def test_exporters_stay_on_without_opting_in():
    assert _config._exporters_enabled is True


def test_otel_logs_captures_a_log_record(otel_logs):
    otel.instrument(logging)
    logging.getLogger('x').warning('hello')
    records = otel_logs.get_finished_logs()
    assert len(records) == 1, records
    assert records[0].log_record.body == 'hello'
'''

WHOLE_SUITE_TEST = '''\
from opentelemetry_wrapper.v1 import _config


def test_the_whole_suite_has_opted_in():
    assert _config._exporters_enabled is False
'''


def _run_inner(directory: Path, tests: str, ini: str = '') -> 'subprocess.CompletedProcess[str]':
    (directory / 'conftest.py').write_text(CONFTEST, encoding='utf-8')
    (directory / 'test_inner.py').write_text(textwrap.dedent(tests), encoding='utf-8')
    if ini:
        (directory / 'pytest.ini').write_text(ini, encoding='utf-8')
    return subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', str(directory)],
                          env=clean_env(), cwd=str(directory), capture_output=True, text=True, timeout=120,
                          encoding='utf-8', errors='replace')


@pytest.mark.criterion('AC-5')
def test_the_fixtures_capture_reset_and_opt_in_per_test(tmp_path):  # AC-5, DEC-10
    proc = _run_inner(tmp_path, INNER_TESTS)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert '4 passed' in proc.stdout, proc.stdout


@pytest.mark.criterion('AC-5')
def test_otel_capture_in_the_ini_file_opts_the_whole_suite_in(tmp_path):  # AC-5, DEC-10
    proc = _run_inner(tmp_path, WHOLE_SUITE_TEST, ini='[pytest]\notel_capture = true\n')
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert '1 passed' in proc.stdout, proc.stdout
