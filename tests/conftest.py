"""
shared fixtures for the characterization suite

the suite pins down v0's *current* behaviour so that the v1 rewrite (see PLAN.md) can be checked against it
conventions:
* a plain test asserts what v0 does today, and is expected to hold for v1 too
* `@pytest.mark.xfail(strict=True, reason=...)` asserts the *correct* behaviour for a known v0 bug, so it starts
  failing-to-xfail (i.e. XPASS -> error) the moment the bug is fixed; then delete the marker
* `@pytest.mark.v0_specific` pins a v0 detail that PLAN.md intends to change (or that is an implementation detail),
  so a v1 run is expected to differ there; read those failures, don't blindly fix them
"""
import os
import sys
from pathlib import Path

# v0 reads its configuration from env vars at import time, so sanitise them before anything imports the package:
# no OTLP exporter (nothing must try to reach a collector), no prometheus port (nothing must bind :9464), not disabled
for _k in list(os.environ):
    if _k.upper().startswith('OTEL_'):
        del os.environ[_k]

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest  # noqa: E402

from tests.v0 import _harness  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line('markers', 'v0_specific: pins a v0 detail that v1 is expected to change (see PLAN.md)')


def pytest_collection_finish(session):
    # start every scenario (subprocess) needed by the selected tests, all in parallel
    if session.config.option.collectonly:
        return
    _harness.start_scenarios({item.module.__name__ for item in session.items if getattr(item, 'module', None)})


def pytest_sessionfinish(session, exitstatus):
    _harness.shutdown()


@pytest.fixture(scope='session')
def otw():
    """the public API of the package under test"""
    import opentelemetry_wrapper
    return opentelemetry_wrapper


@pytest.fixture(scope='session')
def _in_memory_exporter(otw):
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    # importing the package installs v0's global tracer provider (decorated functions get their tracer at import)
    from opentelemetry_wrapper.v0.dependencies.opentelemetry.otel_providers import init_tracer_provider
    init_tracer_provider()
    provider = trace.get_tracer_provider()
    assert isinstance(provider, TracerProvider), f'some other tracer provider got installed first: {provider!r}'

    _silence_console_span_exporters(provider)
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    yield exporter
    provider.force_flush()


def _silence_console_span_exporters(provider):
    """
    v0 always adds a batched ConsoleSpanExporter, whose background thread writes span json straight to the terminal
    (it bound sys.stdout before pytest's capture was involved); point it at a null stream for in-process tests.
    best effort, via SDK internals: if they change, the only cost is noisy output
    """
    import io
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter

    for processor in getattr(getattr(provider, '_active_span_processor', None), '_span_processors', ()):
        exporter = getattr(getattr(processor, '_batch_processor', None), '_exporter', None)
        if isinstance(exporter, ConsoleSpanExporter):
            exporter.out = io.StringIO()  # nothing reads it; replaced rather than closed so writes never fail


class SpanCapture:
    def __init__(self, exporter):
        self._exporter = exporter

    def clear(self):
        self._exporter.clear()

    def records(self, *, include_library_spans=False):
        """finished spans (oldest first) as dicts, see `tests/v0/_child.py:span_record`; clears the buffer"""
        from tests.v0._child import take
        return take(self._exporter, include_library_spans=include_library_spans)

    def names(self, **kwargs):
        return [s['name'] for s in self.records(**kwargs)]


@pytest.fixture
def spans(_in_memory_exporter):
    """
    in-process span capture; only safe for things that don't patch globals (function decoration, FastAPI apps,
    requests). class instrumentation is NOT safe in-process (see test_v0_classes.py)
    """
    _in_memory_exporter.clear()
    yield SpanCapture(_in_memory_exporter)
    _in_memory_exporter.clear()
