"""
canary: a tracer obtained before any provider is set is the API's `ProxyTracer`, which picks up the provider set
later; contrib instrumentors created before configuration rely on it, which is why instrumenting before configuring
loses nothing (DEC-27, configuration rule 2). sets the global provider, so it runs in a fresh interpreter
"""
import pytest

from tests.v0._harness import ASGI_HELPER_SOURCE
from tests.v0._harness import scenario

pytest.importorskip('fastapi')

PROXY = scenario(__name__, 'upstream_proxy_tracer', ASGI_HELPER_SOURCE + r'''
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

early = trace.get_tracer('canary.early')
emit('early_is_proxy', isinstance(early, trace.ProxyTracer))

app = FastAPI()

@app.get('/hello')
def hello():
    return 'hello'

FastAPIInstrumentor.instrument_app(app)  # before any provider

exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
trace.set_tracer_provider(provider)

with early.start_as_current_span('from the early tracer'):
    pass
emit('status', asgi_request(app, '/hello').status)
emit('spans', sorted(s.name for s in exporter.get_finished_spans()))
''')


def test_a_tracer_from_before_the_provider_is_a_proxy():
    assert PROXY.result()['early_is_proxy'] is True


def test_the_proxy_tracer_records_once_a_provider_is_set():
    assert 'from the early tracer' in PROXY.result()['spans']


def test_an_instrumentor_from_before_the_provider_records_once_it_is_set():
    result = PROXY.result()
    assert result['status'] == 200
    assert 'GET /hello' in result['spans'], result['spans']
