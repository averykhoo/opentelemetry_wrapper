import logging
import sys

from asgiref.sync import async_to_sync
from opentelemetry import trace
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.logging.constants import DEFAULT_LOGGING_FORMAT
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.export import ConsoleSpanExporter

# instrument logging.Logger
# write as 0xBEEF instead of BEEF so it matches the trace exactly
_log_format = (DEFAULT_LOGGING_FORMAT
               .replace('%(otelTraceID)s', '0x%(otelTraceID)s')
               .replace('%(otelSpanID)s', '0x%(otelSpanID)s'))
LoggingInstrumentor().instrument(set_logging_format=True, logging_format=_log_format)

# init tracer
trace.set_tracer_provider(TracerProvider())
_formatter = lambda span: f'{span.to_json(indent=None)}\n'
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(ConsoleSpanExporter(out=sys.stderr,
                                                                                      formatter=_formatter)))
tracer = trace.get_tracer(__name__)


def bitshift(x: int, shift_by: int):
    """
    shifts left if positive, right if negative
    """
    with tracer.start_as_current_span('def-bitshift'):
        assert isinstance(x, int)
        assert isinstance(shift_by, int)

        if shift_by > 0:
            logging.debug(f'bit-shifting {x=} right by {shift_by}')
            return x << shift_by
        elif shift_by < 0:
            logging.debug(f'bit-shifting {x=} left by {-shift_by}')
            return x >> -shift_by
        else:
            logging.debug(f'bit-shifting {x=} by 0')
            return x


async def multiply(multiplier: int, multiplicand: int):
    """
    very silly way to multiply things inspired by exponentiation-by-squaring
    constrained to only use the `bitshift` function and addition
    uses async in order to test that logging works normally
    """
    with tracer.start_as_current_span('def-multiply'):
        logging.info(f'multiply {multiplier=} by {multiplicand=}')
        _negative = multiplicand < 0
        multiplicand = abs(multiplicand)

        assert multiplicand >= 0
        assert isinstance(multiplier, int)
        assert isinstance(multiplicand, int)

        accumulator = 0
        while multiplicand:
            _tmp, multiplicand = multiplicand, bitshift(multiplicand, -1)
            if _tmp != bitshift(multiplicand, 1):
                accumulator += multiplier
            if multiplicand:
                multiplier = bitshift(multiplier, 1)

        return accumulator if not _negative else -accumulator


async def square(x):
    """
    absolutely unnecessary abstraction as would be expected in enterprise code
    uses warning instead of info just for testing
    """
    with tracer.start_as_current_span('def-square'):
        assert isinstance(x, int)
        if x < 0:
            logging.warning(f'squaring absolute of negative integer abs({x=})')
        else:
            logging.info(f'squaring non-negative number {x=}')
        return await multiply(abs(x), abs(x))


@async_to_sync
async def exponentiate(base, exponent):
    """
    exponentiation-by-squaring
    constrained not to use any math other than the functions defined above
    """
    with tracer.start_as_current_span('def-multiply'):
        logging.info(f'exponentiate {base=} by non-negative {exponent=}')
        assert exponent >= 0
        assert isinstance(base, int)
        assert isinstance(exponent, int)

        out = 1
        while exponent:
            _tmp, exponent = exponent, bitshift(exponent, -1)
            if _tmp != bitshift(exponent, 1):
                out = await multiply(out, base)
            if exponent:
                base = await square(base)
        return out


if __name__ == '__main__':
    assert exponentiate(-10, 5) == -100000
