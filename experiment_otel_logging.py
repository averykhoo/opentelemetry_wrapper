import logging
import os
import sys

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


def double(x):
    with tracer.start_as_current_span('def-double'):
        logging.debug(f'doubling {x=}')
        return x + x


def multiply(multiplier, multiplicand):
    """
    very silly way to multiply things
    inspired by exponentiation-by-squaring
    """
    with tracer.start_as_current_span('def-multiply'):
        logging.info(f'multiply {multiplier=} by non-negative {multiplicand=}')
        assert multiplicand >= 0

        accumulator = 0
        while multiplicand:
            if multiplicand & 1:
                accumulator += multiplier
            multiplicand >>= 1
            if multiplicand:
                multiplier = double(multiplier)
        return accumulator


@async_to_sync
async def square(x):
    with tracer.start_as_current_span('def-square'):
        if x < 0:
            logging.warning(f'squaring absolute of negative number abs({x=})')
        else:
            logging.info(f'squaring non-negative number {x=}')
        return multiply(abs(x), abs(x))


if __name__ == '__main__':
    # print(double(2))
    # print([multiply(i, i) for i in range(5)])
    multiply(-5, 20)
    square(-10)
