"""
`@otel` on functions and other routines: one span per call, the wrapper keeping the target's kind and signature

* idempotent, keyed on the underlying function (v0 lessons): decorating a wrapper, a partial or `lru_cache` over a
  wrapper, or the same function again returns what is already there
* never crashes (AC-7): an unsupported target is returned unchanged with one `OtelWrapperWarning`
* disabled (DEC-24): decorating returns the target unchanged, and existing wrappers check at call time
* no arguments or return values on spans (DEC-26); exceptions re-raise with a bare `raise`, and the wrapper frames
  set `__tracebackhide__` (pytest) and `__traceback_hide__` (Sentry and others)
* generators and async generators (DEC-22): one span per generator, current only while its body runs, the wrapper
  itself a (async) generator function; over `@contextmanager` / `@asynccontextmanager`, one span from enter to exit,
  current across the yield so the `with` body is its child (put `@otel` on top: underneath, it sees a generator)
"""
import contextlib
import functools
import inspect
import sys
import time
import types
import weakref
from typing import Any
from typing import AsyncIterator
from typing import Iterator
from typing import List
from typing import Mapping
from typing import Optional

from opentelemetry_wrapper.v1 import _config
from opentelemetry_wrapper.v1 import _env
from opentelemetry_wrapper.v1 import _introspect
from opentelemetry_wrapper.v1 import _spans
from opentelemetry_wrapper.v1._warnings import runtime
from opentelemetry_wrapper.v1._warnings import warn


# every `@contextmanager` function shares one `__code__` object, and exposes the generator function as `__wrapped__`
@contextlib.contextmanager
def _sync_cm_probe() -> Iterator[None]:
    yield


@contextlib.asynccontextmanager
async def _async_cm_probe() -> AsyncIterator[None]:
    yield


_SYNC_CM_CODE = _sync_cm_probe.__code__
_ASYNC_CM_CODE = _async_cm_probe.__code__
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


def _context_manager_kind(target: Any) -> Optional[str]:
    """'sync' or 'async' for a `contextlib` context-manager function over a generator function, else None"""
    if not inspect.isfunction(target):
        return None
    inner = getattr(target, '__wrapped__', None)
    if target.__code__ is _SYNC_CM_CODE and inspect.isgeneratorfunction(inner):
        return 'sync'
    if target.__code__ is _ASYNC_CM_CODE and inspect.isasyncgenfunction(inner):
        return 'async'
    return None


def _sync_generator(target: Any, span_name: str, span_attributes: dict, hold: bool) -> Any:
    """a generator function over a generator function (DEC-22): one span from the first `next()` to exhaustion,
    close or garbage collection, current only while the body runs (`hold`, for a context manager: across the yield).
    `send`, `throw` and `close` are forwarded, so the target sees exactly what it would without us

    the wrapper is itself a generator function, so FastAPI and pytest still see a `yield`; the price is that nothing
    runs when it is called: the target's arguments are bound, and the span parented, at the first `next()`"""
    disabled = _env.disabled
    start, finish, clock = _spans.start, _spans.finish, time.perf_counter

    def wrapper(*args, **kwargs):
        __tracebackhide__ = __traceback_hide__ = True  # noqa: F841
        gen = target(*args, **kwargs)
        if disabled():  # DEC-24: no span, no context
            return (yield from gen)
        ensure_configured()
        scope = start(span_name, span_attributes, attach=hold)
        yields, active, saved = 0, 0.0, None

        def run(call, argument=None):  # one step of the body, in its own context (the span current)
            nonlocal active, saved
            token = None if hold else _spans.attach(scope, saved)
            began = clock()
            try:
                return call() if argument is None else call(argument)
            finally:
                active += clock() - began
                if token is not None:  # what the body entered before the yield is current again when it resumes
                    saved = _spans.current()
                _spans.detach(token)

        step, argument = gen.__next__, None
        try:
            while True:
                box = [run(step, argument)]  # StopIteration at the end
                yields += 1
                step = argument = None  # nothing of ours holds a sent value or a thrown exception while suspended
                try:
                    sent = yield box.pop()  # ... nor the value handed out
                except GeneratorExit:
                    run(gen.close)
                    raise
                except BaseException as e:
                    step, argument = gen.throw, e
                else:
                    step, argument = (gen.__next__, None) if sent is None else (gen.send, sent)
                    del sent
        except StopIteration as stop:
            finish(scope, None, _tally(yields, active))
            return stop.value
        except BaseException as e:
            finish(scope, e, _tally(yields, active))
            raise

    return wrapper


