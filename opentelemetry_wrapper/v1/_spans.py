"""
span lifecycle for our own spans (DEC-25: from the OTel tracer), exception status per DEC-3, and minimal code info
(stable `code.*` keys, DEC-31; workstream 3 refines the introspection)

nothing here raises into the app: a failure is reported once on stderr (DEC-75) and the span is skipped
"""
import functools
import inspect
import sys
import threading
from types import CodeType
from typing import Any
from typing import Dict
from typing import Optional
from typing import Set
from typing import Tuple

from opentelemetry import context
from opentelemetry import trace
from opentelemetry.semconv.attributes.code_attributes import CODE_FILE_PATH
from opentelemetry.semconv.attributes.code_attributes import CODE_FUNCTION_NAME
from opentelemetry.semconv.attributes.code_attributes import CODE_LINE_NUMBER
from opentelemetry.semconv.attributes.error_attributes import ERROR_TYPE
from opentelemetry.trace import Status
from opentelemetry.trace import StatusCode

from opentelemetry_wrapper.v1._warnings import report
from opentelemetry_wrapper.v1._warnings import warn_at_runtime

PROCESS_EXIT_CODE = 'process.exit.code'  # semconv, incubating
CLOSED_EARLY = 'opentelemetry_wrapper.closed_early'
CANCELLED = 'opentelemetry_wrapper.cancelled'
INTERRUPTED = 'opentelemetry_wrapper.interrupted'
_RECORDED = '__opentelemetry_wrapper_recorded__'  # marker on an exception whose stack trace is already on a span

_TRACER = trace.get_tracer('opentelemetry_wrapper')  # a proxy until a provider is set, then follows it

Attributes = Dict[str, Any]
Scope = Tuple[trace.Span, object]  # (span, context token or None)


# ----------------------------------------------------------------------------------------------------------------------
# lifecycle
# ----------------------------------------------------------------------------------------------------------------------

def start(name: str, attributes: Optional[Attributes], attach: bool = True) -> Optional[Scope]:
    try:
        span = _TRACER.start_span(name, attributes=attributes)
        token = context.attach(trace.set_span_in_context(span)) if attach else None
        return span, token
    except Exception as e:
        report('span.start', e)
        return None


def attach(scope: Optional[Scope]) -> object:
    if scope is None:
        return None
    try:
        return context.attach(trace.set_span_in_context(scope[0]))
    except Exception as e:
        report('span.attach', e)
        return None


def detach(token: object) -> None:
    if token is None:
        return
    try:
        context.detach(token)
    except Exception as e:
        report('span.detach', e)


def finish(scope: Optional[Scope], exc: Optional[BaseException]) -> None:
    """set the status (OK, or per DEC-3), end the span, and detach its context; never raises"""
    if scope is None:
        return
    span, token = scope
    try:
        if exc is None:
            span.set_status(Status(StatusCode.OK))
        else:
            record_exception(span, exc)
    except Exception as e:
        report('span.status', e)
    try:
        span.end()
    except Exception as e:
        report('span.end', e)
    detach(token)


def _error_type(exc: BaseException) -> str:
    cls = type(exc)
    return cls.__qualname__ if cls.__module__ == 'builtins' else f'{cls.__module__}.{cls.__qualname__}'


