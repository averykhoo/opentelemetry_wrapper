import asyncio
import inspect
from functools import cached_property
from functools import wraps
from typing import Callable
from typing import Coroutine
from typing import Optional
from typing import Union

from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace import Status
from opentelemetry.trace import StatusCode

from introspect import CodeInfo
from otel_instrumentation.config import __version__
from otel_instrumentation.utils import get_tracer

_TRACER = get_tracer(__name__, __version__)
_CACHE_INSTRUMENTED = dict()


def _instrument_class(cls: type):
    assert not inspect.isroutine(cls)

    # wrap the constructors if they exist
    if cls.__new__ is not object.__new__:
        cls.__new__ = instrument_decorate(cls.__new__, func_name=f'{func_name}.__new__')
    if cls.__init__ is not object.__init__:
        cls.__init__ = instrument_decorate(cls.__init__, func_name=f'{func_name}.__init__')

    # also wrap the call method, if it exists
    if not isinstance(cls.__call__, type(object.__call__)):
        cls.__call__ = instrument_decorate(cls.__call__, func_name=f'{func_name}.__call__')

    # wrap the generic attribute getter to auto-wrap all methods
    _original_getattribute = cls.__getattribute__

    @wraps(cls.__getattribute__)
    def _wrapped_getattribute(*args, **kwargs):

        # if it's a property, start a trace before getting it
        if isinstance(getattr(cls, args[1], None), (property, cached_property)):
            _name = f'property {func_name}.{args[1]}'
            if hasattr(getattr(cls, args[1]), 'fget'):
                _attribs = dict()
                _attribs.update(span_attributes)
                _attribs[SpanAttributes.CODE_LINENO] = inspect.getsourcelines(getattr(cls, args[1]).fget)[1]
            else:
                _attribs = span_attributes
            with _TRACER.start_as_current_span(_name, attributes=_attribs) as span:
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

    cls.__getattribute__ = _wrapped_getattribute


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
    # this requires slightly more complex logic than lru_cache provides
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

    if inspect.isclass(func):

        # noinspection PyTypeChecker
        _instrument_class(func)  # somewhat complex logic to wrap all methods and properties in a class

        # we want to return the original class, which was passed in as `func`
        wrapped = func

    # coroutines need an async decorator
    elif asyncio.iscoroutinefunction(func):
        @wraps(func)
        async def wrapped(*args, **kwargs):
            with _TRACER.start_as_current_span(f'async {func_name}', attributes=span_attributes) as span:
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
            with _TRACER.start_as_current_span(func_name, attributes=span_attributes) as span:
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
