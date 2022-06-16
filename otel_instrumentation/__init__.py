from otel_instrumentation.instrument_dataclasses import instrument_dataclasses
from otel_instrumentation.instrument_decorator import instrument_decorate
from otel_instrumentation.instrument_fastapi import instrument_fastapi
from otel_instrumentation.instrument_logging import instrument_logging
from otel_instrumentation.instrument_requests import instrument_requests


@instrument_decorate
def instrument_all():
    instrument_dataclasses()
    instrument_logging()
    instrument_fastapi()
    instrument_requests()


__all__ = (
    instrument_decorate,
    instrument_dataclasses,
    instrument_logging,
    instrument_fastapi,
    instrument_requests,
    instrument_all,
)