def record_exception(span: trace.Span, exc: BaseException) -> None:
    """DEC-3's table: ERROR with the stack trace on the innermost span, `error.type` only on the outer ones"""
    if isinstance(exc, (StopIteration, StopAsyncIteration)):
        return
    if isinstance(exc, GeneratorExit):
        span.set_attribute(CLOSED_EARLY, True)
        return
    asyncio = sys.modules.get('asyncio')  # not imported: then it can't be a CancelledError
    if asyncio is not None and isinstance(exc, asyncio.CancelledError):
        span.set_attribute(CANCELLED, True)
        return
    if isinstance(exc, KeyboardInterrupt):
        span.set_attribute(INTERRUPTED, True)
        return
    if isinstance(exc, SystemExit):
        code = 0 if exc.code is None else exc.code if isinstance(exc.code, int) else 1
        span.set_attribute(PROCESS_EXIT_CODE, code)
        if code != 0:
            span.set_status(Status(StatusCode.ERROR, f'SystemExit: {exc.code}'))
        return
    span.set_attribute(ERROR_TYPE, _error_type(exc))
    span.set_status(Status(StatusCode.ERROR, f'{type(exc).__name__}: {exc}'))
    if not getattr(exc, _RECORDED, False):
        span.record_exception(exc, escaped=True)
        try:
            setattr(exc, _RECORDED, True)
        except Exception:  # an exception type that refuses attributes: outer spans record the trace again
            pass


# ----------------------------------------------------------------------------------------------------------------------
# names and code info
# ----------------------------------------------------------------------------------------------------------------------

def _underlying(target: Any) -> Any:
    """the function whose code the span describes: through bound methods, partials and `__wrapped__`"""
    seen = 0
    while seen < 100:
        seen += 1
        if isinstance(target, (staticmethod, classmethod)) or inspect.ismethod(target):
            target = target.__func__
        elif isinstance(target, functools.partial):
            target = target.func
        elif getattr(target, '__wrapped__', None) is not None and not isinstance(target, type):
            target = target.__wrapped__
        else:
            return target
    return target


def describe(target: Any) -> Tuple[str, Attributes]:
    """span name `module.qualname` (the shape of DEC-47) and the stable `code.*` attributes, looked up once"""
    func = _underlying(target)
    named = isinstance(getattr(func, '__qualname__', None), str) or isinstance(getattr(func, '__name__', None), str)
    if not isinstance(func, type) and callable(func) and not (inspect.isroutine(func) and named):
        call = getattr(type(func), '__call__', None)  # a callable instance: never its repr (high cardinality)
        module, qualname = type(func).__module__, f'{type(func).__qualname__}.__call__'
        code = getattr(call, '__code__', None)
    else:
        code = getattr(func, '__code__', None)
        module = getattr(func, '__module__', None)
        qualname = getattr(func, '__qualname__', None) or getattr(func, '__name__', None) or type(func).__qualname__
        if module is None and inspect.isbuiltin(func):
            module = getattr(getattr(func, '__self__', None), '__name__', None)
    name = f'{module}.{qualname}' if module else qualname
    attributes: Attributes = {CODE_FUNCTION_NAME: name}
    if isinstance(code, CodeType):
        attributes[CODE_FILE_PATH] = code.co_filename
        attributes[CODE_LINE_NUMBER] = code.co_firstlineno
    return name, attributes


_call_sites: Dict[Tuple[CodeType, int], Tuple[str, Attributes]] = {}
_lines_by_code: Dict[CodeType, Set[int]] = {}
_sites_lock = threading.Lock()


def describe_call_site(frame: Any) -> Tuple[str, Attributes]:
    """an unnamed `with otel:` block: named after the enclosing function, never a line number (DEC-47)"""
    code, line = frame.f_code, frame.f_lineno
    cached = _call_sites.get((code, line))
    if cached is not None:
        return cached
    module = frame.f_globals.get('__name__') or '<unknown>'
    name = f'{module}.{code.co_qualname}'
    described = name, {CODE_FUNCTION_NAME: name, CODE_FILE_PATH: code.co_filename, CODE_LINE_NUMBER: line}
    with _sites_lock:
        _call_sites[(code, line)] = described
        lines = _lines_by_code.setdefault(code, set())
        lines.add(line)
        second = len(lines) == 2
    if second:
        # runtime: stderr once, never `warnings.warn`, which an error filter would raise into the app (DEC-81)
        warn_at_runtime(f'two unnamed `with otel:` blocks in {name} share the span name {name!r}; '
                        f'name them, e.g. `with otel(\'load settings\'):`', key=('unnamed', code))
    return described
