"""
the package root is v1 (DEC-46). v0 was deleted at 1.0.0 (DEC-96): its functions are warn-once aliases onto v1
(tests/v1/test_v1_aliases.py), and its configuration values are gone
"""
import pytest

from tests.v0._harness import run_python

V0_FUNCTIONS = (
    'instrument_all', 'instrument_dataclasses', 'instrument_decorate', 'instrument_fastapi_app', 'instrument_logging',
    'instrument_requests', 'instrument_sqlalchemy', 'instrument_sqlalchemy_engine', 'instrument_system_metrics',
)
V0_VALUES = (
    'OTEL_EXPORTER_OTLP_ENDPOINT', 'OTEL_EXPORTER_OTLP_HEADER', 'OTEL_EXPORTER_OTLP_INSECURE',
    'OTEL_EXPORTER_PROMETHEUS_ENDPOINT', 'OTEL_EXPORTER_PROMETHEUS_PORT', 'OTEL_HEADER_ATTRIBUTES', 'OTEL_LOG_LEVEL',
    'OTEL_SERVICE_NAME', 'OTEL_SERVICE_NAMESPACE', 'OTEL_WRAPPER_DISABLED',
)


@pytest.mark.criterion('AC-26')
def test_the_root_exports_v1_s_otel_and_warning_class():  # DEC-46
    result = run_python('''
import opentelemetry_wrapper as root
import opentelemetry_wrapper.v1 as v1
emit('same', [root.otel is v1.otel, root.OtelWrapperWarning is v1.OtelWrapperWarning])
emit('version', isinstance(root.__version__, str) and bool(root.__version__))
emit('doc', bool(root.__doc__))
''')
    assert result['same'] == [True, True]
    assert result['version'] is True and result['doc'] is True


HEAVY = ('fastapi', 'starlette', 'sqlalchemy', 'requests', 'pydantic', 'grpc', 'psutil')


def test_v0_is_gone_and_importing_the_root_configures_and_imports_nothing():  # DEC-96, DEC-27
    result = run_python(f'''
import importlib.util
import logging
import sys
handlers = list(logging.getLogger().handlers)
import opentelemetry_wrapper as root
from opentelemetry import trace
from opentelemetry_wrapper.v1 import _config
emit('v0', importlib.util.find_spec('opentelemetry_wrapper.v0') is not None)
emit('configured', [_config._state is not None, type(trace.get_tracer_provider()).__name__,
                    logging.getLogger().handlers == handlers])
emit('heavy', sorted(m for m in sys.modules if m.split('.')[0] in {HEAVY!r}))
emit('all', sorted(root.__all__))
emit('dir', sorted(set(root.__all__) - set(dir(root))))
''')
    assert result['v0'] is False
    assert result['configured'] == [False, 'ProxyTracerProvider', True]
    assert result['heavy'] == []  # installed here, but importing the package imports none of them
    assert result['all'] == sorted(('__version__', 'otel', 'OtelWrapperWarning') + V0_FUNCTIONS)
    assert result['dir'] == []


def test_v0_s_configuration_values_are_gone_with_a_pointer_to_the_environment():  # DEC-96
    result = run_python(f'''
import opentelemetry_wrapper as root
errors = {{}}
for name in {V0_VALUES!r}:
    try:
        getattr(root, name)
    except AttributeError as e:
        errors[name] = str(e)
try:
    root.not_a_name
except AttributeError as e:
    errors['not_a_name'] = str(e)
emit('errors', errors)
''')
    errors = result['errors']
    assert sorted(errors) == sorted(V0_VALUES + ('not_a_name',))
    for name in V0_VALUES:
        assert f'os.environ[{name!r}]' in errors[name] and 'removed in 1.0.0' in errors[name], errors[name]
    assert errors['not_a_name'] == "module 'opentelemetry_wrapper' has no attribute 'not_a_name'"
