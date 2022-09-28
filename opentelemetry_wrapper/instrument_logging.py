import logging
import sys
from functools import lru_cache
from functools import update_wrapper
from functools import wraps
from pathlib import Path
from typing import Optional
from typing import TextIO

from opentelemetry.instrumentation.logging import LoggingInstrumentor

from opentelemetry_wrapper.instrument_decorator import instrument_decorate
from opentelemetry_wrapper.utils.logging_json_formatter import JsonFormatter

# write IDs as 0xBEEF instead of BEEF so it matches the trace json exactly
LOGGING_FORMAT_VERBOSE = (
    '%(asctime)s '
    '%(levelname)-8s '
    '[%(name)s] '
    '[%(filename)s:%(funcName)s:%(lineno)d] '
    '[trace_id=0x%(otelTraceID)s span_id=0x%(otelSpanID)s resource.service.name=%(otelServiceName)s] '
    '- %(message)s'
)

# in the short format, write it as a [traceparent header](https://www.w3.org/TR/trace-context/#traceparent-header)
LOGGING_FORMAT_MINIMAL = (
    '%(levelname)-8s '
    '%(otelServiceName)s '
    '[00-%(otelTraceID)s-%(otelSpanID)s-01] '
    '[%(name)s:%(module)s:%(funcName)s] '
    '%(message)s'
)


@lru_cache  # avoid creating duplicate handlers
def get_json_handler(*,
                     level: int = logging.NOTSET,
                     path: Optional[Path] = None,
                     stream: Optional[TextIO] = None,
                     ) -> logging.Handler:
    if path is not None and stream is not None:
        raise ValueError('cannot set both path and stream')

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
                       level: int = logging.NOTSET,
                       print_json: bool = True,
                       verbose: bool = True,
                       force_reinstrumentation: bool = False,
                       ) -> None:
    """
    this function is (by default) idempotent; calling it multiple times has no additional side effects

    :param print_json:
    :param verbose:
    :param force_reinstrumentation:
    :param level:
    :return:
    """
    _instrumentor = LoggingInstrumentor()
    if _instrumentor.is_instrumented_by_opentelemetry:
        if force_reinstrumentation:
            _instrumentor.uninstrument()
        else:
            return
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
        # so we format it to match
        # note that logs outside a span will be assigned an invalid trace-id and span-id (all zeroes)
        record.otelTraceID = f'0x{int(record.otelTraceID, 16):032x}'
        record.otelSpanID = f'0x{int(record.otelSpanID, 16):016x}'

        return record

    logging.setLogRecordFactory(record_factory)

    # output as json
    if print_json:
        # todo: take in appropriate args to specify an output (e.g. to a path or stream)
        # todo: re-instrument correctly if args are different
        json_handler = get_json_handler(level=level)
        if json_handler not in logging.root.handlers:
            logging.root.addHandler(json_handler)
        logging.root.setLevel(level)

    # output as above logging string format
    else:
        # force overwrite of logging basic config since their instrumentor doesn't do it correctly
        logging.basicConfig(format=LOGGING_FORMAT_VERBOSE if verbose else LOGGING_FORMAT_MINIMAL,
                            level=level,
                            force=True,
                            )
