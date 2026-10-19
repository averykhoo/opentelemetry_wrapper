"""
canary: `EngineTracer`, the per-engine half of `SQLAlchemyInstrumentor` (DEC-1, the SQLAlchemy evidence in
`docs/evidence/v1-design-evidence-2026-10-18.md`)

`SQLAlchemyInstrumentor().instrument(engine=e)` only traces engines created after its first call, so v1 attaches an
`EngineTracer` to each engine itself. it lives in a non-`__init__` module and is not documented api, so an upgrade
that moves it, changes its signature or stops it producing query spans must fail here. each scenario runs in a fresh
interpreter: the instrumentor is a process-wide singleton and patches `create_engine` and `connect`
"""
import pytest

from tests.v0._harness import scenario

pytest.importorskip('sqlalchemy')

_SETUP = r'''
from opentelemetry.metrics import get_meter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from sqlalchemy import create_engine, text

exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
tracer = provider.get_tracer('canary')
# what upstream's `_instrument` passes as `connections_usage`
connections_usage = get_meter('canary').create_up_down_counter(
    name='db.client.connections.usage', unit='connections', description='canary')

def query(engine, sql='SELECT 1'):
    exporter.clear()
    with engine.connect() as conn:
        conn.execute(text(sql)).fetchall()
    return [s.name for s in sorted(exporter.get_finished_spans(), key=lambda s: s.start_time)]
'''

IMPORT_PATHS = scenario(__name__, 'upstream_engine_tracer_import', r'''
import inspect
from opentelemetry.instrumentation.sqlalchemy import EngineTracer as from_package
from opentelemetry.instrumentation.sqlalchemy.engine import EngineTracer
emit('same_class', from_package is EngineTracer)
emit('params', list(inspect.signature(EngineTracer.__init__).parameters)[1:4])
''')

PRE_EXISTING_ENGINES = scenario(__name__, 'upstream_engine_tracer_pre_existing', _SETUP + r'''
from opentelemetry.instrumentation.sqlalchemy.engine import EngineTracer

e1 = create_engine('sqlite:///:memory:')
e2 = create_engine('sqlite:///:memory:')
EngineTracer(tracer, e1, connections_usage)
EngineTracer(tracer, e2, connections_usage)
emit('e1', query(e1))
emit('e2', query(e2))
EngineTracer(tracer, e1, connections_usage)  # a second tracer on the same engine
emit('e1_twice', query(e1))
emit('untraced', query(create_engine('sqlite:///:memory:')))
''')

CONNECT_SPANS = scenario(__name__, 'upstream_engine_tracer_connect', _SETUP + r'''
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.sqlalchemy.engine import EngineTracer

engine = create_engine('sqlite:///:memory:')  # exists before instrument()
EngineTracer(tracer, engine, connections_usage)
emit('before_instrument', query(engine))
SQLAlchemyInstrumentor().instrument(tracer_provider=provider)
emit('after_instrument', query(engine))
''')


def _is_select(name):
    return name.upper().startswith('SELECT')


def test_engine_tracer_import_path_and_signature():
    assert IMPORT_PATHS.result()['same_class'] is True
    assert IMPORT_PATHS.result()['params'] == ['tracer', 'engine', 'connections_usage']


def test_engine_tracer_traces_engines_that_already_exist():
    result = PRE_EXISTING_ENGINES.result()
    for key in ('e1', 'e2'):
        assert [n for n in result[key] if _is_select(n)] != [], (key, result[key])
    assert result['untraced'] == []


def test_a_second_engine_tracer_does_not_duplicate_spans():
    # how (read in 0.65b0's source): each tracer stores its span on the execution context as `_otel_span`, so the
    # later one overwrites the earlier one's, which is then never ended or exported. v1 tracks engines in a WeakSet
    # instead of relying on this
    result = PRE_EXISTING_ENGINES.result()
    assert len([n for n in result['e1_twice'] if _is_select(n)]) == 1, result['e1_twice']


def test_connect_spans_come_from_the_instrumentor_not_the_engine_tracer():
    result = CONNECT_SPANS.result()
    assert 'connect' not in result['before_instrument'], result['before_instrument']
    assert 'connect' in result['after_instrument'], result['after_instrument']
    assert len([n for n in result['after_instrument'] if _is_select(n)]) == 1, result['after_instrument']


# what `opentelemetry_wrapper.v1._instrument` reads of upstream besides `EngineTracer` (OTW-4)

GLOBAL_TRACER_LISTENS = scenario(__name__, 'upstream_engine_tracer_listener', _SETUP + r'''
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.sqlalchemy.engine import EngineTracer

import sqlalchemy

before = sqlalchemy.create_engine('sqlite://')
SQLAlchemyInstrumentor().instrument(tracer_provider=provider)
after = sqlalchemy.create_engine('sqlite://')  # not `_SETUP`'s `create_engine`, imported before the patch


def tracers(engine):
    return [type(fn.__self__).__name__ for fn in engine.dispatch.before_cursor_execute
            if isinstance(getattr(fn, '__self__', None), EngineTracer)]


emit('before', tracers(before))
emit('after', tracers(after))
''')

