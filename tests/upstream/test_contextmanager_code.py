"""
canary: every `@contextmanager` function shares one `__code__` object and exposes the generator function as
`__wrapped__` (DEC-22), which is how v1 detects context-manager functions regardless of decorator order and re-wraps
them as `contextmanager(spanned(f.__wrapped__))`. CPython, not OTel, but upstream all the same
"""
import asyncio
import contextlib

import pytest


def _gen():
    yield 1


async def _agen():
    yield 1


@pytest.mark.parametrize('decorator, function', [(contextlib.contextmanager, _gen),
                                                 (contextlib.asynccontextmanager, _agen)])
def test_context_manager_functions_share_one_code_object(decorator, function):
    def other():
        yield 2

    async def other_async():
        yield 2

    probe = decorator(lambda: (yield))
    assert decorator(function).__code__ is probe.__code__
    assert decorator(other if function is _gen else other_async).__code__ is probe.__code__
    assert decorator(function).__wrapped__ is function


def test_the_two_decorators_have_different_code_objects():
    # so the check tells a sync context manager from an async one
    probe_sync = contextlib.contextmanager(lambda: (yield))
    probe_async = contextlib.asynccontextmanager(lambda: (yield))
    assert probe_sync.__code__ is not probe_async.__code__


def test_a_plain_generator_function_does_not_match():
    probe = contextlib.contextmanager(lambda: (yield))
    assert _gen.__code__ is not probe.__code__


def test_rewrapping_the_unwrapped_function_keeps_the_context_manager():
    events = []

    @contextlib.contextmanager
    def managed():
        events.append('enter')
        yield 'value'
        events.append('exit')

    rewrapped = contextlib.contextmanager(managed.__wrapped__)
    with rewrapped() as value:
        events.append(value)
    assert events == ['enter', 'value', 'exit']


def test_rewrapping_the_unwrapped_async_function_keeps_the_context_manager():
    events = []

    @contextlib.asynccontextmanager
    async def managed():
        events.append('enter')
        yield 'value'
        events.append('exit')

    async def main():
        async with contextlib.asynccontextmanager(managed.__wrapped__)() as value:
            events.append(value)

    asyncio.run(main())
    assert events == ['enter', 'value', 'exit']
