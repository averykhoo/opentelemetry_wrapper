import asyncio
import dataclasses
import inspect
import logging
from functools import lru_cache
from functools import reduce
from functools import wraps
from typing import Any
from typing import Callable
from typing import Coroutine
from typing import Dict
from typing import Optional
from typing import Union

import fastapi
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.resources import SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.export import ConsoleSpanExporter

__version__ = '0.1'

# write IDs as 0xBEEF instead of BEEF so it matches the trace json exactly
from get_function_name import get_function_name

LOGGING_FORMAT_VERBOSE = (
    '%(asctime)s '
    '%(levelname)-8s '
    '[%(name)s] '
    '[%(filename)s:%(funcName)s:%(lineno)d] '
    '[trace_id=0x%(otelTraceID)s span_id=0x%(otelSpanID)s resource.service.name=%(otelServiceName)s] '
    '- %(message)s'
)
LOGGING_FORMAT_MINIMAL = (
    '%(levelname)-8s '
    '%(otelServiceName)s '
    '[00-%(otelTraceID)s-%(otelSpanID)s-01] '
    '[%(name)s:%(module)s:%(funcName)s] '
    '%(message)s'
)

# init tracer
trace.set_tracer_provider(tp := TracerProvider(resource=Resource.create({SERVICE_NAME: 'test-service-name'})))
tp.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter(formatter=lambda span: f'{span.to_json(indent=None)}\n')))
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

    todo: correctly set span attributes
     from opentelemetry.semconv.trace import SpanAttributes
     from opentelemetry.trace.status import Status
     span_attributes = {
            SpanAttributes.CODE_FUNCTION:  function name,
            SpanAttributes.CODE_NAMESPACE: module name,
            SpanAttributes.CODE_FILEPATH:  full path,
            SpanAttributes.CODE_LINENO:    first line number,
        }
     with tracer.start_as_current_span(span_name, kind=SpanKind.???, attributes=span_attributes) as span
     ...
     if span.is_recording():
         span.set_attribute(
             SpanAttributes.HTTP_STATUS_CODE, result.status_code
         )
         span.set_status(
             Status(http_status_to_status_code(result.status_code))
         )

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
    if func_name is None:
        func_name = get_function_name(func)

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
            if isinstance(getattr(func, args[1], None), property):
                with tracer.start_as_current_span(f'property {func_name}.{args[1]}'):
                    return _original_getattribute(*args, **kwargs)

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
            with tracer.start_as_current_span(f'async {func_name}'):
                return await func(*args, **kwargs)

    # normal routines (functions, methods, builtins) just use a normal decorator
    # note that coroutine functions are also functions, so this needs to be checked last
    elif inspect.isroutine(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            with tracer.start_as_current_span(func_name):
                return func(*args, **kwargs)

    # what is this?
    else:
        raise TypeError(type(func))

    # add to cache and return
    _CACHE_INSTRUMENTED[func] = wrapped
    _CACHE_INSTRUMENTED[wrapped] = None  # a class will end up here
    return wrapped


@instrument_decorate
def instrument_logging(*, verbose: bool = True, force_reinstrumentation: bool = True):
    _instrumentor = LoggingInstrumentor()
    if _instrumentor.is_instrumented_by_opentelemetry:
        if force_reinstrumentation:
            _instrumentor.uninstrument()
        else:
            return
    _instrumentor.instrument(set_logging_format=False)

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
