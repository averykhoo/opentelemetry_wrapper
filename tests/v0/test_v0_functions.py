"""
`instrument_decorate` on functions, coroutines, methods and other routines (in-process)

class instrumentation is in test_v0_classes.py, since it can't be tested in-process (it is order-dependent)
"""
import asyncio
import functools
import inspect
from pathlib import Path

import pytest


def expected_name(func) -> str:
    """v0's span name for a plain function: `<module>.qualname`"""
    return f'<{func.__module__}>.{func.__qualname__}'


# ----------------------------------------------------------------------------------------------------------------------
# plain functions
# ----------------------------------------------------------------------------------------------------------------------

def plain_add(x, y=1):
    """docstring of plain_add"""
    return x + y


def test_function_call_creates_one_ok_span_named_after_module_and_qualname(otw, spans):
    wrapped = otw.instrument_decorate(plain_add)
    assert wrapped(1, y=2) == 3

    records = spans.records()
    assert [s['name'] for s in records] == [expected_name(plain_add)]
    assert records[0]['status'] == 'OK'
    assert records[0]['kind'] == 'INTERNAL'
    assert records[0]['parent'] is None


def test_decorated_function_keeps_metadata(otw, spans):
    wrapped = otw.instrument_decorate(plain_add)
    assert wrapped.__name__ == 'plain_add'
    assert wrapped.__qualname__ == 'plain_add'
    assert wrapped.__doc__ == 'docstring of plain_add'
    assert wrapped.__wrapped__ is plain_add
    assert inspect.signature(wrapped) == inspect.signature(plain_add)


def attrs_target(x):
    return x


@pytest.mark.v0_specific  # deprecated `code.*` keys; v1 switches to the stable ones (DEC-31)
def test_function_span_has_deprecated_code_attributes(otw, spans):
    otw.instrument_decorate(attrs_target)(1)
    (record,) = spans.records()
    assert record['attributes'] == {
        'code.function':  'attrs_target',
        'code.namespace': __name__,
        'code.filepath':  str(Path(__file__)),
        'code.lineno':    attrs_target.__code__.co_firstlineno,
    }


def stable_attrs_target(x):
    return x


@pytest.mark.xfail(strict=True, reason='v0 bug list "Update CodeInfo": emit the stable code.function.name / '
                                       'code.file.path / code.line.number instead of the deprecated keys')
def test_function_span_has_stable_code_attributes(otw, spans):
    otw.instrument_decorate(stable_attrs_target)(1)
    (record,) = spans.records()
    attributes = record['attributes']
    assert attributes['code.function.name'] == f'{__name__}.stable_attrs_target'
    assert Path(attributes['code.file.path']) == Path(__file__)
    assert attributes['code.line.number'] == stable_attrs_target.__code__.co_firstlineno


def raises_value_error():
    raise ValueError('boom')


def test_exception_propagates_and_span_is_error_with_exception_event(otw, spans):
    wrapped = otw.instrument_decorate(raises_value_error)
    with pytest.raises(ValueError, match='boom'):
        wrapped()
    (record,) = spans.records()
    assert record['name'] == expected_name(raises_value_error)
    assert record['status'] == 'ERROR'
    assert 'exception' in record['events']


def nested_inner():
    return 1


def nested_outer(inner):
    return inner() + inner()


def test_nested_decorated_calls_are_parent_and_children(otw, spans):
    inner = otw.instrument_decorate(nested_inner)
    outer = otw.instrument_decorate(nested_outer)
    assert outer(inner) == 2

    records = spans.records()
    expected = [expected_name(nested_outer)] + [expected_name(nested_inner)] * 2
    assert sorted(s['name'] for s in records) == sorted(expected)
    outer_record = [s for s in records if s['name'] == expected_name(nested_outer)][0]
    for s in records:
        assert s['trace_id'] == outer_record['trace_id']
        if s is not outer_record:
            assert s['parent'] == expected_name(nested_outer)


def lambda_holder():
    return lambda: 42


