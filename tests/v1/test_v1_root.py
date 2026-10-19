"""
the package root is v1, and v0's names load lazily (DEC-80, DEC-46): importing `opentelemetry_wrapper` or
`opentelemetry_wrapper.v1` imports no v0; the first access to a v0 name imports v0 (and so runs its import-time setup)
and then behaves as v0 did
"""
import pytest

from tests.v0._harness import run_python

V0_NAMES = (
    'OTEL_EXPORTER_OTLP_ENDPOINT', 'OTEL_EXPORTER_OTLP_HEADER', 'OTEL_EXPORTER_OTLP_INSECURE',
    'OTEL_EXPORTER_PROMETHEUS_ENDPOINT', 'OTEL_EXPORTER_PROMETHEUS_PORT', 'OTEL_HEADER_ATTRIBUTES', 'OTEL_LOG_LEVEL',
    'OTEL_SERVICE_NAME', 'OTEL_SERVICE_NAMESPACE', 'OTEL_WRAPPER_DISABLED',
    'instrument_all', 'instrument_dataclasses', 'instrument_decorate', 'instrument_fastapi_app', 'instrument_logging',
    'instrument_requests', 'instrument_sqlalchemy', 'instrument_sqlalchemy_engine', 'instrument_system_metrics',
)

# the child must not import `tests.impl`-style helpers that touch the package: only `emit` and sys.modules
IMPORTS_NO_V0 = r'''
import sys
{imports}
loaded = sorted(m for m in sys.modules if m.startswith('opentelemetry_wrapper.v0'))
emit('v0_modules', loaded)
emit('v1_loaded', 'opentelemetry_wrapper.v1' in sys.modules)
'''


@pytest.mark.parametrize('imports', ['import opentelemetry_wrapper', 'import opentelemetry_wrapper.v1',
                                     'from opentelemetry_wrapper import otel, OtelWrapperWarning, __version__'])
def test_importing_the_root_or_v1_imports_no_v0(imports):  # DEC-80
    result = run_python(IMPORTS_NO_V0.format(imports=imports))
    assert result['v0_modules'] == []
    assert result['v1_loaded'] is True


@pytest.mark.criterion('AC-26')
def test_the_root_exports_v1_s_otel_and_warning_class():  # DEC-46, DEC-80
    result = run_python('''
import opentelemetry_wrapper as root
import opentelemetry_wrapper.v1 as v1
emit('same', [root.otel is v1.otel, root.OtelWrapperWarning is v1.OtelWrapperWarning])
emit('version', isinstance(root.__version__, str) and bool(root.__version__))
emit('doc', bool(root.__doc__))
''')
    assert result['same'] == [True, True]
    assert result['version'] is True and result['doc'] is True


def test_v0_names_are_listed_in_all_and_dir_without_loading_v0():  # DEC-80
    result = run_python(f'''
import sys
import opentelemetry_wrapper as root
names = {V0_NAMES!r}
emit('all', sorted(set(names + ('__version__', 'otel', 'OtelWrapperWarning')) - set(root.__all__)))
emit('dir', sorted(set(names) - set(dir(root))))
emit('v0_loaded', any(m.startswith('opentelemetry_wrapper.v0') for m in sys.modules))
try:
    root.not_a_name
except AttributeError as e:
    emit('error', str(e))
''')
    assert result['all'] == [] and result['dir'] == []
    assert result['v0_loaded'] is False
    assert 'not_a_name' in result['error']


def test_every_v0_name_still_imports_from_the_root_and_loads_v0():  # DEC-80
    result = run_python(f'''
import sys
import opentelemetry_wrapper as root
assert not any(m.startswith('opentelemetry_wrapper.v0') for m in sys.modules)
got = {{}}
for name in {V0_NAMES!r}:
    exec(f'from opentelemetry_wrapper import {{name}} as value')
    got[name] = value
emit('names', sorted(got))
emit('v0_loaded', 'opentelemetry_wrapper.v0.config.otel_headers' in sys.modules)
from opentelemetry_wrapper.v0.config import otel_headers
from opentelemetry_wrapper.v0.dependencies.opentelemetry import instrument_decorator, instrument_sqlalchemy
emit('same_objects', [got['OTEL_SERVICE_NAME'] == otel_headers.OTEL_SERVICE_NAME,
                      got['instrument_decorate'] is instrument_decorator.instrument_decorate,
                      got['instrument_sqlalchemy_engine'] is instrument_sqlalchemy.instrument_sqlalchemy_engine,
                      all(callable(got[n]) for n in got if n.startswith('instrument_'))])
emit('instrument_all', [got['instrument_all'].__module__, got['instrument_all'].__name__,
                        got['instrument_all'] is root.instrument_all])
''')
    assert result['names'] == sorted(V0_NAMES)
    assert result['v0_loaded'] is True
    assert result['same_objects'] == [True, True, True, True]
    assert result['instrument_all'] == ['opentelemetry_wrapper', 'instrument_all', True]


@pytest.mark.parametrize('first', ['instrument_sqlalchemy_engine', 'OTEL_SERVICE_NAME', 'instrument_all'])
def test_any_v0_name_can_be_the_first_access(first):  # DEC-80: v0's own modules import names back from the root
    result = run_python(f'''
from opentelemetry_wrapper import {first}
emit('ok', {first} is not None)
''')
    assert result['ok'] is True


def test_v0_behaves_as_v0_when_reached_through_the_root():  # DEC-80
    result = run_python('''
import logging
from opentelemetry import trace
from opentelemetry_wrapper import instrument_decorate, instrument_all
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

exporter = InMemorySpanExporter()
trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(exporter))  # v0's import installed the provider


@instrument_decorate
def f(x):
    return x + 1


assert f(1) == 2
instrument_all(requests=False, system_metrics=False, dataclasses=False)
spans = exporter.get_finished_spans()
emit('spans', [s.name for s in spans])
by_name = {s.name: s for s in spans}
emit('instrument_all_span_namespace', by_name['<opentelemetry_wrapper>.instrument_all'].attributes['code.namespace'])
''')
    assert '<opentelemetry_wrapper>.instrument_all' in result['spans']  # the name it had when the root defined it
    assert any(name.endswith('.f') for name in result['spans'])
    assert result['instrument_all_span_namespace'] == 'opentelemetry_wrapper'  # as when the root defined it
