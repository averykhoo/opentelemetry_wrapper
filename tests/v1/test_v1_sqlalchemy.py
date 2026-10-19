"""
v1 SQLAlchemy (OTW-4, AC-9, DEC-1): `otel.instrument(sqlalchemy)` is global and reaches the engines created after it,
with `connect` spans; `otel.instrument(engine)` is that engine only, through its own `EngineTracer`, whether it
existed before or not, with query spans and no `connect` spans; both are idempotent and combine without a second
tracer on an engine (AC-6). an `AsyncEngine` is instrumented through its sync engine. without sqlalchemy's asyncio
extension sync engines are still instrumented; without the SQLAlchemy instrumentation, one warning and no crash

`SQLAlchemyInstrumentor` is a process-wide singleton that patches `create_engine` and `Engine.connect`, so every test
reads a scenario that ran in its own interpreter
"""
import pytest

from tests.v0._harness import scenario
from tests.v1._prelude import PRELUDE as V1_PRELUDE

pytest.importorskip('sqlalchemy')

PRELUDE = V1_PRELUDE + r'''
import sqlalchemy
from sqlalchemy import text


def query(engine, sql='SELECT 1'):
    """the names of the spans one connection and one query make, oldest first"""
    exporter.clear()
    with engine.connect() as conn:
        conn.execute(text(sql)).fetchall()
    return [s.name for s in sorted(exporter.get_finished_spans(), key=lambda s: s.start_time)]


def listeners(engine):
    """the query listeners on an engine: one per `EngineTracer` (a second one would leak a span per query)"""
    return len(engine.dispatch.before_cursor_execute)
'''

# aiosqlite (the async sqlite driver) is not installed here: this stands in for it, sqlite3 behind coroutines, enough
# for sqlalchemy's own `sqlite+aiosqlite` dialect, which then runs real queries through the asyncio extension
FAKE_AIOSQLITE = r'''
import sqlite3
import sys
import types

aiosqlite = types.ModuleType('aiosqlite')
for _name in ('DatabaseError', 'Error', 'IntegrityError', 'NotSupportedError', 'OperationalError',
              'ProgrammingError', 'sqlite_version', 'sqlite_version_info'):
    setattr(aiosqlite, _name, getattr(sqlite3, _name))


class _Cursor:
    def __init__(self, cursor):
        self._cursor = cursor

    description = property(lambda self: self._cursor.description)
    lastrowid = property(lambda self: self._cursor.lastrowid)
    rowcount = property(lambda self: self._cursor.rowcount)

    async def execute(self, *args):
        self._cursor.execute(*args)

    async def executemany(self, *args):
        self._cursor.executemany(*args)

    async def fetchall(self):
        return self._cursor.fetchall()

    async def fetchone(self):
        return self._cursor.fetchone()

    async def fetchmany(self, size=None):
        return self._cursor.fetchmany(size)

    async def close(self):
        self._cursor.close()


class _Connection:
    def __init__(self, conn):
        self._conn = conn

    isolation_level = property(lambda self: self._conn.isolation_level)

    async def cursor(self):
        return _Cursor(self._conn.cursor())

    async def create_function(self, *args, **kwargs):
        self._conn.create_function(*args, **kwargs)

    async def commit(self):
        self._conn.commit()

    async def rollback(self):
        self._conn.rollback()

    async def close(self):
        self._conn.close()


aiosqlite.Connection = _Connection
sys.modules['aiosqlite'] = aiosqlite


async def aiosqlite_creator():
    return _Connection(sqlite3.connect(':memory:', check_same_thread=False))
'''


def _selects(names):
    return [n for n in names if n.upper().startswith('SELECT')]


# ----------------------------------------------------------------------------------------------------------------------
# per engine: engines that already exist, and one created later
# ----------------------------------------------------------------------------------------------------------------------

PER_ENGINE = scenario(__name__, 'v1_sqlalchemy_per_engine', PRELUDE + r'''
e1 = sqlalchemy.create_engine('sqlite:///:memory:')  # both exist before anything is instrumented
e2 = sqlalchemy.create_engine('sqlite:///file:e2?mode=memory&uri=true')
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    returned = [otel.instrument(e1), otel.instrument(e2)]
    e3 = sqlalchemy.create_engine('sqlite://')  # created later, and passed in
    returned.append(otel.instrument(e3))
emit('returned', [r is e for r, e in zip(returned, (e1, e2, e3))])
emit('warnings', otel_warnings(caught))
emit('e1', query(e1))
emit('e2', query(e2))
emit('e3', query(e3))
emit('untraced', query(sqlalchemy.create_engine('sqlite://')))
query(e1)
emit('select_scope', [(s.instrumentation_scope.name, s.instrumentation_scope.schema_url)
                      for s in exporter.get_finished_spans()])
''')


