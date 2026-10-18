"""
`instrument_sqlalchemy_engine` / `instrument_sqlalchemy` with sqlite in-memory engines

`SQLAlchemyInstrumentor` is a process-wide singleton (and its first instrument() patches create_engine), so every
scenario runs in a fresh interpreter. async engines are not covered: the only async sqlite driver (aiosqlite) is not
installed in the env
"""
import pytest

from tests.v0._harness import scenario

pytest.importorskip('sqlalchemy')

ONE_ENGINE = scenario(__name__, 'sqlalchemy_one_engine', r'''
from sqlalchemy import create_engine, text
from opentelemetry_wrapper import instrument_sqlalchemy_engine
from opentelemetry_wrapper.v0.dependencies.sqlalchemy.engine_typedef import (
    is_sqlalchemy_engine, is_sqlalchemy_sync_engine, is_sqlalchemy_async_engine)
exp = setup_spans()

engine = create_engine('sqlite:///:memory:')
emit('engine_type_checks', [is_sqlalchemy_engine(engine), is_sqlalchemy_sync_engine(engine),
                            is_sqlalchemy_async_engine(engine)])
emit('returns_same_engine', instrument_sqlalchemy_engine(engine) is engine)
emit('second_call_returns_same_engine', instrument_sqlalchemy_engine(engine) is engine)
emit('non_engine_passthrough', instrument_sqlalchemy_engine('not an engine'))
take(exp)

with engine.connect() as conn:
    rows = conn.execute(text('SELECT * FROM sqlite_master')).fetchall()
    emit('rows', len(rows))
emit('first_query', take(exp))
with engine.connect() as conn:
    conn.execute(text('SELECT 1')).fetchall()
    conn.execute(text('SELECT 2')).fetchall()
emit('two_more_queries', take(exp))
''')

TWO_ENGINES = scenario(__name__, 'sqlalchemy_two_engines', r'''
from sqlalchemy import create_engine, text
from opentelemetry_wrapper import instrument_sqlalchemy_engine
exp = setup_spans()

# both engines exist before either is instrumented (the usual case: engines are module-level globals)
e1 = create_engine('sqlite:///:memory:')
e2 = create_engine('sqlite:///file:e2?mode=memory&uri=true')
instrument_sqlalchemy_engine(e1)
instrument_sqlalchemy_engine(e2)
take(exp)
for key, engine in (('e1', e1), ('e2', e2)):
    with engine.connect() as conn:
        conn.execute(text('SELECT 1')).fetchall()
    emit(key, take(exp))
''')

GLOBAL = scenario(__name__, 'sqlalchemy_global', r'''
import sqlalchemy
from sqlalchemy import create_engine as create_engine_imported_early, text
from opentelemetry_wrapper import instrument_sqlalchemy
exp = setup_spans()

before = sqlalchemy.create_engine('sqlite://')
instrument_sqlalchemy()
instrument_sqlalchemy()
after = sqlalchemy.create_engine('sqlite://')
after_via_early_import = create_engine_imported_early('sqlite://')
take(exp)
for key, engine in (('created_after', after), ('created_before', before),
                    ('created_after_via_early_import', after_via_early_import)):
    with engine.connect() as conn:
        conn.execute(text('SELECT 1')).fetchall()
    emit(key, take(exp))
''')


NO_ASYNCIO_EXTENSION = scenario(__name__, 'sqlalchemy_no_asyncio_extension', r'''
import sys
sys.modules['sqlalchemy.ext.asyncio'] = None  # e.g. sqlalchemy 2.1 without greenlet: importing it fails
import opentelemetry_wrapper
from opentelemetry_wrapper.v0.dependencies.sqlalchemy.engine_typedef import (
    is_sqlalchemy_engine, is_sqlalchemy_sync_engine, is_sqlalchemy_async_engine)
from sqlalchemy import create_engine, text
exp = setup_spans()
engine = create_engine('sqlite:///:memory:')
emit('checks', [is_sqlalchemy_engine(engine), is_sqlalchemy_sync_engine(engine), is_sqlalchemy_async_engine(engine)])
try:
    opentelemetry_wrapper.instrument_sqlalchemy_engine(engine)
except Exception as e:
    emit('instrument_error', f'{type(e).__name__}: {e}')
take(exp)
with engine.connect() as conn:
    conn.execute(text('SELECT 1')).fetchall()
emit('spans', names(exp))
''')