def make_closure():
    def local_closure():
        return 7

    return local_closure


def test_lambda_and_closure_names(otw, spans):
    fn = lambda_holder()
    assert otw.instrument_decorate(fn)() == 42
    closure = make_closure()
    assert otw.instrument_decorate(closure)() == 7
    assert spans.names() == [f'<{__name__}>.lambda_holder.<locals>.<lambda>',
                             f'<{__name__}>.make_closure.<locals>.local_closure']


def renamed_target():
    return 'x'


def test_func_name_override_via_partial(otw, spans):
    # documented in the docstring of instrument_decorate
    decorated = functools.partial(otw.instrument_decorate, func_name='custom span name')(renamed_target)
    assert decorated() == 'x'
    assert spans.names() == ['custom span name']


def test_builtin_function(otw, spans):
    wrapped = otw.instrument_decorate(len)
    assert wrapped([1, 2, 3]) == 3
    assert spans.names() == ['<builtins>.len']


# ----------------------------------------------------------------------------------------------------------------------
# idempotency
# ----------------------------------------------------------------------------------------------------------------------

def idempotent_target():
    return 'ok'


def test_decorating_twice_gives_one_span_and_the_same_wrapper(otw, spans):
    once = otw.instrument_decorate(idempotent_target)
    twice = otw.instrument_decorate(otw.instrument_decorate(idempotent_target))
    later = otw.instrument_decorate(idempotent_target)  # decorating the original again, later on
    again = otw.instrument_decorate(once)  # decorating the wrapper
    assert once is twice is later is again

    assert twice() == 'ok'
    assert spans.names() == [expected_name(idempotent_target)]


def lru_target(x):
    return x * 2


def test_decorating_an_lru_cache_over_an_instrumented_function_adds_no_second_span(otw, spans):
    # same stack as `multiply` in experiment_otel_logging.py: @instrument_decorate @lru_cache @instrument_decorate
    inner = otw.instrument_decorate(lru_target)
    cached = functools.lru_cache(inner)
    outer = otw.instrument_decorate(cached)
    assert outer is cached  # recognised as already instrumented underneath, so returned unchanged

    assert outer(2) == 4
    assert outer(2) == 4  # cache hit, the instrumented function is not called again
    assert spans.names() == [expected_name(lru_target)]


def partial_target(a, b):
    return a + b


def test_partial_of_an_instrumented_function_is_returned_unchanged(otw, spans):
    inner = otw.instrument_decorate(partial_target)
    part = functools.partial(inner, 1)
    assert otw.instrument_decorate(part) is part
    assert part(2) == 3
    assert spans.names() == [expected_name(partial_target)]


# ----------------------------------------------------------------------------------------------------------------------
# coroutines
# ----------------------------------------------------------------------------------------------------------------------

async def async_double(x):
    await asyncio.sleep(0)
    return x * 2


def test_async_function_span_is_prefixed_with_async(otw, spans):
    wrapped = otw.instrument_decorate(async_double)
    assert inspect.iscoroutinefunction(wrapped)
    assert asyncio.run(wrapped(21)) == 42

    records = spans.records()
    assert [s['name'] for s in records] == [f'async {expected_name(async_double)}']
    assert records[0]['status'] == 'OK'
    assert records[0]['attributes']['code.function'] == 'async_double'


async def async_raises():
    raise KeyError('nope')


def test_async_exception_propagates_and_span_is_error(otw, spans):
    wrapped = otw.instrument_decorate(async_raises)
    with pytest.raises(KeyError):
        asyncio.run(wrapped())
    (record,) = spans.records()
    assert record['status'] == 'ERROR'
    assert 'exception' in record['events']


async def async_inner_leaf():
    return 1


async def async_outer_node(leaf):
    return await leaf() + await leaf()


