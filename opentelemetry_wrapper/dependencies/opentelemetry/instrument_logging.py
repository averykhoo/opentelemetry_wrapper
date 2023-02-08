import logging
import sys
from functools import lru_cache
from functools import update_wrapper
from functools import wraps
from pathlib import Path
from typing import Optional
from typing import Set
from typing import TextIO

from opentelemetry.instrumentation.logging import LoggingInstrumentor

from opentelemetry_wrapper.config.otel_headers import OTEL_LOG_LEVEL
from opentelemetry_wrapper.config.otel_headers import OTEL_WRAPPER_DISABLED
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_decorator import instrument_decorate
from opentelemetry_wrapper.utils.logging_json_formatter import JsonFormatter

# write IDs as 0xBEEF instead of BEEF, so it matches the trace json exactly
LOGGING_FORMAT_VERBOSE = (
    '%(asctime)s '
    '%(levelname)-8s '
    '[%(name)s] '
    '[%(filename)s:%(funcName)s:%(lineno)d] '
    '[trace_id=0x%(otelTraceID)s span_id=0x%(otelSpanID)s resource.service.name=%(otelServiceName)s] '
    '- %(message)s'
)

_CURRENT_ROOT_JSON_HANDLERS: Set[logging.Handler] = set()


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


@instrument_decorate
def instrument_logging(*,
                       level: int = OTEL_LOG_LEVEL,
                       path: Optional[Path] = None,
                       stream: Optional[TextIO] = None,
                       print_json: bool = True,
                       ) -> None:
    """
    this function is (by default) idempotent; calling it multiple times has no additional side effects

    :param level:
    :param path:
    :param stream:
    :param print_json:
    :return:
    """
    global _CURRENT_ROOT_JSON_HANDLERS

    # no-op
    if OTEL_WRAPPER_DISABLED:
        return

    _instrumentor = LoggingInstrumentor()
    if _instrumentor.is_instrumented_by_opentelemetry:
        _instrumentor.uninstrument()
    _instrumentor.instrument(set_logging_format=False)
    old_factory = logging.getLogRecordFactory()

    # the instrumentor failed to use the @wraps decorator so let's do it for them
    # noinspection PyProtectedMember
    if LoggingInstrumentor._old_factory is not None:
        # noinspection PyProtectedMember
        update_wrapper(old_factory, LoggingInstrumentor._old_factory)

    @wraps(old_factory)
    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)

        # we want the trace-id and span-id in a log to match the span it was created in
        # therefore we format it to match
        # note that logs outside a span will be assigned an invalid trace-id and span-id (all zeroes)
        record.otelTraceID = f'0x{int(record.otelTraceID, 16):032x}'
        record.otelSpanID = f'0x{int(record.otelSpanID, 16):016x}'

        return record

    logging.setLogRecordFactory(record_factory)

    # un-instrument logging root handler
    while _CURRENT_ROOT_JSON_HANDLERS:
        logging.root.removeHandler(_CURRENT_ROOT_JSON_HANDLERS.pop())

    # output as json
    if print_json:
        if path is not None:
            _CURRENT_ROOT_JSON_HANDLERS.add(get_json_handler(level=level, path=path))
        if stream is not None or path is None:
            _CURRENT_ROOT_JSON_HANDLERS.add(get_json_handler(level=level, stream=stream))

    # output as text, using the templated logging string format
    else:
        # equivalent to logging.basicConfig(format=..., level=level)
        _formatter = logging.Formatter(fmt=LOGGING_FORMAT_VERBOSE)

        if path is not None:
            _file_handler = logging.FileHandler(path)
            _file_handler.setFormatter(_formatter)
            _CURRENT_ROOT_JSON_HANDLERS.add(_file_handler)
        if stream is not None or path is None:
            _stream_handler = logging.StreamHandler(stream)
            _stream_handler.setFormatter(_formatter)
            _CURRENT_ROOT_JSON_HANDLERS.add(_stream_handler)

    # set root handlers
    for _handler in _CURRENT_ROOT_JSON_HANDLERS:
        logging.root.addHandler(_handler)
    logging.root.setLevel(level)
