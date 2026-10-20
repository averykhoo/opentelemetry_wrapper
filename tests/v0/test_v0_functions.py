"""
`instrument_decorate` (v1: `@otel`) on functions, coroutines and other callables (in-process)

class instrumentation is in test_v0_classes.py, since it can't be tested in-process (it is order-dependent). v1's span
names and generator spans differ from v0's (DEC-47, DEC-52, DEC-22): tests/v1/test_v1_decorator.py and
tests/v1/test_v1_generators.py pin them
"""
import asyncio
import functools
import inspect
from pathlib import Path

import pytest


# ----------------------------------------------------------------------------------------------------------------------
# plain functions
# ----------------------------------------------------------------------------------------------------------------------

def plain_add(x, y=1):
    """docstring of plain_add"""
    return x + y


def test_decorated_function_keeps_metadata(otw, spans):
    wrapped = otw.decorate(plain_add)
    assert wrapped.__name__ == 'plain_add'
    assert wrapped.__qualname__ == 'plain_add'
    assert wrapped.__doc__ == 'docstring of plain_add'
    assert wrapped.__wrapped__ is plain_add
    assert inspect.signature(wrapped) == inspect.signature(plain_add)


def stable_attrs_target(x):
    return x


def test_function_span_has_stable_code_attributes(otw, spans):
    # v0 emitted the deprecated `code.function` / `code.namespace` / `code.filepath` / `code.lineno` (DEC-31)
    otw.decorate(stable_attrs_target)(1)
    (record,) = spans.records()
    attributes = record['attributes']
    assert attributes['code.function.name'] == f'{__name__}.stable_attrs_target'
    assert Path(attributes['code.file.path']) == Path(__file__)
    assert attributes['code.line.number'] == stable_attrs_target.__code__.co_firstlineno


def renamed_target():
    return 'x'


def test_func_name_override_via_partial(otw, spans):
    # documented in the docstring of v0's instrument_decorate
    decorated = functools.partial(otw.decorate, func_name='custom span name')(renamed_target)
    assert decorated() == 'x'
    assert spans.names() == ['custom span name']


# ----------------------------------------------------------------------------------------------------------------------
# coroutines
# ----------------------------------------------------------------------------------------------------------------------

async def async_raises():
    raise KeyError('nope')


def test_async_exception_propagates_and_span_is_error(otw, spans):
    wrapped = otw.decorate(async_raises)
    with pytest.raises(KeyError):
        asyncio.run(wrapped())
    (record,) = spans.records()
    assert record['status'] == 'ERROR'
    assert 'exception' in record['events']


# ----------------------------------------------------------------------------------------------------------------------
# "never crash" (charter goal G-3); the v0 bug list found these holes by reading the code
# ----------------------------------------------------------------------------------------------------------------------

def partial_fresh_target(a, b):
    return a * b


class CallableInstance:
    def __call__(self, x):
        return x


# v0 bug list "Never crash holes in instrument_decorate": v0 raised TypeError for these (before 3.14, for a partial)
@pytest.mark.parametrize('make', [
    pytest.param(lambda: functools.partial(partial_fresh_target, 3), id='functools.partial'),
    pytest.param(CallableInstance, id='callable instance'),
])
def test_decorating_unsupported_callables_does_not_crash(otw, make):
    obj = make()
    wrapped = otw.decorate(obj)
    assert wrapped(5) == obj(5)
