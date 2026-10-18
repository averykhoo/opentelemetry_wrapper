"""
two asyncio tasks plus a thread, interleaved ("Public API notes", `docs/evidence/v1-design-evidence-2026-10-18.md`)

the sketch's `with otel:` kept one shared span stack, so with task A entering first and exiting first, A's exit ended
B's span. `check_interleaving` forces exactly that order: A enters, B enters, a thread enters and exits while both are
inside, A exits, then B. for each, the span it exits must be the one it entered, a task's span must not be a child of
the other task's, and the thread's span must not be a child of either. it takes any `name -> context manager`
factory: the OTel tracer's `start_as_current_span` here (what v1's `ContextVar` design rests on), the shared-stack
sketch as the known-bad control, and v1's `with otel:` once it is bound in `tests/impl.py`
"""
import asyncio
import threading

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


@pytest.fixture
def tracer_and_exporter():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    yield provider.get_tracer('interleaving'), exporter
    provider.shutdown()


def check_interleaving(span_cm, exporter):
    """`span_cm(name)` opens a span named `name`; fails with an AssertionError naming what went wrong"""
    finished_at_exit = {}

    def finished():
        return {s.name for s in exporter.get_finished_spans()}

    def in_thread():
        with span_cm('T'):
            pass
        finished_at_exit['T'] = finished()

    async def task_a(a_entered, b_entered, a_exited):
        with span_cm('A'):
            a_entered.set()
            await b_entered.wait()
            thread = threading.Thread(target=in_thread)
            thread.start()
            thread.join()
        finished_at_exit['A'] = finished()
        a_exited.set()

    async def task_b(a_entered, b_entered, a_exited):
        await a_entered.wait()
        with span_cm('B'):
            b_entered.set()
            await a_exited.wait()
        finished_at_exit['B'] = finished()

    async def main():
        a_entered, b_entered, a_exited = asyncio.Event(), asyncio.Event(), asyncio.Event()
        await asyncio.gather(task_a(a_entered, b_entered, a_exited), task_b(a_entered, b_entered, a_exited))

    asyncio.run(main())

    assert finished_at_exit['T'] == {'T'}, f'the thread ended {finished_at_exit["T"] - {"T"}} as well as its own span'
    assert finished_at_exit['A'] == {'T', 'A'}, f'task A ended {finished_at_exit["A"] - {"T"}}, not its own span'
    assert finished_at_exit['B'] == {'T', 'A', 'B'}
    spans = {s.name: s for s in exporter.get_finished_spans()}
    names_by_id = {s.context.span_id: name for name, s in spans.items()}
    parents = {name: names_by_id.get(s.parent.span_id) if s.parent else None for name, s in spans.items()}
    assert parents['A'] != 'B' and parents['B'] != 'A', f'one task span is a child of the other: {parents}'
    assert parents['T'] not in ('A', 'B'), f'the thread span is a child of a task span: {parents}'


class SharedStackSketch:
    """the sketch's design (`next_version_intended_usage.py`): one module-level object, one shared span stack"""

    def __init__(self, tracer):
        self.tracer = tracer
        self.spans = []

    def __call__(self, name):
        self.name = name
        return self

    def __enter__(self):
        parent = trace.set_span_in_context(self.spans[-1]) if self.spans else None
        self.spans.append(self.tracer.start_span(self.name, context=parent))
        return self

    def __exit__(self, *exc_info):
        self.spans.pop().end()


def test_the_otel_tracer_keeps_interleaved_spans_apart(tracer_and_exporter):
    tracer, exporter = tracer_and_exporter
    check_interleaving(tracer.start_as_current_span, exporter)


def test_the_check_catches_a_shared_span_stack(tracer_and_exporter):
    tracer, exporter = tracer_and_exporter
    with pytest.raises(AssertionError, match='ended'):
        check_interleaving(SharedStackSketch(tracer), exporter)
