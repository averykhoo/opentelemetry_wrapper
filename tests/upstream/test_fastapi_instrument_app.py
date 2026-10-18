"""
canary: `FastAPIInstrumentor.instrument_app` (the FastAPI notes under workstream 1 in `docs/archive/PLAN.md`):
`exclude_spans=['send', 'receive']` leaves only the server span, a second call on the same app neither raises nor
duplicates spans, and the app carries the `_is_instrumented_by_opentelemetry` flag the idempotent wrapper checks.
explicit providers, so nothing global is touched
"""
import pytest

from tests.v0._harness import asgi_request

pytest.importorskip('fastapi')


@pytest.fixture
def instrumented():
    from fastapi import FastAPI
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))
    meter_provider = MeterProvider()

    def build(**kwargs):
        app = FastAPI()

        @app.get('/hello')
        def hello():
            return 'hello'

        def instrument():
            FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider, meter_provider=meter_provider,
                                               **kwargs)

        return app, instrument

    yield build, exporter
    meter_provider.shutdown()
    tracer_provider.shutdown()


def _names(exporter):
    names = sorted(s.name for s in exporter.get_finished_spans())
    exporter.clear()
    return names


def test_without_exclude_spans_there_are_send_and_receive_spans(instrumented):
    # the control: proves the next test's `exclude_spans` is what removes them
    build, exporter = instrumented
    app, instrument = build()
    instrument()
    assert asgi_request(app, '/hello').status == 200
    names = _names(exporter)
    assert 'GET /hello' in names
    assert len(names) > 1, names


def test_exclude_spans_leaves_only_the_server_span(instrumented):
    build, exporter = instrumented
    app, instrument = build(exclude_spans=['send', 'receive'])
    instrument()
    assert asgi_request(app, '/hello').status == 200
    assert _names(exporter) == ['GET /hello']


def test_instrumenting_twice_neither_raises_nor_duplicates_spans(instrumented):
    build, exporter = instrumented
    app, instrument = build(exclude_spans=['send', 'receive'])
    instrument()
    instrument()
    assert getattr(app, '_is_instrumented_by_opentelemetry', None) is True
    assert asgi_request(app, '/hello').status == 200
    assert _names(exporter) == ['GET /hello']
