import logging

from pydantic import BaseModel

from opentelemetry_wrapper.dependencies.opentelemetry.instrument_logging import instrument_logging

instrument_logging()

logging.info(logging)
logging.info(logging.info)
logging.info(BaseModel)
logging.info(instrument_logging)
logging.warning('')
logging.warning(None)
logging.warning([1, 2, 3])
logging.warning({1: 11, None: None, 'a': 'A'})
logging.warning(object())
logging.warning(1.234 + 4j)


class Something(BaseModel):
    key: str = 'value'


logging.error(Something)
logging.error(Something())
