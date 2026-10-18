"""
the OTW_IMPL adapter itself (`tests/impl.py`)
"""
import pytest

from tests import impl
from tests.v0._harness import run_python

V0_NAMES = {
    'decorate':                  'instrument_decorate',
    'instrument_app':            'instrument_fastapi_app',
    'instrument_engine':         'instrument_sqlalchemy_engine',
    'setup':                     'instrument_all',
    'instrument_logging':        'instrument_logging',
    'instrument_requests':       'instrument_requests',
    'instrument_dataclasses':    'instrument_dataclasses',
    'instrument_sqlalchemy':     'instrument_sqlalchemy',
    'instrument_system_metrics': 'instrument_system_metrics',
}


@pytest.mark.parametrize('value', ['v0', 'v1'])
def test_selected_impl_accepts_v0_and_v1(value):
    assert impl.selected_impl({'OTW_IMPL': value}) == value


@pytest.mark.parametrize('environ', [{}, {'OTW_IMPL': ''}])
def test_selected_impl_defaults_to_v0(environ):
    assert impl.selected_impl(environ) == 'v0'


@pytest.mark.parametrize('value', ['v2', 'V0', 'v0 ', 'latest'])
def test_selected_impl_rejects_other_values(value):
    with pytest.raises(ValueError, match='OTW_IMPL'):
        impl.selected_impl({'OTW_IMPL': value})


def test_a_bad_otw_impl_fails_on_import():
    result = run_python('import tests.impl', env={'OTW_IMPL': 'v2'})
    assert result.returncode != 0
    assert "OTW_IMPL='v2' is not valid" in result.stderr


def test_unknown_names_are_attribute_errors():
    with pytest.raises(AttributeError):
        impl.not_a_name


@pytest.mark.skipif(impl.IMPL != 'v0', reason='binds the v0 names')
def test_v0_names_resolve_to_the_v0_objects():
    import opentelemetry_wrapper
    for name, v0_name in V0_NAMES.items():
        assert getattr(impl, name) is getattr(opentelemetry_wrapper, v0_name), name
    assert impl.__version__ == opentelemetry_wrapper.__version__
    # the root's `__all__` (DEC-80: v1's names plus every v0 name, `instrument_system_metrics` and the OTEL_* included),
    # in neutral names
    assert set(impl.__all__) >= set(V0_NAMES) | {'__version__', 'otel', 'OtelWrapperWarning', 'OTEL_SERVICE_NAME'}


@pytest.mark.skipif(impl.IMPL != 'v1', reason='binds the v1 names')
def test_v1_names_bind_to_v1_or_fail_clearly_when_used():
    for name in set(V0_NAMES) - {'instrument_dataclasses'}:
        assert callable(getattr(impl, name)), name
    # dropped in v1 (PLAN "Global dataclass instrumentation is dropped"), and v1 has no version or __all__ of its own
    with pytest.raises(NotImplementedError, match='instrument_dataclasses.*OTW_IMPL=v1'):
        impl.instrument_dataclasses()
    with pytest.raises(NotImplementedError, match='OTW_IMPL=v1'):
        impl.__version__


def test_import_v1_imports_no_v0():
    result = run_python('''
import sys
from tests.impl import import_v1
v1 = import_v1()
emit('v0_imported', any(m.startswith('opentelemetry_wrapper.v0') for m in sys.modules))
emit('has_otel', hasattr(v1, 'otel'))
''')
    assert result['v0_imported'] is False
    assert result['has_otel'] is True
