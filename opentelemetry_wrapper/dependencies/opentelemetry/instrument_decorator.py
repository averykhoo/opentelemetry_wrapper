import asyncio
import inspect
from functools import cached_property
from functools import wraps
from typing import Callable
from typing import Coroutine
from typing import Dict
from typing import Optional
from typing import TypeVar
from typing import Union

from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace import Status
from opentelemetry.trace import StatusCode

from opentelemetry_wrapper import __version__  # don't worry, this does not create an infinite import loop
from opentelemetry_wrapper.config.config import OTEL_WRAPPER_DISABLED
from opentelemetry_wrapper.dependencies.opentelemetry.tracers import get_tracer
from opentelemetry_wrapper.utils.introspect import CodeInfo

_TRACER = get_tracer(__name__, __version__)

InstrumentableThing = TypeVar('InstrumentableThing', Callable, Coroutine, type)

_CACHE_INSTRUMENTED: Dict[InstrumentableThing, Optional[InstrumentableThing]] = dict()  # type: ignore[valid-type]
_CACHE_GETATTRIBUTE: Dict[InstrumentableThing, InstrumentableThing] = dict()  # type: ignore[valid-type]


def instrument_decorate(func: InstrumentableThing,
                        /, *,
                        func_name: Optional[str] = None,
                        ) -> InstrumentableThing:
    """
    use as a decorator to start a new trace with any class, function, or async function
    for a class, it will instrument the new, init, and call dunders, as well as any defined methods and properties

    if `func_name` is not set, it will attempt to guess the function/class name
    to decorate a function/class but specify `func_name`, use functools.partial as follows
        @partial(instrument_decorate, func_name='example')
        def f():
            pass

    alternatively, use it as a function to wrap something and optionally set a function name

    this function is idempotent; calling it multiple times has no additional side effects

    todo: don't recurse into pydantic dataclasses, those get re-initialized too often

    :param func: function or class
    :param func_name: if not set, makes an intelligent guess
    :return:
    """

    # no-op
    if OTEL_WRAPPER_DISABLED:
        return func

    # avoid re-instrumenting (or double-instrumenting) things
    # this requires slightly more complex logic than lru_cache provides
    if func in _CACHE_INSTRUMENTED:
        ret = _CACHE_INSTRUMENTED[func]
        if ret is not None:
            return ret
        return func

    # if not provided, try to find the function name
    code_info = CodeInfo(func)
    func_name = func_name or code_info.name

    # build span attributes for this class / function / method / builtin / etc
    span_attributes: Dict[str, Union[str, None, int]] = dict()
    if code_info.function_name:
        span_attributes[SpanAttributes.CODE_FUNCTION] = code_info.function_name
    if code_info.module_name:
        span_attributes[SpanAttributes.CODE_NAMESPACE] = code_info.module_name
    if code_info.path:
        span_attributes[SpanAttributes.CODE_FILEPATH] = str(code_info.path)
    if code_info.lineno:
        span_attributes[SpanAttributes.CODE_LINENO] = code_info.lineno

    wrapped: InstrumentableThing
    if inspect.isclass(func):
        # noinspection PyTypeChecker
        wrapped = _instrument_class(func, func_name, span_attributes)  # type: ignore[assignment]

    elif asyncio.iscoroutinefunction(func):  # coroutine functions are also functions, so this must be checked first
        wrapped = _instrument_coroutine(func, func_name, span_attributes)  # type: ignore[assignment]

    elif inspect.isroutine(func):
        wrapped = _instrument_routine(func, func_name, span_attributes)  # type: ignore[assignment]

    # what is this?
    else:
        raise TypeError(type(func))

    # add to cache and return
    _CACHE_INSTRUMENTED[func] = wrapped
    _CACHE_INSTRUMENTED[wrapped] = None  # a class will end up here
    return wrapped


def _instrument_coroutine(coro: Callable,
                          coro_name: str,
                          span_attributes: dict,
                          ) -> Callable:
    """
    coroutines need an async decorator

    :param coro:
    :param coro_name:
    :param span_attributes:
    :return:
    """

    # no-op
    if OTEL_WRAPPER_DISABLED:
        return coro

    # sanity checks
    assert isinstance(coro, Callable)  # type: ignore[arg-type]
    assert not isinstance(coro, type)
    assert asyncio.iscoroutinefunction(coro)

    @wraps(coro)
    async def wrapped(*args, **kwargs):
        with _TRACER.start_as_current_span(f'async {coro_name}', attributes=span_attributes) as span:
            ret = await coro(*args, **kwargs)
            if span.is_recording():
                # span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, result.status_code)
                span.set_status(Status(StatusCode.OK))
            return ret

    return wrapped


