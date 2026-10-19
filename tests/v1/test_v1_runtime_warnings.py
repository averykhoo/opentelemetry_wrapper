"""
runtime warnings go to stderr once, never through `warnings.warn` (DEC-81): the second unnamed `with otel:` block, and
the warnings implicit configuration raises at the first span or call. an explicit `otel.configure(...)` and decoration
time keep `warnings.warn`, so an error filter still raises there
"""
import pytest
import json

from tests.v0._harness import scenario
from tests.v1._prelude import PRELUDE

RUNTIME = scenario(__name__, 'v1_runtime_warnings', PRELUDE + r'''
import sys
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

# an application's own provider, set before ours: implicit configuration at the first span says so
trace.set_tracer_provider(TracerProvider())
warnings.simplefilter('error')  # every warning is an exception, in the app and so in our runtime paths


def two_blocks():
    with otel:
        pass
    with otel:
        pass


@otel
def decorated():
    return 'ok'


raised = []
try:
    two_blocks()          # configures implicitly (the first span), then the second block is the second site
    two_blocks()
    two_blocks()
    emit('decorated', decorated())
except BaseException as e:  # noqa
    raised.append(f'{type(e).__name__}: {e}')
emit('runtime_raised', raised)
emit('configured', _config.is_configured())

# decoration time and explicit configure are not runtime: an error filter still raises there
from opentelemetry_wrapper.v1 import _decorator
try:
    _decorator.decorate(42)
except v1.OtelWrapperWarning as e:
    emit('decoration_raised', str(e))
try:
    otel.configure(service_name='too late, and different')
except v1.OtelWrapperWarning as e:
    emit('explicit_configure_raised', str(e))
''')


def _reports(result):
    records = []
    for line in result.stderr_lines:
        if line.startswith('{'):
            record = json.loads(line)  # every report is one valid JSON line
            if record.get('opentelemetry_wrapper') == 'warning':
                records.append(record)
    return records


@pytest.mark.criterion('AC-22')
def test_runtime_warnings_do_not_raise_under_an_error_filter():  # DEC-81
    result = RUNTIME.result()
    assert result['runtime_raised'] == []
    assert result['decorated'] == 'ok'
    assert result['configured'] is True


@pytest.mark.criterion('AC-2')
@pytest.mark.criterion('AC-22')
def test_runtime_warnings_are_one_stderr_line_each_once_per_site():  # DEC-81
    messages = [r['message'] for r in _reports(RUNTIME.result())]
    unnamed = [m for m in messages if 'two unnamed `with otel:` blocks' in m and 'two_blocks' in m]
    assert len(unnamed) == 1, messages  # three calls of the same function, one line
    foreign = [m for m in messages if 'tracer' in m]
    assert len(foreign) == 1, messages  # implicit configuration's own warning, reported rather than raised
    assert len(messages) == 2, messages
    assert all('site' in r for r in _reports(RUNTIME.result()))


@pytest.mark.criterion('AC-22')
def test_decoration_time_and_explicit_configure_still_warn_through_warnings():  # DEC-81, DEC-49
    result = RUNTIME.result()
    assert 'it is not callable' in result['decoration_raised']
    assert 'ignored' in result['explicit_configure_raised']