@pytest.mark.criterion('AC-9')
def test_two_engines_that_already_exist_and_one_created_later_all_give_select_spans():  # AC-9
    r = PER_ENGINE.result()
    assert r['returned'] == [True, True, True]
    assert r['warnings'] == []
    for key in ('e1', 'e2', 'e3'):
        assert len(_selects(r[key])) == 1, (key, r[key])


@pytest.mark.criterion('AC-9')
def test_an_engine_passed_in_gives_no_connect_spans_and_others_stay_untraced():  # AC-9, DEC-1
    r = PER_ENGINE.result()
    for key in ('e1', 'e2', 'e3'):
        assert 'connect' not in r[key], (key, r[key])
    assert r['untraced'] == []


# ----------------------------------------------------------------------------------------------------------------------
# globally: `otel.instrument(sqlalchemy)`, alone and combined with engines passed in
# ----------------------------------------------------------------------------------------------------------------------

GLOBAL = scenario(__name__, 'v1_sqlalchemy_global', PRELUDE + r'''
before = sqlalchemy.create_engine('sqlite://')
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    returned = otel.instrument(sqlalchemy)
    otel.instrument(sqlalchemy)
    later = sqlalchemy.create_engine('sqlite://')  # never passed in
    both = sqlalchemy.create_engine('sqlite://')  # created later and also passed in
    emit('both_listeners_before', listeners(both))
    otel.instrument(both)
    otel.instrument(both)
emit('returned_module', returned is sqlalchemy)
emit('warnings', otel_warnings(caught))
emit('later', query(later))
emit('later_listeners', listeners(later))
emit('before_not_passed_in', query(before))
otel.instrument(before)
emit('before_passed_in', query(before))
emit('both', query(both))
emit('both_listeners', listeners(both))
global_scope = {(s.instrumentation_scope.name, s.instrumentation_scope.schema_url)
                for s in exporter.get_finished_spans() if s.name.startswith('SELECT')}
emit('global_select_scope', sorted(global_scope))
''')


@pytest.mark.criterion('AC-9')
def test_after_instrumenting_sqlalchemy_a_later_engine_never_passed_in_gives_connect_and_select_spans():  # AC-9
    r = GLOBAL.result()
    assert r['returned_module'] is True
    assert r['warnings'] == []
    assert r['later'] == ['connect', 'SELECT'], r['later']
    assert r['later_listeners'] == 1


@pytest.mark.criterion('AC-9')
def test_an_engine_that_existed_before_the_global_call_is_reached_once_passed_in():  # AC-9, DEC-1
    r = GLOBAL.result()
    # upstream's patch never reaches it (the documented constraint): `connect` only, from the class-level patch
    assert r['before_not_passed_in'] == ['connect'], r['before_not_passed_in']
    assert r['before_passed_in'] == ['connect', 'SELECT'], r['before_passed_in']


@pytest.mark.criterion('AC-9')
@pytest.mark.criterion('AC-6')
def test_an_engine_created_after_the_global_call_and_also_passed_in_keeps_one_tracer():  # AC-9, AC-6
    r = GLOBAL.result()
    assert r['both_listeners_before'] == 1
    assert r['both_listeners'] == 1
    assert r['both'] == ['connect', 'SELECT'], r['both']


def test_an_engine_passed_in_has_the_global_instrumentations_scope():  # DEC-1
    # same tracer name, version and schema url as upstream's own `_instrument`, so a backend sees one instrumentation
    per_engine = PER_ENGINE.result()['select_scope']
    assert per_engine and len(set(map(tuple, per_engine))) == 1, per_engine
    assert sorted(set(map(tuple, per_engine))) == [tuple(s) for s in GLOBAL.result()['global_select_scope']]


# ----------------------------------------------------------------------------------------------------------------------
# instrumenting an engine twice (also AC-6, test_v1_instrument.py)
# ----------------------------------------------------------------------------------------------------------------------