def test_nested_async_calls_are_parent_and_children(otw, spans):
    leaf = otw.instrument_decorate(async_inner_leaf)
    node = otw.instrument_decorate(async_outer_node)
    assert asyncio.run(node(leaf)) == 2
    records = spans.records()
    children = [s for s in records if s['name'] == f'async {expected_name(async_inner_leaf)}']
    assert len(children) == 2
    assert all(s['parent'] == f'async {expected_name(async_outer_node)}' for s in children)


def test_asgiref_async_to_sync_wrapper_is_labelled(otw, spans):
    from asgiref.sync import async_to_sync

    async def converted(x):
        return x + 1

    wrapped = otw.instrument_decorate(async_to_sync(converted))
    assert wrapped(1) == 2
    assert spans.names() == [f'asgiref.sync.AsyncToSync <{__name__}>.{converted.__qualname__}']


# ----------------------------------------------------------------------------------------------------------------------
# methods of classes that are NOT themselves instrumented
# ----------------------------------------------------------------------------------------------------------------------

class PlainThing:
    def method(self, x):
        return x

    @staticmethod
    def static(x):
        return x

    @classmethod
    def clsmeth(cls, x):
        return x


def test_bound_method_static_method_and_classmethod(otw, spans):
    thing = PlainThing()
    assert otw.instrument_decorate(thing.method)(1) == 1
    assert otw.instrument_decorate(PlainThing.static)(2) == 2
    assert otw.instrument_decorate(PlainThing.clsmeth)(3) == 3
    assert spans.names() == [f'<{__name__}>.PlainThing.method',
                             f'<{__name__}>.PlainThing.static',
                             f'<{__name__}>.PlainThing.clsmeth']


def test_bound_method_code_function_attribute_drops_the_class_name(otw, spans):
    otw.instrument_decorate(PlainThing().method)(1)
    (record,) = spans.records()
    assert record['attributes']['code.function'] == 'method'
    assert record['attributes']['code.namespace'] == __name__


# ----------------------------------------------------------------------------------------------------------------------
# generators (v1 will have real generator spans, DEC-22)
# ----------------------------------------------------------------------------------------------------------------------

def generator_child():
    return 'child'


def generator_target(child):
    yield child()
    yield child()


@pytest.mark.v0_specific
def test_generator_span_only_covers_creating_the_generator(otw, spans):
    child = otw.instrument_decorate(generator_child)
    gen = otw.instrument_decorate(generator_target)
    assert list(gen(child)) == ['child', 'child']

    records = spans.records()
    assert sorted(s['name'] for s in records) == sorted([expected_name(generator_target)] +
                                                        [expected_name(generator_child)] * 2)
    # the generator's span already ended when the generator object was returned, so the body's spans are roots
    for s in records:
        assert s['parent'] is None


# ----------------------------------------------------------------------------------------------------------------------
# "never crash" (charter goal G-3); the v0 bug list found these holes by reading the code
# ----------------------------------------------------------------------------------------------------------------------

def partial_fresh_target(a, b):
    return a * b


class CallableInstance:
    def __call__(self, x):
        return x


@pytest.mark.v0_specific
def test_currently_raises_for_unsupported_objects(otw):
    with pytest.raises(TypeError):
        otw.instrument_decorate(functools.partial(partial_fresh_target, 2))  # partial of an un-instrumented function
    with pytest.raises(TypeError):
        otw.instrument_decorate(CallableInstance())
    with pytest.raises(AssertionError):  # not even a TypeError: CodeInfo's __post_init__ asserts
        otw.instrument_decorate(42)


@pytest.mark.xfail(strict=True, reason='v0 bug list "Never crash holes in instrument_decorate": raises TypeError for '
                                       'unsupported types (instrument_decorator.py:107)')
@pytest.mark.parametrize('make', [
    pytest.param(lambda: functools.partial(partial_fresh_target, 3), id='functools.partial'),
    pytest.param(CallableInstance, id='callable instance'),
])
def test_decorating_unsupported_callables_does_not_crash(otw, make):
    obj = make()
    wrapped = otw.instrument_decorate(obj)
    assert wrapped(5) == obj(5)
