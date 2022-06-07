import logging
import os

from opentelemetry.instrumentation.logging import LoggingInstrumentor

os.environ['OTEL_PYTHON_LOG_CORRELATION'] = 'true'
LoggingInstrumentor().instrument()


def double(x):
    logging.info(f'doubling {x=}')
    return x * 2


def multiply(multiplier, multiplicand):
    """
    very silly way to multiply things
    inspired by exponentiation-by-squaring
    """
    logging.info(f'multiply {multiplier=} by {multiplicand=}')
    assert multiplicand >= 0

    accumulator = 0
    while multiplicand:
        if multiplicand & 1:
            accumulator += multiplier
        multiplicand >>= 1
        if multiplicand:
            multiplier = double(multiplier)
    return accumulator


if __name__ == '__main__':
    print(double(2))
    print([multiply(i, i) for i in range(5)])
    print(multiply(-5, 20))
