import asyncio
import dataclasses
import datetime
import inspect
import json
import logging
import sys
from functools import cached_property
from functools import lru_cache
from functools import reduce
from functools import wraps
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Coroutine
from typing import Dict
from typing import Iterable
from typing import List
from typing import Optional
from typing import TextIO
from typing import Tuple
from typing import Union

import fastapi
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.resources import SERVICE_NAME
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.export import ConsoleSpanExporter
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace import Status
from opentelemetry.trace import StatusCode

from introspect import CodeInfo

__version__ = '0.2'

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


def init_tracer():
    def format_span(span: ReadableSpan) -> str:
        return f'{span.to_json(indent=None)}\n'

    tp = TracerProvider(resource=Resource.create({SERVICE_NAME: 'test-service-name'}))

    # noinspection PyProtectedMember
    trace._set_tracer_provider(tp, log=False)  # try to set, but don't warn otherwise
    if trace.get_tracer_provider() is tp:  # if we succeeded in setting it, set it up
        tp.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter(formatter=format_span)))


# get tracer
init_tracer()
tracer = trace.get_tracer(__name__, __version__)

_CACHE_INSTRUMENTED = dict()


def instrument_decorate(func: Union[Callable, Coroutine],
                        /, *,
                        func_name: Optional[str] = None,
                        ) -> Union[Callable, Coroutine]:
    """
    use as a decorator to start a new trace with any class, function, or async function
    for a class, it will instrument the new, init, and call dunders, as well as any defined methods and properties

    if `func_name` is not set, it will attempt to guess the function/class name
    to decorate a function/class but specify `func_name`, use functools.partial as follows
        @partial(instrument_decorate, func_name='example')
        def f():
            pass

    alternatively, use it as a function to wrap something and optionally set a function name

    :param func: function or class
    :param func_name: if not set, makes an intelligent guess
    :return:
    """
    # avoid re-instrumenting (or double-instrumenting) things
    if func in _CACHE_INSTRUMENTED:
        if _CACHE_INSTRUMENTED[func] is None:
            return func
        return _CACHE_INSTRUMENTED[func]

    # if not provided, try to find the function name
    code_info = CodeInfo(func)
    func_name = func_name or code_info.name

    span_attributes = dict()
    if code_info.function_name:
        span_attributes[SpanAttributes.CODE_FUNCTION] = code_info.function_name
    if code_info.module_name:
        span_attributes[SpanAttributes.CODE_NAMESPACE] = code_info.module_name
    if code_info.path:
        span_attributes[SpanAttributes.CODE_FILEPATH] = str(code_info.path)
    if code_info.lineno:
        span_attributes[SpanAttributes.CODE_LINENO] = code_info.lineno

    # somewhat complex logic to wrap all methods and properties in a class
    if inspect.isclass(func):
        assert not inspect.isroutine(func)
        # wrap the constructors if they exist
        if func.__new__ is not object.__new__:
            func.__new__ = instrument_decorate(func.__new__, func_name=f'{func_name}.__new__')
        if func.__init__ is not object.__init__:
            func.__init__ = instrument_decorate(func.__init__, func_name=f'{func_name}.__init__')

        # also wrap the call method, if it exists
        if not isinstance(func.__call__, type(object.__call__)):
            func.__call__ = instrument_decorate(func.__call__, func_name=f'{func_name}.__call__')

        # wrap the generic attribute getter to auto-wrap all methods
        _original_getattribute = func.__getattribute__

        @wraps(func.__getattribute__)
        def _wrapped_getattribute(*args, **kwargs):

            # if it's a property, start a trace before getting it
            if isinstance(getattr(func, args[1], None), (property, cached_property)):
                _name = f'property {func_name}.{args[1]}'
                if hasattr(getattr(func, args[1]), 'fget'):
                    _attribs = dict()
                    _attribs.update(span_attributes)
                    _attribs[SpanAttributes.CODE_LINENO] = inspect.getsourcelines(getattr(func, args[1]).fget)[1]
                else:
                    _attribs = span_attributes
                with tracer.start_as_current_span(_name, attributes=_attribs) as span:
                    ret = _original_getattribute(*args, **kwargs)
                    if span.is_recording():
                        span.set_status(Status(StatusCode.OK))
                    return ret

            # otherwise just get it
            obj = _original_getattribute(*args, **kwargs)

            # wrap if function
            if inspect.isclass(obj) or inspect.isroutine(obj):
                return instrument_decorate(obj)

            # just return otherwise
            else:
                return obj

        func.__getattribute__ = _wrapped_getattribute

        # we want to return the original class, which was passed in as `func`
        wrapped = func

    # coroutines need an async decorator
    elif asyncio.iscoroutinefunction(func):
        @wraps(func)
        async def wrapped(*args, **kwargs):
            with tracer.start_as_current_span(f'async {func_name}', attributes=span_attributes) as span:
                ret = await func(*args, **kwargs)
                if span.is_recording():
                    # span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, result.status_code)
                    span.set_status(Status(StatusCode.OK))
                return ret

    # normal routines (functions, methods, builtins) just use a normal decorator
    # note that coroutine functions are also functions, so this needs to be checked last
    elif inspect.isroutine(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            with tracer.start_as_current_span(func_name, attributes=span_attributes) as span:
                ret = func(*args, **kwargs)
                if span.is_recording():
                    span.set_status(Status(StatusCode.OK))
                return ret

    # what is this?
    else:
        raise TypeError(type(func))

    # add to cache and return
    _CACHE_INSTRUMENTED[func] = wrapped
    _CACHE_INSTRUMENTED[wrapped] = None  # a class will end up here
    return wrapped


@lru_cache
def get_json_handler(*,
                     level: int = logging.DEBUG,
                     path: Optional[Path] = None,
                     stream: Optional[TextIO] = None,
                     ) -> logging.Handler:
    class JsonFormatter(logging.Formatter):
        """
        converts a LogRecord to a JSON string

        see https://docs.python.org/3/library/logging.html#logrecord-attributes for record keys

        opentelemetry also adds `otelSpanID`, `otelTraceID`, and `otelServiceName`
        """

        def __init__(self,
                     keys: Optional[Union[Tuple[str, ...], List[str], Dict[str, str]]] = None,
                     datefmt: Optional[str] = None,
                     ensure_ascii: bool = False,
                     allow_nan: bool = True,
                     indent: Optional[int] = None,
                     separators: Optional[Tuple[str, str]] = None,
                     sort_keys: bool = False,
                     ) -> None:
            """

            :param keys: list of LogRecord attributes, or mapper from LogRecord attribute name -> output json key name
            :param datefmt: date format string; if not set, defaults to ISO8601
            :param ensure_ascii: see `json.dumps` docs
            :param allow_nan: see `json.dumps` docs
            :param indent: see `json.dumps` docs
            :param separators: see `json.dumps` docs
            :param sort_keys: see `json.dumps` docs
            """

            super().__init__(datefmt)

            self._keys: Optional[Dict[str, str]]
            if isinstance(keys, dict):
                self._keys = dict()
                self._keys.update(keys)
            elif not isinstance(keys, str) and isinstance(keys, Iterable):
                self._keys = dict()
                for key in keys:
                    assert isinstance(key, str), key
                    self._keys[key] = key
            elif keys is None:
                self._keys = None
            else:
                raise TypeError(keys)

            self.ensure_ascii = ensure_ascii
            self.allow_nan = allow_nan
            self.indent = indent
            self.separators = separators
            self.sort_keys = sort_keys

            # noinspection PyTypeChecker
            self.tz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo

        def usesTime(self):
            return self._keys is None or 'asctime' in self._keys

        def formatMessage(self, record: logging.LogRecord):
            raise DeprecationWarning

        def format(self, record):
            """
            Format the specified record as text.

            The record's attribute dictionary is used as the operand to a
            string formatting operation which yields the returned string.
            Before formatting the dictionary, a couple of preparatory steps
            are carried out. The message attribute of the record is computed
            using LogRecord.getMessage(). If the formatting string uses the
            time (as determined by a call to usesTime(), formatTime() is
            called to format the event time. If there is exception information,
            it is formatted using formatException() and appended to the message.
            """
            # add `message`
            record.message = record.getMessage()

            # add `asctime`, `tz_name`, and `tz_utc_offset_seconds`
            if self.usesTime():
                record.tz_name = self.tz.tzname(None)
                record.tz_utc_offset_seconds = self.tz.utcoffset(None).seconds
                if self.datefmt:
                    record.asctime = self.formatTime(record, self.datefmt)
                else:
                    record.asctime = datetime.datetime.fromtimestamp(record.created, tz=self.tz).isoformat()

            # add `exc_text`
            if record.exc_info and not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)

            if self._keys is not None:
                log_data = {k: getattr(record, v, None) for k, v in self._keys.items()}
            else:
                log_data = record.__dict__
            return json.dumps(log_data,
                              ensure_ascii=self.ensure_ascii,
                              allow_nan=self.allow_nan,
                              indent=self.indent,
                              separators=self.separators,
                              sort_keys=self.sort_keys)

    if not path and not stream:
        stream = sys.stderr
    elif path and stream:
        raise ValueError('cannot set both path and stream')

    if path:
        handler = logging.FileHandler(path)
    else:
        handler = logging.StreamHandler(stream=stream)
    handler.setFormatter(JsonFormatter())
    handler.setLevel(level)
    return handler


