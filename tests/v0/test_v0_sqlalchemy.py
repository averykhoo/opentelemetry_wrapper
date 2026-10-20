"""
`instrument_sqlalchemy_engine` / `instrument_sqlalchemy` with sqlite in-memory engines

`SQLAlchemyInstrumentor` is a process-wide singleton (and its first instrument() patches create_engine), so every
scenario runs in a fresh interpreter. async engines are not covered here: v1's are, against aiosqlite, in
tests/v1/test_v1_sqlalchemy.py

the scenarios run against `otel.instrument(engine)` / `otel.instrument(sqlalchemy)` (OTW-4). v1 attaches its own
tracer to each engine, so an engine passed in gets query spans but no `connect` spans, which come only from the
global call (DEC-1; v0's per-engine call also instrumented globally, so it had them). the tests that claim AC-9 pin
the v0 engine bugs v1 fixes (v1's own tests: `tests/v1/test_v1_sqlalchemy.py`)
"""
import pytest

from tests.v0._harness import scenario

pytest.importorskip('sqlalchemy')

ONE_ENGINE = scenario(__name__, 'sqlalchemy_one_engine', r'''
from sqlalchemy import create_engine, text
from tests.impl import instrument_engine
exp = setup_spans()

engine = create_engine('sqlite:///:memory:')
emit('returns_same_engine', instrument_engine(engine) is engine)
emit('second_call_returns_same_engine', instrument_engine(engine) is engine)
emit('non_engine_passthrough', instrument_engine('not an engine'))
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
from tests.impl import instrument_engine
exp = setup_spans()

# both engines exist before either is instrumented (the usual case: engines are module-level globals)
e1 = create_engine('sqlite:///:memory:')
e2 = create_engine('sqlite:///file:e2?mode=memory&uri=true')
instrument_engine(e1)
instrument_engine(e2)
take(exp)
for key, engine in (('e1', e1), ('e2', e2)):
    with engine.connect() as conn:
        conn.execute(text('SELECT 1')).fetchall()
    emit(key, take(exp))
''')

GLOBAL = scenario(__name__, 'sqlalchemy_global', r'''
import sqlalchemy
from sqlalchemy import create_engine as create_engine_imported_early, text
from tests.impl import instrument_sqlalchemy
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
from tests import impl
impl.load()
from sqlalchemy import create_engine, text
exp = setup_spans()
engine = create_engine('sqlite:///:memory:')
try:
    impl.instrument_engine(engine)
except Exception as e:
    emit('instrument_error', f'{type(e).__name__}: {e}')
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


def test_instrumenting_returns_the_engine_and_ignores_non_engines(one_engine):
    assert one_engine['returns_same_engine'] is True
    assert one_engine['second_call_returns_same_engine'] is True
    assert one_engine['non_engine_passthrough'] == 'not an engine'


def test_query_spans(one_engine):
    # CLAUDE.md § Gate, outside the gate: sqlalchemy_example.py -> `connect` + `SELECT :memory:` spans
    assert one_engine['rows'] == 0
    records = one_engine['first_query']
    assert names(records) == ['SELECT :memory:']
    select = records[-1]
    assert select['kind'] == 'CLIENT'
    assert select['attributes']['db.system'] == 'sqlite'
    assert select['attributes']['db.statement'].startswith('SELECT * FROM sqlite_master')


def test_instrumenting_twice_gives_one_span_per_query(one_engine):
    assert names(one_engine['two_more_queries']) == ['SELECT :memory:', 'SELECT :memory:']


@pytest.fixture(scope='module')
def two_engines():
    return TWO_ENGINES.result()


def test_first_of_two_engines_is_traced(two_engines):
    assert names(two_engines['e1']) == ['SELECT :memory:']


# v0 bug list "Only the first sqlalchemy engine gets traced": SQLAlchemyInstrumentor is a singleton, so v0's second
# instrument_sqlalchemy_engine() call was a no-op
@pytest.mark.criterion('AC-9')
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
    assert names(global_result['created_after_via_early_import']) == ['connect']


# v0 bug (v0 bug list, 2nd section): without sqlalchemy.ext.asyncio, upstream's instrument() raised, and v0 did not
# catch it ("never crash")
@pytest.mark.criterion('AC-9')
def test_instrumenting_without_the_asyncio_extension_does_not_crash_and_traces():
    result = NO_ASYNCIO_EXTENSION.result()
    assert result.values.get('instrument_error') is None
    assert result['spans'] == ['SELECT :memory:']