def _async_generator(target: Any, span_name: str, span_attributes: dict, hold: bool) -> Any:
    """`_sync_generator` for async generator functions, with `asend`, `athrow` and `aclose`"""
    disabled = _env.disabled
    start, finish, clock = _spans.start, _spans.finish, time.perf_counter

    async def wrapper(*args, **kwargs):
        __tracebackhide__ = __traceback_hide__ = True  # noqa: F841
        agen = target(*args, **kwargs)
        if disabled():  # DEC-24: no span, no context; asend / athrow / aclose still reach the target
            scope = None
        else:
            ensure_configured()
            scope = start(span_name, span_attributes, attach=hold)
        yields, active, saved = 0, 0.0, None

        async def run(call, argument=None):
            nonlocal active, saved
            token = None if hold else _spans.attach(scope, saved)
            began = clock()
            try:
                return await (call() if argument is None else call(argument))
            finally:
                active += clock() - began
                if token is not None:
                    saved = _spans.current()
                _spans.detach(token)

        step, argument = functools.partial(_first_step, agen), None
        try:
            while True:
                box = [await run(step, argument)]  # StopAsyncIteration at the end
                yields += 1
                step = argument = None
                try:
                    sent = yield box.pop()
                except GeneratorExit:
                    await run(agen.aclose)
                    raise
                except BaseException as e:
                    step, argument = agen.athrow, e
                else:
                    step, argument = (agen.__anext__, None) if sent is None else (agen.asend, sent)
                    del sent
        except StopAsyncIteration:
            finish(scope, None, _tally(yields, active))
        except BaseException as e:
            finish(scope, e, _tally(yields, active))
            raise

    return wrapper


def _first_step(agen: Any) -> Any:
    """`agen.__anext__()` with the event loop's async-generator hooks off, so the loop tracks only our wrapper.
    Otherwise `shutdown_asyncgens()` (at the end of `asyncio.run`) calls `aclose()` on both at once, and if the
    target's cleanup awaits, the two collide ('aclose(): asynchronous generator is already running'). The wrapper
    closes the target itself when it is closed or finalized; the hooks are read when an async generator is first
    advanced, before its body runs, so async generators the body starts are tracked as usual"""
    try:
        hooks = sys.get_asyncgen_hooks()
        sys.set_asyncgen_hooks(None, None)
    except Exception:  # never in CPython; then the loop simply tracks both, as before
        return agen.__anext__()
    try:
        return agen.__anext__()
    finally:
        sys.set_asyncgen_hooks(*hooks)


def _tally(yields: int, active: float) -> dict:
    return {_spans.YIELDS: yields, _spans.ACTIVE_SECONDS: active}


def _make_wrapper(target: Any, name: Optional[str], attributes: Optional[dict]) -> Any:
    described_name, described = _introspect.describe(target)
    span_name = name or described_name
    span_attributes = {**described, **(attributes or {})}
    disabled = _env.disabled
    start, finish = _spans.start, _spans.finish

    cm_kind = _context_manager_kind(target)
    if cm_kind is not None:  # DEC-22: `@otel` over `@contextmanager`: the span covers enter -> body -> exit
        builder = _async_generator if cm_kind == 'async' else _sync_generator
        inner = builder(target.__wrapped__, span_name, span_attributes, True)
        functools.update_wrapper(inner, target.__wrapped__, updated=('__dict__',))
        rewrapped = (contextlib.asynccontextmanager if cm_kind == 'async' else contextlib.contextmanager)(inner)
        rewrapped.__wrapped__ = target  # type: ignore[union-attr]  # as every other wrapper: the cache key
        setattr(rewrapped, MARK, True)
        return rewrapped

    if inspect.isasyncgenfunction(target):
        wrapper = _async_generator(target, span_name, span_attributes, False)
    elif inspect.isgeneratorfunction(target):
        wrapper = _sync_generator(target, span_name, span_attributes, False)
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
