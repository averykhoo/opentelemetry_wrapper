"""
the adapter itself (`tests/impl.py`)
"""
from tests import impl
from tests.v0._harness import run_python

NEUTRAL_NAMES = ('decorate', 'instrument_app', 'instrument_engine', 'setup', 'instrument_logging',
                 'instrument_requests', 'instrument_sqlalchemy', 'instrument_system_metrics', 'span_exporter', 'load')


def test_the_neutral_names_are_callable():
    for name in NEUTRAL_NAMES:
        assert callable(getattr(impl, name)), name
    assert not hasattr(impl, 'instrument_dataclasses')  # dropped in v1 (DEC-42)


def test_importing_the_adapter_imports_no_package():
    # scenarios care about what is imported when: the package is imported by the first call, never by the import
    result = run_python('''
import sys
import tests.impl
emit('imported', sorted(m for m in sys.modules if m.startswith('opentelemetry_wrapper')))
''')
    assert result['imported'] == []
