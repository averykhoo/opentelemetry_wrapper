"""
the one `otel` object (DEC-19): a decorator, a context manager, and the entry point for `instrument` / `configure`

configured objects (`otel('name')`, `otel(name=..., attributes=...)`) are immutable and stateless (DEC-20): the spans a
`with` block opens live in a `ContextVar` holding an immutable tuple, set on enter and reset on exit, so concurrent
tasks and threads never close each other's spans. `@otel()` / `with otel():` mean `@otel` / `with otel:` (DEC-50)
"""
import sys
from contextvars import ContextVar
from types import MappingProxyType
from typing import Any
from typing import Mapping
from typing import Optional
from typing import Sequence
from typing import Tuple
from typing import TypeVar
from typing import overload

from opentelemetry import trace

from opentelemetry_wrapper.v1 import _config
from opentelemetry_wrapper.v1 import _env
from opentelemetry_wrapper.v1 import _introspect
from opentelemetry_wrapper.v1 import _spans
from opentelemetry_wrapper.v1._decorator import decorate
from opentelemetry_wrapper.v1._decorator import ensure_configured
from opentelemetry_wrapper.v1._instrument import MISSING
from opentelemetry_wrapper.v1._instrument import instrument as _instrument
from opentelemetry_wrapper.v1._warnings import report

# one entry per open `with otel` block in this context: (scope or None, the token of the `set` that pushed it)
_open_blocks: ContextVar[Tuple[Tuple[Any, Any], ...]] = ContextVar('opentelemetry_wrapper_open_blocks', default=())

_T = TypeVar('_T')

_ZERO_TRACE_ID = '0' * 32
_ZERO_SPAN_ID = '0' * 16


