from opentelemetry_wrapper.instrument_dataclasses import instrument_dataclasses
from opentelemetry_wrapper.instrument_decorator import instrument_decorate
from opentelemetry_wrapper.instrument_fastapi import instrument_fastapi
from opentelemetry_wrapper.instrument_logging import instrument_logging
from opentelemetry_wrapper.instrument_requests import instrument_requests


@instrument_decorate
def instrument_all():
    # todo: accept kwargs to disable/enable some of these
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