TWICE = scenario(__name__, 'v1_sqlalchemy_engine_twice', PRELUDE + r'''
import gc
import weakref
engine = sqlalchemy.create_engine('sqlite://')
otel.instrument(engine)
otel.instrument(engine)
names = query(engine, 'SELECT 1')
exporter.clear()
with engine.connect() as conn:
    conn.execute(text('SELECT 1')).fetchall()
    conn.execute(text('SELECT 2')).fetchall()
emit('one_query', names)
emit('two_queries', [s.name for s in exporter.get_finished_spans()])
emit('listeners', listeners(engine))
ref = weakref.ref(engine)
engine.dispose()
del engine, conn
gc.collect()
emit('engine_freed', ref() is None)
''')


@pytest.mark.criterion('AC-9')
@pytest.mark.criterion('AC-6')
def test_an_engine_instrumented_twice_gives_one_span_per_query():  # AC-9, AC-6
    r = TWICE.result()
    assert r['one_query'] == ['SELECT'], r['one_query']
    assert r['two_queries'] == ['SELECT', 'SELECT'], r['two_queries']
    assert r['listeners'] == 1


def test_an_instrumented_engine_is_not_kept_alive():  # DEC-1 (the WeakSet)
    assert TWICE.result()['engine_freed'] is True


# ----------------------------------------------------------------------------------------------------------------------
# AsyncEngine
# ----------------------------------------------------------------------------------------------------------------------

ASYNC_ENGINE_BODY = FAKE_AIOSQLITE + PRELUDE + r'''
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
INSTRUMENT_GLOBALLY = %r
if INSTRUMENT_GLOBALLY:
    otel.instrument(sqlalchemy)
engine = create_async_engine('sqlite+aiosqlite://', async_creator=aiosqlite_creator)
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    returned = otel.instrument(engine)
    otel.instrument(engine)
    otel.instrument(engine.sync_engine)  # the same engine, seen through its sync half
emit('returned_engine', returned is engine)
emit('warnings', otel_warnings(caught))
emit('listeners', listeners(engine.sync_engine))


async def main():
    exporter.clear()
    async with engine.connect() as conn:
        result = await conn.execute(text('SELECT 1'))
        rows = result.fetchall()
    await engine.dispose()
    return rows

emit('rows', [list(row) for row in asyncio.run(main())])
emit('spans', [s.name for s in sorted(exporter.get_finished_spans(), key=lambda s: s.start_time)])
'''
ASYNC_ENGINE = scenario(__name__, 'v1_sqlalchemy_async_engine', ASYNC_ENGINE_BODY % False)
ASYNC_ENGINE_GLOBAL = scenario(__name__, 'v1_sqlalchemy_async_engine_global', ASYNC_ENGINE_BODY % True)


@pytest.mark.criterion('AC-9')
def test_an_async_engine_gives_select_spans_once():  # AC-9
    r = ASYNC_ENGINE.result()
    assert r['returned_engine'] is True
    assert r['warnings'] == []
    assert r['rows'] == [[1]]
    assert r['spans'] == ['SELECT'], r['spans']
    assert r['listeners'] == 1


@pytest.mark.criterion('AC-9')
def test_an_async_engine_created_after_the_global_call_and_passed_in_keeps_one_tracer():  # AC-9, AC-6
    r = ASYNC_ENGINE_GLOBAL.result()
    assert r['warnings'] == []
    assert r['listeners'] == 1
    assert r['spans'] == ['connect', 'SELECT'], r['spans']


# ----------------------------------------------------------------------------------------------------------------------
# without sqlalchemy's asyncio extension (e.g. sqlalchemy 2.1 without greenlet)
# ----------------------------------------------------------------------------------------------------------------------

NO_ASYNCIO = scenario(__name__, 'v1_sqlalchemy_no_asyncio_extension', r'''
import sys
sys.modules['sqlalchemy.ext.asyncio'] = None  # importing it fails
''' + PRELUDE + r'''
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
before = sqlalchemy.create_engine('sqlite://')
raised = None
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    try:
        emit('returned_engine', otel.instrument(before) is before)
        otel.instrument(sqlalchemy)
        otel.instrument(sqlalchemy)  # must not patch create_engine and connect a second time
    except BaseException as e:
        raised = repr(e)
emit('raised', raised)
emit('warnings', otel_warnings(caught))
emit('flag', SQLAlchemyInstrumentor().is_instrumented_by_opentelemetry)
later = sqlalchemy.create_engine('sqlite://')
emit('before', query(before))
emit('later', query(later))
emit('later_listeners', listeners(later))
''')


