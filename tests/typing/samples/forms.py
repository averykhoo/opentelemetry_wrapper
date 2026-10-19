"""
`reveal_type` samples for AC-21 (OTW-14): every form of `otel` keeps the decorated object's type under mypy

each `reveal_type(...)` line carries its expected type in a trailing `# R: <type>` comment, and `test_typing_forms.py`
runs mypy over this file and compares the two: so the samples are never run, only type-checked
"""
import asyncio
from typing import AsyncIterator
from typing import Awaitable
from typing import Callable
from typing import Generator
from typing import Iterator
from typing import List

from opentelemetry import trace

from opentelemetry_wrapper.v1 import otel


# --- functions: sync, async, generator, async generator ---------------------------------------------------------------

@otel
def sync_fn(x: int, *, y: str = '') -> float:
    return x + len(y)


reveal_type(sync_fn)  # R: def (x: int, *, y: str =) -> float
reveal_type(sync_fn(1, y='a'))  # R: float


@otel
async def async_fn(x: int) -> str:
    return str(x)


reveal_type(async_fn)  # R: def (x: int) -> typing.Coroutine[Any, Any, str]


@otel
def gen_fn(n: int) -> Generator[int, str, bool]:
    yield n
    return True


reveal_type(gen_fn)  # R: def (n: int) -> typing.Generator[int, str, bool]


@otel
async def agen_fn(n: int) -> AsyncIterator[int]:
    yield n


reveal_type(agen_fn)  # R: def (n: int) -> typing.AsyncIterator[int]


# --- `@otel(...)` with options, `@otel()` -----------------------------------------------------------------------------

@otel('named')
def named_fn(a: List[int]) -> Iterator[int]:
    return iter(a)


reveal_type(named_fn)  # R: def (a: list[int]) -> typing.Iterator[int]


@otel(name='kw', attributes={'k': 1})
def kw_fn(a: int) -> int:
    return a


reveal_type(kw_fn)  # R: def (a: int) -> int


@otel()
def empty_call_fn(a: int) -> int:
    return a


reveal_type(empty_call_fn)  # R: def (a: int) -> int

configured = otel('base', attributes={'k': 1})
reveal_type(configured)  # R: opentelemetry_wrapper.v1._otel.Otel


@configured
def via_configured(a: int) -> int:
    return a


reveal_type(via_configured)  # R: def (a: int) -> int


@configured('other')
async def via_configured_async(a: int) -> int:
    return a


reveal_type(via_configured_async)  # R: def (a: int) -> typing.Coroutine[Any, Any, int]


# --- methods, classmethods, staticmethods, properties, classes --------------------------------------------------------

class Service:
    @otel
    def method(self, x: int) -> str:
        return str(x)

    @otel
    async def amethod(self, x: int) -> str:
        return str(x)

    @classmethod
    @otel
    def cm(cls, x: int) -> 'Service':
        return cls()

    @staticmethod
    @otel
    def sm(x: int) -> int:
        return x

    @otel('over')
    @classmethod
    def cm_over(cls, x: int) -> 'Service':
        return cls()

    @property
    @otel
    def prop(self) -> int:  # DEC-48: `@property` on top, `@otel` underneath
        return 1


reveal_type(Service().method)  # R: def (x: int) -> str
reveal_type(Service().method(1))  # R: str
reveal_type(Service().amethod)  # R: def (x: int) -> typing.Coroutine[Any, Any, str]
reveal_type(Service.cm)  # R: def (x: int) -> tests.typing.samples.forms.Service
reveal_type(Service.sm)  # R: def (x: int) -> int
reveal_type(Service.cm_over)  # R: def (x: int) -> tests.typing.samples.forms.Service
reveal_type(Service().prop)  # R: int


@otel
class Decorated:
    def __init__(self, x: int) -> None:
        self.x = x

    def method(self) -> int:
        return self.x


reveal_type(Decorated)  # R: def (x: int) -> tests.typing.samples.forms.Decorated
reveal_type(Decorated(1))  # R: tests.typing.samples.forms.Decorated
reveal_type(Decorated(1).method())  # R: int


@otel('named-class')
class DecoratedNamed:
    pass


reveal_type(DecoratedNamed())  # R: tests.typing.samples.forms.DecoratedNamed


# --- `otel.instrument(x)` returns x's type ----------------------------------------------------------------------------

def plain(x: int) -> int:
    return x


reveal_type(otel.instrument(plain))  # R: def (x: int) -> int
reveal_type(otel.instrument(Service()))  # R: tests.typing.samples.forms.Service
reveal_type(otel.instrument(Service))  # R: def () -> tests.typing.samples.forms.Service
reveal_type(otel.instrument())  # R: None
reveal_type(otel(plain))  # R: def (x: int) -> int

callback: Callable[[float], Awaitable[None]] = otel(asyncio.sleep)  # a typeshed overloaded function stays assignable


# --- `with otel:` / `with otel('x'):`, `async with` -------------------------------------------------------------------

with otel as bare_span:
    reveal_type(bare_span)  # R: opentelemetry.trace.span.Span

with otel('x') as named_span:
    reveal_type(named_span)  # R: opentelemetry.trace.span.Span

with otel(name='x', attributes={'k': 1}) as kw_span:
    reveal_type(kw_span)  # R: opentelemetry.trace.span.Span

with otel() as empty_span:
    reveal_type(empty_span)  # R: opentelemetry.trace.span.Span

with configured('y') as chained_span:
    reveal_type(chained_span)  # R: opentelemetry.trace.span.Span

span_annotated: trace.Span = bare_span


async def use_async_with() -> None:
    async with otel as a_span:
        reveal_type(a_span)  # R: opentelemetry.trace.span.Span

    async with otel('x') as an_span:
        reveal_type(an_span)  # R: opentelemetry.trace.span.Span


# --- the escape hatches -----------------------------------------------------------------------------------------------

reveal_type(otel.span)  # R: opentelemetry.trace.span.Span
reveal_type(otel.trace_id)  # R: str
reveal_type(otel.span_id)  # R: str
reveal_type(otel.configure())  # R: None


# --- the signature is kept, so a wrong call is an error (`# E: <code>` marks the expected mypy error) -----------------

sync_fn('x')  # E: arg-type
Service().method('x')  # E: arg-type
Service.sm('x')  # E: arg-type
Decorated('x')  # E: arg-type
otel.instrument(plain)('x')  # E: arg-type
named_span.no_such_attribute  # E: attr-defined
