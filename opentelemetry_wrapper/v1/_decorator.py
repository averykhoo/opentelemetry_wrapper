"""
`@otel` on functions and other routines: one span per call, the wrapper keeping the target's kind and signature

* idempotent, keyed on the underlying function (v0 lessons): decorating a wrapper, a partial or `lru_cache` over a
  wrapper, or the same function again returns what is already there
* never crashes (AC-7): an unsupported target is returned unchanged with one `OtelWrapperWarning`
* disabled (DEC-24): decorating returns the target unchanged, and existing wrappers check at call time
* no arguments or return values on spans (DEC-26); exceptions re-raise with a bare `raise`, and the wrapper frames
  set `__tracebackhide__` (pytest) and `__traceback_hide__` (Sentry and others)
"""
import functools
import inspect
import types
import weakref
from typing import Any
from typing import List
from typing import Mapping
from typing import Optional

from opentelemetry_wrapper.v1 import _config
from opentelemetry_wrapper.v1 import _env
from opentelemetry_wrapper.v1 import _spans
from opentelemetry_wrapper.v1._warnings import runtime
from opentelemetry_wrapper.v1._warnings import warn

MARK = '__opentelemetry_wrapper__'  # set on every wrapper we make
_CACHE = '__opentelemetry_wrapper_cache__'  # set on the underlying function: its wrapper
_fallback_cache: 'weakref.WeakKeyDictionary[Any, weakref.ref]' = weakref.WeakKeyDictionary()


def ensure_configured() -> None:
    """configure from env vars if nothing has yet, at the first span or call: a runtime path, so the warnings that
    configuring raises go to stderr once and never through `warnings.warn` (DEC-81)"""
    if not _config.is_configured():
        with runtime():
            _config.ensure_configured()


def is_instrumented(target: Any) -> bool:
    """ours, or something over ours (a partial, a bound method, `lru_cache` or another `__wrapped__` chain)"""
    for _ in range(100):
        if getattr(target, MARK, False) is True:
            return True
        if isinstance(target, (staticmethod, classmethod)) or inspect.ismethod(target):
            target = target.__func__
        elif isinstance(target, functools.partial):
            target = target.func
        elif getattr(target, '__wrapped__', None) is not None and not isinstance(target, type):
            target = target.__wrapped__
        else:
            return False
    return False


def _cached(func: Any) -> Optional[Any]:
    found = getattr(func, _CACHE, None) if inspect.isfunction(func) else None
    if found is None:
        try:
            ref = _fallback_cache.get(func)
            found = ref() if ref is not None else None
        except TypeError:  # unhashable or not weakly referenceable
            return None
    # `functools.wraps` copies __dict__, so another decorator over `func` may carry our cache entry: check it's ours
    return found if found is not None and getattr(found, '__wrapped__', None) is func else None


def _remember(func: Any, wrapper: Any) -> None:
    if inspect.isfunction(func):
        setattr(func, _CACHE, wrapper)  # a cycle, collected with the function; no strong cache of user objects
        return
    try:
        _fallback_cache[func] = weakref.ref(wrapper)
    except TypeError:
        pass


def decorate(target: Any, name: Optional[str] = None, attributes: Optional[Mapping[str, Any]] = None) -> Any:
    """the public `@otel` for routines; warnings are emitted at the end, outside our own `try`"""
    if _env.disabled():
        return target
    notes: List[str] = []
    try:
        result = _decorate(target, name, dict(attributes) if attributes else None, notes)
    except Exception as e:
        notes.append(f'@otel could not instrument {_short(target)} and returned it unchanged: {type(e).__name__}: {e}')
        result = target
    for note in notes:
        warn(note)
    return result


def _short(target: Any) -> str:
    try:
        text = repr(target)
    except Exception:
        text = f'<{type(target).__qualname__} object>'
    return text if len(text) <= 120 else text[:117] + '...'