DEPENDENCY_CONFLICT = scenario(__name__, 'sqlalchemy_dependency_conflict', r'''
import warnings
from opentelemetry_wrapper.v0.dependencies.opentelemetry import instrument_sqlalchemy as module
# simulate an installed sqlalchemy outside the instrumentation's supported range (e.g. 2.1, see DEC-62)
module.get_dependency_conflicts = lambda deps: ('DependencyConflict: requested: "sqlalchemy >= 1.0.0, < 2.1.0" '
                                                'but found: "sqlalchemy 2.1.3"')
import sqlalchemy
from sqlalchemy import text
from opentelemetry_wrapper import instrument_sqlalchemy, instrument_sqlalchemy_engine
exp = setup_spans()
engine = sqlalchemy.create_engine('sqlite://')
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    emit('returned_engine', instrument_sqlalchemy_engine(engine) is engine)
    instrument_sqlalchemy_engine(engine)
    instrument_sqlalchemy()
emit('warnings', [str(w.message) for w in caught])
take(exp)
with engine.connect() as conn:
    conn.execute(text('SELECT 1')).fetchall()
emit('spans', names(exp))
''')


def names(records):
    return [r['name'] for r in records]


@pytest.fixture(scope='module')
def one_engine():
    return ONE_ENGINE.result()


def test_engine_type_detection(one_engine):
    assert one_engine['engine_type_checks'] == [True, True, False]


def test_instrumenting_returns_the_engine_and_ignores_non_engines(one_engine):
    assert one_engine['returns_same_engine'] is True
    assert one_engine['second_call_returns_same_engine'] is True
    assert one_engine['non_engine_passthrough'] == 'not an engine'


def test_query_spans(one_engine):
    # CLAUDE.md § Gate, outside the gate: sqlalchemy_example.py -> `connect` + `SELECT :memory:` spans
    assert one_engine['rows'] == 0
    records = one_engine['first_query']
    assert names(records) == ['connect', 'SELECT :memory:']
    select = records[1]
    assert select['kind'] == 'CLIENT'
    assert select['attributes']['db.system'] == 'sqlite'
    assert select['attributes']['db.statement'].startswith('SELECT * FROM sqlite_master')


def test_instrumenting_twice_gives_one_span_per_query(one_engine):
    assert names(one_engine['two_more_queries']) == ['connect', 'SELECT :memory:', 'SELECT :memory:']


@pytest.fixture(scope='module')
def two_engines():
    return TWO_ENGINES.result()


def test_first_of_two_engines_is_traced(two_engines):
    assert names(two_engines['e1']) == ['connect', 'SELECT :memory:']


def test_connect_is_traced_for_every_engine(two_engines):
    # `connect` spans come from upstream's global connect patch, not from the per-engine tracer
    assert 'connect' in names(two_engines['e2'])


@pytest.mark.xfail(strict=True, reason='v0 bug list "Only the first sqlalchemy engine gets traced": '
                                       'SQLAlchemyInstrumentor is a singleton, so the second '
                                       'instrument_sqlalchemy_engine() call is a no-op (instrument_sqlalchemy.py:88)')
def test_second_of_two_engines_is_traced(two_engines):
    assert any(name.startswith('SELECT') for name in names(two_engines['e2']))


@pytest.fixture(scope='module')
def global_result():
    return GLOBAL.result()


def test_global_instrumentation_traces_engines_created_afterwards(global_result):
    assert names(global_result['created_after']) == ['connect', 'SELECT']


def test_global_instrumentation_does_not_trace_queries_of_engines_created_before(global_result):
    # upstream only patches create_engine; pre-existing engines get `connect` spans but no query spans
    assert names(global_result['created_before']) == ['connect']


def test_global_instrumentation_misses_create_engine_imported_before_it(global_result):
    # `from sqlalchemy import create_engine` before instrument_sqlalchemy() keeps the unpatched function
    # (same import-order caveat as instrument_dataclasses)
    assert names(global_result['created_after_via_early_import']) == ['connect']


def test_import_and_engine_detection_work_without_the_asyncio_extension():
    # the pre-adoption HANDOFF.md, "State" (docs/evidence/history-to-2026-10-18.md): a missing asyncio extension no
    # longer breaks `import opentelemetry_wrapper`
    result = NO_ASYNCIO_EXTENSION.result()
    assert result['checks'] == [True, True, False]


@pytest.mark.xfail(strict=True, reason='found while writing this suite (not in the v0 bug list; simulated with '
                                       'sys.modules["sqlalchemy.ext.asyncio"] = None): the upstream instrument() '
                                       'patches sqlalchemy.ext.asyncio and raises (wrapt TargetModuleNotFoundError), '
                                       'which instrument_sqlalchemy_engine does not catch ("never crash")')
def test_instrumenting_without_the_asyncio_extension_does_not_crash_and_traces():
    result = NO_ASYNCIO_EXTENSION.result()
    assert result.values.get('instrument_error') is None
    assert result['spans'] == ['connect', 'SELECT :memory:']


def test_unsupported_sqlalchemy_version_warns_once_and_skips_instrumenting():
    result = DEPENDENCY_CONFLICT.result()
    assert result['returned_engine'] is True
    (warning,) = result['warnings']
    assert warning.startswith('SQLAlchemy will NOT be traced')
    assert 'DependencyConflict' in warning
    assert result['spans'] == []