@pytest.mark.criterion('AC-9')
def test_without_the_asyncio_extension_an_engine_passed_in_is_traced():  # AC-9
    r = NO_ASYNCIO.result()
    assert r['raised'] is None
    assert r['returned_engine'] is True
    assert r['before'] == ['connect', 'SELECT'], r['before']


@pytest.mark.criterion('AC-9')
def test_without_the_asyncio_extension_the_global_call_traces_later_sync_engines_once():  # AC-9, AC-6
    r = NO_ASYNCIO.result()
    assert r['warnings'] == []
    assert r['flag'] is True
    assert r['later'] == ['connect', 'SELECT'], r['later']
    assert r['later_listeners'] == 1


# ----------------------------------------------------------------------------------------------------------------------
# without the SQLAlchemy instrumentation (the `[sqlalchemy]` extra), and without sqlalchemy
# ----------------------------------------------------------------------------------------------------------------------

NO_INSTRUMENTATION = scenario(__name__, 'v1_sqlalchemy_no_instrumentation', r'''
import sys
for _name in ('opentelemetry.instrumentation.sqlalchemy', 'opentelemetry.instrumentation.sqlalchemy.engine'):
    sys.modules[_name] = None  # the extra is not installed: importing it fails
''' + PRELUDE + r'''
engine = sqlalchemy.create_engine('sqlite://')
raised = None
results = {}
for label, target in (('module', sqlalchemy), ('engine', engine)):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        try:
            results[label] = otel.instrument(target) is target
        except BaseException as e:
            raised = repr(e)
    emit(f'{label}_warnings', otel_warnings(caught))
emit('raised', raised)
emit('returned', results)
emit('spans', query(engine))
''')

NO_SQLALCHEMY = scenario(__name__, 'v1_sqlalchemy_not_installed', r'''
import sys
sys.modules['sqlalchemy'] = None  # not installed: importing it fails
''' + V1_PRELUDE + r'''
raised = None
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    try:
        otel.instrument()

        @otel
        def f():
            return 1

        emit('called', f())
    except BaseException as e:
        raised = repr(e)
emit('raised', raised)
emit('warnings', otel_warnings(caught))
emit('spans', [s.name for s in exporter.get_finished_spans()])
''')


@pytest.mark.criterion('AC-9')
@pytest.mark.criterion('AC-7')
def test_without_the_sqlalchemy_instrumentation_each_call_warns_once_and_returns_its_target():  # AC-9, AC-7
    r = NO_INSTRUMENTATION.result()
    assert r['raised'] is None
    assert r['returned'] == {'module': True, 'engine': True}
    for label in ('module', 'engine'):
        (warning,) = r[f'{label}_warnings']
        assert 'opentelemetry_wrapper[sqlalchemy]' in warning, warning
    assert r['spans'] == []


@pytest.mark.criterion('AC-9')
def test_without_sqlalchemy_otel_still_works_without_warnings():  # AC-9, DEC-11
    r = NO_SQLALCHEMY.result()
    assert r['raised'] is None
    assert r['called'] == 1
    assert r['warnings'] == []
    assert r['spans'] == ['__main__.f']


# ----------------------------------------------------------------------------------------------------------------------
# an unsupported sqlalchemy version (DEC-62): the global call warns, an engine passed in is still traced
# ----------------------------------------------------------------------------------------------------------------------

CONFLICT = scenario(__name__, 'v1_sqlalchemy_dependency_conflict', PRELUDE + r'''
from opentelemetry.instrumentation import dependencies


class FakeConflict:
    def __str__(self):
        return 'DependencyConflict: requested: "sqlalchemy >= 1.0.0, < 2.1.0" but found: "sqlalchemy 2.1.3"'


dependencies.get_dependency_conflicts = lambda *args, **kwargs: FakeConflict()
before = sqlalchemy.create_engine('sqlite://')
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    otel.instrument(sqlalchemy)
    otel.instrument(before)
emit('warnings', otel_warnings(caught))
emit('before', query(before))
emit('later', query(sqlalchemy.create_engine('sqlite://')))
''')


def test_an_unsupported_sqlalchemy_version_warns_on_the_global_call_but_engines_passed_in_are_traced():  # DEC-62
    r = CONFLICT.result()
    (warning,) = r['warnings']
    assert 'DependencyConflict' in warning and 'sqlalchemy was not instrumented' in warning, warning
    # `EngineTracer` attached directly skips upstream's dependency check (its hooks work on 2.1, DEC-62)
    assert r['before'] == ['SELECT'], r['before']
    assert r['later'] == [], r['later']
