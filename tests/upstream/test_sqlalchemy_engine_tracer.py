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
