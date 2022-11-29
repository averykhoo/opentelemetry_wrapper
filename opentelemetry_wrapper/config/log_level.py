import logging
import os
from functools import lru_cache

# see logging._nameToLevel, which is protected
NAME_TO_LEVEL = {
    'critical': logging.CRITICAL,
    'fatal':    logging.FATAL,
    'error':    logging.ERROR,
    'warn':     logging.WARNING,
    'warning':  logging.WARNING,
    'info':     logging.INFO,
    'debug':    logging.DEBUG,
    'notset':   logging.NOTSET,
}


@lru_cache
def get_log_level(default=logging.NOTSET) -> int:
    _level = os.getenv('OTEL_LOG_LEVEL', '').casefold().strip()

    # default
    if not _level:
        return default

    # it's an integer, todo: should this be allowed? should there be a min/max?
    if _level.isdigit():
        return int(_level)

    # a known level name
    if _level in NAME_TO_LEVEL:
        return NAME_TO_LEVEL[_level]

    # is it a user-defined level?
    if isinstance(logging.getLevelName(_level), int):
        return logging.getLevelName(_level)

    # don't error or warn, just default
    return default
