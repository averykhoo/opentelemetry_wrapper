"""
canary: which `logging.Handler` turns stdlib log records into OTel log records

v0 (and, as written, the v1 design) uses the SDK's `opentelemetry.sdk._logs.LoggingHandler`, which writes real log
records with the stable `code.*` keys (the "Logs" evidence in `docs/evidence/v1-design-evidence-2026-10-18.md`). since
SDK 1.44 / contrib 0.65b0 it warns that it is deprecated in favour of the handler in
`opentelemetry-instrumentation-logging`, which writes the `code.*` keys only with `log_code_attributes=True`. these
pin both, so the removal of the SDK's handler, or a change to contrib's defaults, fails here first
"""
import logging
import warnings

import pytest

from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter
from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor

CODE_KEYS = {'code.file.path', 'code.function.name', 'code.line.number'}


def _log_through(handler_factory):
    exporter = InMemoryLogRecordExporter()
    provider = LoggerProvider()
    provider.add_log_record_processor(SimpleLogRecordProcessor(exporter))
    logger = logging.getLogger('tests.upstream.handler')
    logger.propagate = False
    handler = handler_factory(provider)
    logger.addHandler(handler)
    try:
        logger.warning('hello %s', 'world', extra={'order_id': 7})
    finally:
        logger.removeHandler(handler)
    [record] = exporter.get_finished_logs()
    return record.log_record


def test_the_sdk_handler_is_deprecated_and_still_writes_code_attributes():
    from opentelemetry.sdk._logs import LoggingHandler

    with pytest.warns(DeprecationWarning, match='opentelemetry-instrumentation-logging'):
        record = _log_through(lambda provider: LoggingHandler(logger_provider=provider))
    assert record.body == 'hello world'
    assert record.attributes['order_id'] == 7
    assert CODE_KEYS <= set(record.attributes)


def test_the_contrib_handler_writes_code_attributes_only_when_asked():
    from opentelemetry.instrumentation.logging.handler import LoggingHandler

    with warnings.catch_warnings():
        warnings.simplefilter('error', DeprecationWarning)
        plain = _log_through(lambda provider: LoggingHandler(logger_provider=provider))
        with_code = _log_through(lambda provider: LoggingHandler(logger_provider=provider, log_code_attributes=True))
    for record in (plain, with_code):
        assert record.body == 'hello world'
        assert record.attributes['order_id'] == 7
    assert not CODE_KEYS & set(plain.attributes)
    assert CODE_KEYS <= set(with_code.attributes)