NO_ASYNCIO_EXTENSION = scenario(__name__, 'upstream_instrumentor_no_asyncio_extension', r'''
import sys
sys.modules['sqlalchemy.ext.asyncio'] = None  # e.g. sqlalchemy 2.1 without greenlet: importing it fails
import sqlalchemy
from sqlalchemy.engine.base import Engine
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

instrumentor = SQLAlchemyInstrumentor()
try:
    instrumentor.instrument()
    emit('raised', None)
except ImportError as e:
    emit('raised', type(e).__name__)
emit('flag', [instrumentor.is_instrumented_by_opentelemetry, instrumentor._is_instrumented_by_opentelemetry])
emit('patched', [hasattr(sqlalchemy.create_engine, '__wrapped__'), hasattr(Engine.connect, '__wrapped__')])
instrumentor._is_instrumented_by_opentelemetry = True
emit('flag_after_setting', instrumentor.is_instrumented_by_opentelemetry)
''')

SCHEMA_URL = scenario(__name__, 'upstream_sqlalchemy_schema_url', _SETUP + r'''
from opentelemetry.instrumentation._semconv import _get_schema_url_for_signal_types
from opentelemetry.instrumentation._semconv import _OpenTelemetrySemanticConventionStability
from opentelemetry.instrumentation._semconv import _OpenTelemetryStabilitySignalType
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

_OpenTelemetrySemanticConventionStability._initialize()
emit('ours', _get_schema_url_for_signal_types([_OpenTelemetryStabilitySignalType.DATABASE,
                                               _OpenTelemetryStabilitySignalType.HTTP]))
import sqlalchemy
SQLAlchemyInstrumentor().instrument(tracer_provider=provider)
query(sqlalchemy.create_engine('sqlite://'))
emit('upstream', sorted({s.instrumentation_scope.schema_url for s in exporter.get_finished_spans()}))
''')


def test_an_engine_created_after_instrument_has_an_engine_tracer_among_its_query_listeners():
    # v1 reads this to skip a second tracer on an engine the global patch already traces
    result = GLOBAL_TRACER_LISTENS.result()
    assert result['before'] == []
    assert result['after'] == ['EngineTracer']


def test_without_the_asyncio_extension_instrument_raises_after_patching_the_sync_entry_points():
    # v1 then sets the flag itself, so a second call does not patch `create_engine` and `connect` twice
    result = NO_ASYNCIO_EXTENSION.result()
    assert result['raised'] is not None
    assert result['flag'] == [False, False]
    assert result['patched'] == [True, True]
    assert result['flag_after_setting'] is True


def test_the_schema_url_v1_computes_is_the_one_upstream_spans_carry():
    result = SCHEMA_URL.result()
    assert result['ours']
    assert result['upstream'] == [result['ours']]


CONNECTIONS_USAGE = scenario(__name__, 'upstream_sqlalchemy_connections_usage', r'''
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
import sqlalchemy
from sqlalchemy import text

reader = InMemoryMetricReader()
instrumentor = SQLAlchemyInstrumentor()
instrumentor.instrument(meter_provider=MeterProvider(metric_readers=[reader]))
with sqlalchemy.create_engine('sqlite://').connect() as conn:
    conn.execute(text('SELECT 1')).fetchall()
emit('metrics', [{'name': m.name, 'unit': m.unit, 'description': m.description}
                 for rm in reader.get_metrics_data().resource_metrics for sm in rm.scope_metrics
                 for m in sm.metrics])
emit('attribute', [name for name in vars(instrumentor) if 'usage' in name.lower()])
''')

OPTION_ENGINE = scenario(__name__, 'upstream_sqlalchemy_option_engine', _SETUP + r'''
from opentelemetry.instrumentation.sqlalchemy.engine import EngineTracer

parent = create_engine('sqlite://')
option = parent.execution_options(isolation_level='AUTOCOMMIT')
nested = option.execution_options(logging_token='nested')
emit('proxied', [option._proxied is parent, nested._proxied is option])
emit('same_pool', option.pool is parent.pool)
lonely_parent = create_engine('sqlite://')
lonely_option = lonely_parent.execution_options(isolation_level='AUTOCOMMIT')
EngineTracer(tracer, lonely_option, connections_usage)
emit('option_tracer_seen_from_parent', len(lonely_parent.dispatch.before_cursor_execute))
EngineTracer(tracer, parent, connections_usage)
emit('parent_tracer_seen_from_options', [len(e.dispatch.before_cursor_execute) for e in (option, nested)])
emit('spans', [query(e) for e in (option, nested)])
''')


def test_the_connections_usage_counter_is_a_local_of_instrument_with_this_identity():
    # v1 makes its own for an engine passed in (`SQLALCHEMY_CONNECTIONS_USAGE` in v1's `_instrument`), so a renamed
    # or re-described upstream metric must fail here; `tests/v1/test_v1_sqlalchemy.py` checks that the two are one
    result = CONNECTIONS_USAGE.result()
    assert result['metrics'] == [{
        'name': 'db.client.connections.usage', 'unit': 'connections',
        'description': 'The number of connections that are currently in state described by the state attribute.'}]
    assert result['attribute'] == []  # still not kept on the instrumentor, so there is nothing to fetch


def test_an_option_engine_joins_its_parents_dispatch_but_not_the_other_way_round():
    # v1 attaches the tracer to the root engine, found through `_proxied`, so an option engine and its parent share one
    result = OPTION_ENGINE.result()
    assert result['proxied'] == [True, True]
    assert result['same_pool'] is True
    assert result['option_tracer_seen_from_parent'] == 0
    assert result['parent_tracer_seen_from_options'] == [1, 1]
    for names in result['spans']:
        assert len([n for n in names if _is_select(n)]) == 1, result['spans']