def _instrument_routine(func: Callable,
                        func_name: str,
                        span_attributes: dict,
                        ) -> Callable:
    """
    normal routines (functions, class methods, builtins) just use a normal decorator

    :param func:
    :param func_name:
    :param span_attributes:
    :return:
    """

    # no-op
    if OTEL_WRAPPER_DISABLED:
        return func

    # sanity checks
    assert isinstance(func, Callable)  # type: ignore[arg-type]
    assert not isinstance(func, type)
    assert inspect.isroutine(func)
    assert not asyncio.iscoroutinefunction(func)

    @wraps(func)
    def wrapped(*args, **kwargs):
        with _TRACER.start_as_current_span(func_name, attributes=span_attributes) as span:
            ret = func(*args, **kwargs)
            if span.is_recording():
                span.set_status(Status(StatusCode.OK))
            return ret

    return wrapped


def _instrument_class(cls: type,
                      class_name: str,
                      span_attributes: dict,
                      ) -> type:
    """
    somewhat complex logic to wrap all methods and properties in a class
    actually wraps the getattribute dunder (magic method) so it can cover as much ground as possible
    to uninstrument, replace cls.func with cls.dunder.__wrapped__ for dunder in new, init, call, and getattribute
    this function is idempotent; calling it multiple times has no additional side effects

    :param cls: class to instrument
    :param class_name: name of the class
    :param span_attributes: additional span attributes
    :return:
    """

    # no-op
    if OTEL_WRAPPER_DISABLED:
        return cls

    # sanity checks
    assert isinstance(cls, type)
    assert inspect.isclass(cls)
    assert not inspect.isroutine(cls)

    # wrap the constructors if they exist
    if cls.__new__ is not object.__new__:
        cls.__new__ = instrument_decorate(cls.__new__, func_name=f'{class_name}.__new__')
    if cls.__init__ is not object.__init__:
        # noinspection PyTypeChecker
        cls.__init__ = instrument_decorate(cls.__init__, func_name=f'{class_name}.__init__')
    if hasattr(cls, '__post_init__'):
        cls.__post_init__ = instrument_decorate(cls.__post_init__, func_name=f'{class_name}.__post_init__')

    # also wrap the call method, if it exists
    if not isinstance(cls.__call__, type(object.__call__)):
        cls.__call__ = instrument_decorate(cls.__call__, func_name=f'{class_name}.__call__')

    # wrap the generic attribute getter to auto-wrap all methods
    _original_getattribute = cls.__getattribute__
    if _original_getattribute not in _CACHE_GETATTRIBUTE:

        @wraps(cls.__getattribute__)
        def wrapped_getattribute(*args, **kwargs):

            # if it's a property, start a trace before getting it
            if isinstance(getattr(cls, args[1], None), (property, cached_property)):

                # get line of code for the property if possible
                if hasattr(getattr(cls, args[1]), 'fget'):
                    _attribs = dict()
                    _attribs.update(span_attributes)
                    _attribs[SpanAttributes.CODE_LINENO] = inspect.getsourcelines(getattr(cls, args[1]).fget)[1]
                else:
                    _attribs = span_attributes

                # instrument the property call
                with _TRACER.start_as_current_span(f'property {class_name}.{args[1]}', attributes=_attribs) as span:
                    ret = _original_getattribute(*args, **kwargs)
                    if span.is_recording():
                        span.set_status(Status(StatusCode.OK))
                    return ret

            # otherwise just get it
            obj = _original_getattribute(*args, **kwargs)

            # wrap if the retrieved object is a method, coroutine, or nested class
            if inspect.isclass(obj) or inspect.isroutine(obj):
                return instrument_decorate(obj)

            # no clue what this is, just return it
            else:
                return obj

        cls.__getattribute__ = wrapped_getattribute
        _CACHE_GETATTRIBUTE[_original_getattribute] = wrapped_getattribute

    return cls