def _decorate(target: Any, name: Optional[str], attributes: Optional[dict], notes: List[str]) -> Any:
    if is_instrumented(target):
        return target
    if isinstance(target, type):
        notes.append(f'@otel on a class ({_short(target)}) is not supported yet; returned unchanged')
        return target
    if isinstance(target, staticmethod):
        return staticmethod(_decorate(target.__func__, name, attributes, notes))
    if isinstance(target, classmethod):
        return classmethod(_decorate(target.__func__, name, attributes, notes))
    if isinstance(target, property):
        parts = [_decorate(f, name, attributes, notes) if f is not None else None
                 for f in (target.fget, target.fset, target.fdel)]
        return type(target)(*parts, target.__doc__)  # type: ignore[call-arg]
    if inspect.ismethod(target):
        return types.MethodType(_decorate(target.__func__, name, attributes, notes), target.__self__)
    if not callable(target):
        notes.append(f'@otel cannot instrument {_short(target)}: it is not callable; returned unchanged')
        return target
    cached = _cached(target)
    if cached is not None:
        return cached
    wrapper = _make_wrapper(target, name, attributes)
    _remember(target, wrapper)
    return wrapper


def _make_wrapper(target: Any, name: Optional[str], attributes: Optional[dict]) -> Any:
    described_name, described = _spans.describe(target)
    span_name = name or described_name
    span_attributes = {**described, **(attributes or {})}
    disabled = _env.disabled
    start, finish = _spans.start, _spans.finish

    if inspect.isasyncgenfunction(target):
        async def wrapper(*args, **kwargs):
            __tracebackhide__ = __traceback_hide__ = True  # noqa: F841
            agen = target(*args, **kwargs)
            if disabled():  # DEC-24: no span, no context; asend / athrow / aclose still reach the target
                scope = None
            else:
                ensure_configured()
                scope = start(span_name, span_attributes, attach=False)
            to_send, to_throw = None, None
            try:
                while True:
                    token = _spans.attach(scope) if scope is not None else None
                    try:
                        if to_throw is not None:
                            thrown, to_throw = to_throw, None
                            value = await agen.athrow(thrown)
                        else:
                            value = await agen.asend(to_send)
                    finally:
                        if token is not None:
                            _spans.detach(token)
                    try:
                        to_send = yield value
                    except GeneratorExit:
                        await agen.aclose()
                        raise
                    except BaseException as e:
                        to_throw = e
            except StopAsyncIteration:
                if scope is not None:
                    finish(scope, None)
            except BaseException as e:
                if scope is not None:
                    finish(scope, e)
                raise

    elif inspect.isgeneratorfunction(target):
        def wrapper(*args, **kwargs):
            __tracebackhide__ = __traceback_hide__ = True  # noqa: F841
            gen = target(*args, **kwargs)
            if disabled():
                return (yield from gen)
            ensure_configured()
            scope = start(span_name, span_attributes, attach=False)
            to_send, to_throw = None, None
            try:
                while True:
                    token = _spans.attach(scope)  # current only while the generator's body runs
                    try:
                        if to_throw is not None:
                            thrown, to_throw = to_throw, None
                            value = gen.throw(thrown)
                        else:
                            value = gen.send(to_send)
                    finally:
                        _spans.detach(token)
                    try:
                        to_send = yield value
                    except GeneratorExit:
                        gen.close()
                        raise
                    except BaseException as e:
                        to_throw = e
            except StopIteration as stop:
                finish(scope, None)
                return stop.value
            except BaseException as e:
                finish(scope, e)
                raise

    elif inspect.iscoroutinefunction(target):
        async def wrapper(*args, **kwargs):  # type: ignore[misc]
            __tracebackhide__ = __traceback_hide__ = True  # noqa: F841
            if disabled():
                return await target(*args, **kwargs)
            ensure_configured()
            scope = start(span_name, span_attributes)
            try:
                result = await target(*args, **kwargs)
            except BaseException as e:
                finish(scope, e)
                raise
            finish(scope, None)
            return result

    else:
        def wrapper(*args, **kwargs):
            __tracebackhide__ = __traceback_hide__ = True  # noqa: F841
            if disabled():
                return target(*args, **kwargs)
            ensure_configured()
            scope = start(span_name, span_attributes)
            try:
                result = target(*args, **kwargs)
            except BaseException as e:
                finish(scope, e)
                raise
            finish(scope, None)
            return result

    try:
        # a function's __dict__ is copied as `functools.wraps` does; a callable instance's state never is
        functools.update_wrapper(wrapper, target, updated=('__dict__',) if inspect.isfunction(target) else ())
    except Exception:
        wrapper.__wrapped__ = target  # type: ignore[attr-defined]
    setattr(wrapper, MARK, True)
    return wrapper
