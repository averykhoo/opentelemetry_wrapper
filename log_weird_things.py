import logging
from decimal import Decimal

from pydantic import BaseModel
from pydantic.v1.json import pydantic_encoder

from opentelemetry_wrapper.dependencies.opentelemetry.instrument_logging import instrument_logging


class Something(BaseModel):
    key: str = 'value'


instrument_logging()

# json-like
logging.warning('')
logging.warning(None)
logging.warning([1, 2, 3])
logging.warning({1: 11, None: None, 'a': {'A'}})
logging.warning(float('nan'))
logging.warning(float('inf'))
logging.warning(float('-inf'))

# not json-like
logging.info(1.234 + 4j)  # a complex number
logging.info(Decimal('0.11111111111111111111111111111111111111111111111111111111111111111111'))  # impossible precision
logging.info(logging)  # a builtin module
logging.info(print)  # a builtin function
logging.info(BaseModel)  # a class from a 3rd party library
logging.info(pydantic_encoder)  # a function from a 3rd party library
logging.info(SENTINEL := object())  # an anonymous sentinel object
logging.info(1, 2, 3, 4, 5, 6, 7)  # passing in random unhandled arguments
logging.error(Something)  # a defined class
logging.error(Something())  # a class instance
