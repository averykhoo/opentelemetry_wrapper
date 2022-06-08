import logging
import os
import sys
from typing import Union

from asgiref.sync import async_to_sync
from opentelemetry import trace
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.export import ConsoleSpanExporter

os.environ['OTEL_PYTHON_LOG_CORRELATION'] = 'true'
LoggingInstrumentor().instrument()

trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(ConsoleSpanExporter(out=sys.stderr,
                                           formatter=lambda span: span.to_json(indent=None) + os.linesep)))
tracer = trace.get_tracer(__name__)


async def double(x: float):
    with tracer.start_as_current_span('def-double'):
        assert isinstance(x, (float, int))
        logging.info(f'doubling {x=}')
        return x + x


async def _multiply(multiplier: Union[float, int], multiplicand: int):
    """
    very silly way to multiply things
    inspired by exponentiation-by-squaring
    """
    with tracer.start_as_current_span('def-multiply'):
        logging.debug(f'multiply {multiplier=} by non-negative {multiplicand=}')
        assert multiplicand >= 0
        assert isinstance(multiplier, (float, int))
        assert isinstance(multiplicand, int)

        accumulator = 0
        while multiplicand:
            if multiplicand & 1:
                accumulator += multiplier
            multiplicand >>= 1
            if multiplicand:
                multiplier = await double(multiplier)
        return accumulator


def square(x):
    """
    wraps async multiply in a sync wrapper
    """
    with tracer.start_as_current_span('def-square'):
        assert isinstance(x, int)
        if x < 0:
            logging.warning(f'squaring absolute of negative integer abs({x=})')
        else:
            logging.info(f'squaring non-negative number {x=}')
        return async_to_sync(_multiply)(abs(x), abs(x))


def exponentiate(base, exponent):
    """
    exponentiation-by-squaring
    """
    with tracer.start_as_current_span('def-multiply'):
        logging.info(f'exponentiate {base=} by non-negative {exponent=}')
        assert exponent >= 0
        assert isinstance(base, int)
        assert isinstance(exponent, int)

        out = 1
        while exponent:
            if exponent & 1:
                out *= base
            exponent >>= 1
            if exponent:
                base = square(base)
        return out


if __name__ == '__main__':
    assert exponentiate(-10, 5) == -100000