class Otel:
    __slots__ = ('_name', '_attributes')
    _name: Optional[str]
    _attributes: Optional[Mapping[str, Any]]

    def __init__(self, name: Optional[str] = None, attributes: Optional[Mapping[str, Any]] = None):
        object.__setattr__(self, '_name', name)
        object.__setattr__(self, '_attributes', MappingProxyType(dict(attributes)) if attributes else None)

    def __setattr__(self, key: str, value: Any) -> None:
        raise AttributeError(f'{type(self).__name__} objects are immutable')

    def __repr__(self) -> str:
        options = ', '.join(f'{k}={v!r}' for k, v in (('name', self._name), ('attributes', self._attributes)) if v)
        return f'otel({options})'

    # ------------------------------------------------------------------------------------------------------------------
    # decorating, and making configured objects
    # ------------------------------------------------------------------------------------------------------------------

    @overload  # `otel('name')`: a configured object
    def __call__(self, name: str, /, *, attributes: Optional[Mapping[str, Any]] = None) -> 'Otel': ...

    @overload  # `@otel` over anything: the decorated object keeps its exact type (AC-21)
    def __call__(self, target: _T, /, *, name: Optional[str] = None,
                 attributes: Optional[Mapping[str, Any]] = None) -> _T: ...

    @overload  # `@otel(name=...)`, `otel()`: a configured object
    def __call__(self, /, *, name: Optional[str] = None, attributes: Optional[Mapping[str, Any]] = None) -> 'Otel': ...

    def __call__(self, target: Any = MISSING, /, *, name: Optional[str] = None,
                 attributes: Optional[Mapping[str, Any]] = None) -> Any:
        if isinstance(target, str):  # otel('name') / with otel('name', attributes=...)
            target, name = MISSING, target
        if target is MISSING:
            if name is None and attributes is None:
                return self
            return Otel(name if name is not None else self._name,
                        attributes if attributes is not None else self._attributes)
        return decorate(target,
                        name=name if name is not None else self._name,
                        attributes=attributes if attributes is not None else self._attributes)

    # ------------------------------------------------------------------------------------------------------------------
    # `with otel:` / `async with otel:`
    # ------------------------------------------------------------------------------------------------------------------

    def _enter(self, frame: Any) -> trace.Span:
        if _env.disabled():
            scope = None
        else:
            ensure_configured()  # runtime: its warnings go to stderr once, never `warnings.warn` (DEC-81)
            if self._name is not None:  # the name is the user's; the code attributes are the caller's (DEC-21)
                name, attributes = self._name, _introspect.call_site(frame)[1]
            else:
                name, attributes = _introspect.unnamed_call_site(frame)
            if self._attributes:
                attributes = {**(attributes or {}), **self._attributes}
            scope = _spans.start(name, attributes)
        try:
            blocks = _open_blocks.get()
            token = _open_blocks.set(blocks + ((scope, None),))
            _open_blocks.set(blocks + ((scope, token),))  # the entry remembers the token that restores `blocks`
        except Exception as e:
            report('with.enter', e)
        return scope[0] if scope is not None else trace.INVALID_SPAN

    def _exit(self, exc: Optional[BaseException]) -> None:
        try:
            blocks = _open_blocks.get()
            if not blocks:
                return
            scope, token = blocks[-1]
            try:
                _open_blocks.reset(token)
            except ValueError:  # exited in another context than it was entered in
                _open_blocks.set(blocks[:-1])
        except Exception as e:
            report('with.exit', e)
            return
        _spans.finish(scope, exc)

    def __enter__(self) -> trace.Span:
        return self._enter(sys._getframe(1))

    def __exit__(self, exc_type: Any, exc: Optional[BaseException], tb: Any) -> None:
        __tracebackhide__ = __traceback_hide__ = True  # noqa: F841
        self._exit(exc)  # returns None: the exception propagates untouched

    async def __aenter__(self) -> trace.Span:
        return self._enter(sys._getframe(1))

    async def __aexit__(self, exc_type: Any, exc: Optional[BaseException], tb: Any) -> None:
        __tracebackhide__ = __traceback_hide__ = True  # noqa: F841
        self._exit(exc)

    # ------------------------------------------------------------------------------------------------------------------
    # escape hatches (DEC-45)
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def span(self) -> trace.Span:
        """the current span; a span that records nothing when there is none, never `None`"""
        if _env.disabled():
            return trace.INVALID_SPAN
        return trace.get_current_span()

    @property
    def trace_id(self) -> str:
        if _env.disabled():
            return _ZERO_TRACE_ID
        return format(trace.get_current_span().get_span_context().trace_id, '032x')

    @property
    def span_id(self) -> str:
        if _env.disabled():
            return _ZERO_SPAN_ID
        return format(trace.get_current_span().get_span_context().span_id, '016x')

    # ------------------------------------------------------------------------------------------------------------------
    # libraries, apps and configuration
    # ------------------------------------------------------------------------------------------------------------------

    @overload
    def instrument(self, target: _T, /) -> _T: ...

    @overload
    def instrument(self, /) -> None: ...

    def instrument(self, target: Any = MISSING, /) -> Any:
        """`otel.instrument(app | engine | logging | requests | sqlalchemy)`; with no argument, logging, requests
        and system metrics (DEC-11). configures eagerly. returns the target"""
        return _instrument(target)

    def configure(self, *,
                  service_name: Optional[str] = None,
                  resource_attributes: Optional[Mapping[str, Any]] = None,
                  traces_exporter: Optional[Sequence[str]] = None,
                  metrics_exporter: Optional[Sequence[str]] = None,
                  logs_exporter: Optional[Sequence[str]] = None,
                  otlp_endpoint: Optional[str] = None,
                  otlp_headers: Optional[Mapping[str, str]] = None,
                  log_level: Optional[str] = None,
                  log_format: Optional[str] = None,
                  prometheus_path: Optional[str] = None,
                  header_attributes: Optional[Sequence[str]] = None,
                  ) -> None:
        """explicit configuration, at startup, before `otel.instrument(...)`: explicit > env > default; final once
        built (a later different call warns once and is ignored, except the log level)"""
        explicit = {k: v for k, v in locals().items() if k != 'self' and v is not None}
        _config.configure(explicit)

    @property
    def config(self) -> Mapping[str, Any]:
        """the effective configuration, read-only, secrets redacted"""
        return _config.config_view()


otel = Otel()