@instrument_decorate
def instrument_logging(*,
                       print_json: bool = True,
                       verbose: bool = True,
                       force_reinstrumentation: bool = True,
                       ) -> None:
    _instrumentor = LoggingInstrumentor()
    if _instrumentor.is_instrumented_by_opentelemetry:
        if force_reinstrumentation:
            _instrumentor.uninstrument()
        else:
            return
    _instrumentor.instrument(set_logging_format=False)

    if print_json:
        # output as json
        json_handler = get_json_handler(stream=sys.stderr)
        if json_handler not in logging.root.handlers:
            logging.root.addHandler(json_handler)
        logging.root.setLevel(logging.DEBUG if verbose else logging.INFO)
    else:
        # force overwrite of logging basic config since their instrumentor doesn't do it correctly
        logging.basicConfig(format=LOGGING_FORMAT_VERBOSE if verbose else LOGGING_FORMAT_MINIMAL,
                            level=logging.DEBUG if verbose else logging.INFO,
                            force=True,
                            )


@instrument_decorate
def instrument_requests(*, force_reinstrumentation: bool = True):
    _instrumentor = RequestsInstrumentor()
    if _instrumentor.is_instrumented_by_opentelemetry:
        if force_reinstrumentation:
            _instrumentor.uninstrument()
        else:
            return
    _instrumentor.instrument()


