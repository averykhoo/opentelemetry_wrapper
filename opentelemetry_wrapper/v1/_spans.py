"""
span lifecycle for our own spans (DEC-25: from the OTel tracer) and exception status per DEC-3; names and `code.*`
attributes come from `_introspect`

nothing here raises into the app: a failure is reported once on stderr (DEC-75) and the span is skipped
"""
import sys
from typing import Any
from typing import Dict
from typing import Optional
from typing import Tuple

from opentelemetry import context
from opentelemetry import trace
from opentelemetry.semconv.attributes.error_attributes import ERROR_TYPE
from opentelemetry.trace import Status
from opentelemetry.trace import StatusCode

from opentelemetry_wrapper.v1._warnings import report

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
