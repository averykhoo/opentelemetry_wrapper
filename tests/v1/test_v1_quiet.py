"""
AC-22, the first clause: our own entry points emit no spans and no logs at runtime. Every public entry point runs in
turn in one scenario, with an in-memory span sink, an in-memory log sink and a root `logging` handler that keeps what
reaches `logging` from the wrapper's own loggers; after each step the spans and logs that appeared are counted. The
spans the user asked for (a call to a decorated function, a `with otel` block) are the only spans allowed, one each.
"""
import pytest

from tests.v0._harness import scenario
from tests.v1._prelude import PRELUDE

pytest.importorskip('fastapi')
pytest.importorskip('sqlalchemy')

QUIET = scenario(__name__, 'v1_quiet', PRELUDE + r'''
import asyncio
import logging

from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter

log_exporter = InMemoryLogRecordExporter()
_config.add_log_sink(log_exporter)


class Own(logging.Handler):
    """what reaches `logging` from our own loggers (the wrapper's package name)"""
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.records = []

    def emit(self, record):
        if record.name.startswith('opentelemetry_wrapper'):
            self.records.append(record.getMessage())


own = Own()
logging.getLogger().addHandler(own)
logging.getLogger().setLevel(logging.DEBUG)
seen = {'spans': 0, 'logs': 0, 'own': 0}
steps = {}


def step(name):
    """the spans, log records and own `logging` records this step added"""
    _config.logger_provider().force_flush()
    spans = [s.name for s in exporter.get_finished_spans()][seen['spans']:]
    logs = [r.log_record.body for r in log_exporter.get_finished_logs()][seen['logs']:]
    mine = own.records[seen['own']:]
    seen.update(spans=seen['spans'] + len(spans), logs=seen['logs'] + len(logs), own=seen['own'] + len(mine))
    steps[name] = {'spans': spans, 'logs': logs, 'own': mine}


with warnings.catch_warnings():
    warnings.simplefilter('error')  # the entry points must also be quiet in warnings, and nothing here may raise
    otel.configure(service_name='quiet')
    step('configure')

    otel.instrument(logging)
    step('instrument_logging')
    otel.instrument()
    step('instrument_all')

    from fastapi import FastAPI
    from sqlalchemy import create_engine
    otel.instrument(FastAPI())
    step('instrument_app')
    otel.instrument(create_engine('sqlite:///:memory:'))
    step('instrument_engine')

    @otel
    def decorated(x):
        return x + 1

    @otel(name='named')
    def decorated_with_arguments(x):
        return x + 1

    @otel
    async def decorated_async(x):
        return x + 1

    @otel
    def decorated_generator():
        yield 1

    def plain():
        return 1

    instrumented = otel.instrument(plain)
    step('decoration')

    decorated(1)
    step('call_decorated')
    decorated_with_arguments(1)
    step('call_decorated_with_arguments')
    asyncio.run(decorated_async(1))
    step('call_decorated_async')
    list(decorated_generator())
    step('call_decorated_generator')
    instrumented()
    step('call_instrumented_function')

    with otel('block'):
        pass
    step('with_named')
    with otel as span:
        pass
    step('with_unnamed')
    with otel('outer'):
        with otel('inner'):
            pass
    step('with_nested')
emit('steps', steps)
''')

SILENT_STEPS = ['configure', 'instrument_logging', 'instrument_all', 'instrument_app', 'instrument_engine', 'decoration']
# step -> the spans the user asked for: exactly one span per call or block, named as the user named it
ASKED_FOR = {
    'call_decorated': ['__main__.decorated'],
    'call_decorated_with_arguments': ['named'],
    'call_decorated_async': ['__main__.decorated_async'],
    'call_decorated_generator': ['__main__.decorated_generator'],
    'call_instrumented_function': ['__main__.plain'],
    'with_named': ['block'],
    'with_unnamed': ['__main__.<module>'],
    'with_nested': ['inner', 'outer'],
}


@pytest.mark.criterion('AC-22')
@pytest.mark.parametrize('name', SILENT_STEPS)
def test_an_entry_point_that_starts_nothing_emits_no_span_and_no_log(name):  # AC-22
    step = QUIET.result()['steps'][name]
    assert step == {'spans': [], 'logs': [], 'own': []}


@pytest.mark.criterion('AC-22')
@pytest.mark.parametrize('name', list(ASKED_FOR))
def test_a_call_or_a_block_emits_only_the_span_the_user_asked_for_and_no_log(name):  # AC-22
    step = QUIET.result()['steps'][name]
    assert step['spans'] == ASKED_FOR[name]
    assert step['logs'] == [] and step['own'] == []