@instrument_decorate
def instrument_fastapi(app: fastapi.FastAPI) -> fastapi.FastAPI:
    """
    instrument a FastAPI app
    also instruments logging and requests (if requests exists)
    """
    # first instrument logging, if not already instrumented
    instrument_logging(force_reinstrumentation=False)

    # instrument the app
    FastAPIInstrumentor.instrument_app(app)

    # instrument requests as well
    if not RequestsInstrumentor().is_instrumented_by_opentelemetry:
        RequestsInstrumentor().instrument()

    # return app
    return app


@instrument_decorate
def instrument_dataclasses():
    """
    magical way to auto-instrument all dataclasses created using the @dataclass decorator
    note that this MUST be called **before** any code imports dataclasses.dataclass
    """
    _original = dataclasses.dataclass

    @wraps(dataclasses.dataclass)
    def wrapped(*args, **kwargs):
        dataclass_or_wrap = _original(*args, **kwargs)
        if inspect.isclass(dataclass_or_wrap):
            return instrument_decorate(dataclass_or_wrap)
        else:
            @wraps(dataclass_or_wrap)
            def double_wrap(*args, **kwargs):
                return instrument_decorate(dataclass_or_wrap(*args, **kwargs))

            return double_wrap

    dataclasses.dataclass = wrapped


def logging_tree():
    root: Dict[Optional[str], Any] = dict()  # {...: logging.root}
    for logger_name in sorted(logging.root.manager.loggerDict.keys()):
        logger = logging.root.manager.loggerDict[logger_name]
        if isinstance(logger, logging.Logger):
            reduce(lambda node, name: node.setdefault(name, {}), logger_name.split('.'), root)  # [...] = logger
    return root


if __name__ == '__main__':
    instrument_dataclasses()
    from dataclasses import dataclass


    @dataclass  # (frozen=True)
    class A:
        x = 1

        # @instrument_decorate
        # def __new__(cls, *args, **kwargs):
        #     logging.info('A.__new__')
        #     return super(A, cls).__new__(cls, *args, **kwargs)

        # @instrument_decorate
        def __init__(self):
            logging.info('A.__init__')
            # self.y = 2

        # @instrument_decorate
        def b(self):
            logging.info('A.b')
            return 1

        # @instrument_decorate
        def c(self):
            logging.info('A.c')

            @instrument_decorate
            def d():
                logging.info('A.c.d')
                return 1

            return d

        def __call__(self, *args, **kwargs):
            logging.info('A.call')
            return

        @property
        def e(self):
            logging.info('A.e')
            return 1


    @instrument_decorate
    @lru_cache
    def f(x):
        return x + 1


    instrument_logging()
    A().b()
    A().c()()
    A()()
    A().__class__
    A().e
    A().x
