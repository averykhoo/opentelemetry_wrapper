import logging
import sys
from functools import lru_cache
from functools import update_wrapper
from functools import wraps
from pathlib import Path
from typing import Dict
from typing import List
from typing import Optional
from typing import Set
from typing import TextIO
from typing import Tuple

from opentelemetry.instrumentation.logging import LoggingInstrumentor

from opentelemetry_wrapper.config.otel_headers import OTEL_EXPORTER_OTLP_ENDPOINT
from opentelemetry_wrapper.config.otel_headers import OTEL_LOG_LEVEL
from opentelemetry_wrapper.config.otel_headers import OTEL_WRAPPER_DISABLED
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_decorator import instrument_decorate
from opentelemetry_wrapper.dependencies.opentelemetry.otel_providers import get_otel_log_handler
from opentelemetry_wrapper.utils.logging_json_formatter import JsonFormatter

LOGGING_FORMAT_VERBOSE = (
    '%(asctime)s '
    '%(levelname)-8s '
    '[%(name)s] '
    '[%(filename)s:%(funcName)s:%(lineno)d] '
    '[trace_id=%(otelTraceID)s span_id=%(otelSpanID)s resource.service.name=%(otelServiceName)s] '
    '- %(message)s'
)

_OUR_ROOT_HANDLERS: Set[logging.Handler] = set()
_CLOBBERED_ROOT_HANDLERS: Dict[str, Tuple[List[logging.Handler], bool]] = dict()


@lru_cache  # avoid creating duplicate handlers
def get_json_handler(*,
                     level: int = OTEL_LOG_LEVEL,
                     path: Optional[Path] = None,
                     stream: Optional[TextIO] = None,
                     ) -> logging.Handler:
    if path is not None and stream is not None:
        raise ValueError('cannot set both path and stream')

    handler: logging.Handler
    if path is not None:
        handler = logging.FileHandler(path)
    elif stream is not None:
        handler = logging.StreamHandler(stream=stream)
    else:
        handler = logging.StreamHandler(stream=sys.stderr)

    handler.setFormatter(JsonFormatter())
    handler.setLevel(level)
    return handler


def uninstrument_logging():
    # un-instrument from OTEL
    _instrumentor = LoggingInstrumentor()  # this is a singleton, so it'll return the same object
    if _instrumentor.is_instrumented_by_opentelemetry:
        _instrumentor.uninstrument()

    # un-clobber the handlers
    for logger_name, (handlers, propagate) in _CLOBBERED_ROOT_HANDLERS.items():
        logging.getLogger(logger_name).handlers = handlers
        logging.getLogger(logger_name).propagate = propagate
    _CLOBBERED_ROOT_HANDLERS.clear()

    # un-instrument logging root handler
    while _OUR_ROOT_HANDLERS:
        # noinspection PyBroadException
        try:
            logging.root.removeHandler(_OUR_ROOT_HANDLERS.pop())
        except Exception:
            continue


@instrument_decorate
def instrument_logging(*,
                       level: int = OTEL_LOG_LEVEL,
                       path: Optional[Path] = None,
                       stream: Optional[TextIO] = None,
                       print_json: bool = True,
                       clobber_other_log_handlers: bool = False,
                       ) -> None:
    """
    this function is (by default) idempotent; calling it multiple times has no additional side effects

    :param level:
    :param path:
    :param stream:
    :param print_json:
    :param clobber_other_log_handlers: drop all other log handlers created by anyone else
    :return:
    """
    # no-op
    if OTEL_WRAPPER_DISABLED:
        return

    uninstrument_logging()

    LoggingInstrumentor().instrument(set_logging_format=False)
    old_factory = logging.getLogRecordFactory()

    # the instrumentor failed to use the @wraps decorator so let's do it for them
    # noinspection PyProtectedMember
    if LoggingInstrumentor._old_factory is not None:
        # noinspection PyProtectedMember
        update_wrapper(old_factory, LoggingInstrumentor._old_factory)

    @wraps(old_factory)
    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)

        # we want the trace-id and span-id in a log to match the span it was created in;
        # therefore, we format it to match (span_id: `0x09f8e31e775ec22e` instead of `9f8e31e775ec22e`)
        # note that logs outside a span will be assigned an invalid trace-id and span-id (all zeroes)
        # TODO: this could skip the int cast and instead just left-pad and lowercase
        record.otelTraceID = f'0x{int(record.otelTraceID, 16):032x}'
        record.otelSpanID = f'0x{int(record.otelSpanID, 16):016x}'

        return record

    logging.setLogRecordFactory(record_factory)

    # output as json
    if print_json:
        if path is not None:
            _OUR_ROOT_HANDLERS.add(get_json_handler(level=level, path=path))
        if stream is not None or path is None:
            _OUR_ROOT_HANDLERS.add(get_json_handler(level=level, stream=stream))

    # output as text, using the templated logging string format
    else:
        # equivalent to logging.basicConfig(format=..., level=level)
        _formatter = logging.Formatter(fmt=LOGGING_FORMAT_VERBOSE)

        if path is not None:
            _file_handler = logging.FileHandler(path)
            _file_handler.setFormatter(_formatter)
            _OUR_ROOT_HANDLERS.add(_file_handler)
        if stream is not None or path is None:
            _stream_handler = logging.StreamHandler(stream)
            _stream_handler.setFormatter(_formatter)
            _OUR_ROOT_HANDLERS.add(_stream_handler)

    # add an otel log exporter too
    if OTEL_EXPORTER_OTLP_ENDPOINT:
        _OUR_ROOT_HANDLERS.add(get_otel_log_handler(level=level))

    # set root handlers
    for _handler in _OUR_ROOT_HANDLERS:
        logging.root.addHandler(_handler)
    logging.root.setLevel(level)

    # clobber all other handlers
    if clobber_other_log_handlers:
        for logger_name, logger in logging.root.manager.loggerDict.items():
            if not isinstance(logger, logging.PlaceHolder):
                _CLOBBERED_ROOT_HANDLERS[logger_name] = (logger.handlers, logger.propagate)
                logger.handlers = []
                logger.propagate = True
