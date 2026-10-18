"""
the pytest plugin (DEC-27 rule 3, DEC-10): `otel_spans` / `otel_logs` capture exactly what would be exported (behind
the same scrubbing wrapper as the real exporters), reset per test

loading it is passive: it only registers the fixtures and an ini option. requesting a fixture opts that test in,
which switches our real exporters off for the test (by swapping the sinks of our processors, so it works after
configuration too); `otel_capture = true` in the ini file opts in the whole suite. the `pytest11` entry point that
loads it is packaging's (workstream 10); until then, `-p opentelemetry_wrapper.v1.pytest_plugin`. to keep it out:
`-p no:opentelemetry_wrapper`
"""
from typing import Any
from typing import Iterator
from typing import Optional

import pytest

INI_OPTION = 'otel_capture'

_span_exporter: Optional[Any] = None
_log_exporter: Optional[Any] = None
_whole_suite = False


def pytest_addoption(parser: Any) -> None:
    parser.addini(INI_OPTION, type='bool', default=False,
                  help='opentelemetry_wrapper: switch exporters off for the whole suite and capture spans and logs '
                       'in memory (otherwise only tests requesting otel_spans / otel_logs opt in)')


def pytest_configure(config: Any) -> None:
    global _whole_suite
    if config.getini(INI_OPTION):
        _whole_suite = True
        from opentelemetry_wrapper.v1 import _config
        _config.set_exporters_enabled(False)


def _spans() -> Any:
    global _span_exporter
    if _span_exporter is None:
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
        from opentelemetry_wrapper.v1 import _config
        _span_exporter = InMemorySpanExporter()
        _config.add_span_sink(_span_exporter)
    return _span_exporter


def _logs() -> Any:
    global _log_exporter
    if _log_exporter is None:
        from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter
        from opentelemetry_wrapper.v1 import _config
        _log_exporter = InMemoryLogRecordExporter()
        _config.add_log_sink(_log_exporter)
    return _log_exporter


def _opted_in(exporter: Any) -> Iterator[Any]:
    from opentelemetry_wrapper.v1 import _config
    exporter.clear()
    _config.set_exporters_enabled(False)
    try:
        yield exporter
    finally:
        if not _whole_suite:
            _config.set_exporters_enabled(True)
        exporter.clear()


@pytest.fixture
def otel_spans() -> Iterator[Any]:
    """the spans this test finished (an `InMemorySpanExporter`: `.get_finished_spans()`), as they would be exported"""
    yield from _opted_in(_spans())


@pytest.fixture
def otel_logs() -> Iterator[Any]:
    """the log records this test emitted (an `InMemoryLogRecordExporter`: `.get_finished_logs()`)"""
    yield from _opted_in(_logs())
