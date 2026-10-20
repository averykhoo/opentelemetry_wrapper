"""
class and dataclass instrumentation (charter goal G-6)

these run in fresh interpreters: v0 wraps `__getattribute__` only for the FIRST class it instruments (see the
first-class bug below), so in a shared process the results would depend on test order

the scenarios run against v1's `@otel` on classes (OTW-6), with v1's span names (`span()` below), properties asked
for with `properties=True` (opt-in, DEC-53), one span from `__enter__` to `__exit__` (DEC-22) and `@otel` on each
dataclass in place of v0's `instrument_dataclasses()` (dropped, DEC-42). the tests that claim AC-11 pin the v0 class
bugs v1 fixes
"""
import pytest

from tests.v0._harness import scenario


def span(qualname):
    """the span name of `__main__.<qualname>`, with no `async ` / `property ` prefix (v0's was
    `<__main__>.<qualname>`, with one; DEC-47, DEC-52)"""
    return f'__main__.{qualname}'


CLASSES = scenario(__name__, 'classes', r'''
import asyncio, functools, gc, weakref
from tests.impl import decorate
exp = setup_spans()
decorate_class = lambda cls: decorate(cls, properties=True)  # properties are opt-in (DEC-53)

class First:
    attr = 1

    def __new__(cls, *args, **kwargs):
        return super().__new__(cls)

    def __init__(self):
        self.value = 2

    def method(self):
        return self.helper()

    def helper(self):
        return 3

    async def amethod(self):
        return 4

    def raises(self):
        raise RuntimeError('boom')

    @decorate  # also decorated explicitly, inside a class that gets instrumented
    def predecorated(self):
        return 11

    @property
    def prop(self):
        return 5

    @functools.cached_property
    def cprop(self):
        return 6

    @staticmethod
    def static():
        return 7

    @classmethod
    def clsmeth(cls):
        return 8

    def __call__(self):
        return 9

    def __len__(self):
        return 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    class Nested:
        def nested_method(self):
            return 10

emit('decorate_returns_same_class', decorate_class(First) is First)
emit('decorate_twice_returns_same_class', decorate(decorate(First)) is First)
take(exp)

x = First();                        emit('construct', take(exp))
assert x.method() == 3;             emit('method', take(exp))
x.method();                         emit('method_again', take(exp))
assert asyncio.run(x.amethod()) == 4; emit('async_method', take(exp))
try:
    x.raises()
except RuntimeError:
    emit('exception_propagates', True)
emit('raising_method', take(exp))
assert x.prop == 5;                 emit('property', take(exp))
x.cprop; x.cprop;                   emit('cached_property_twice', take(exp))
assert x.static() == 7;             emit('staticmethod', take(exp))
assert x.clsmeth() == 8;            emit('classmethod', take(exp))
assert x() == 9;                    emit('call', take(exp))
len(x);                             emit('len_builtin', take(exp))
x.__len__();                        emit('dunder_len_explicit', take(exp))
with x:
    pass
emit('context_manager', take(exp))
x.attr; x.value; x.__class__;       emit('plain_attributes', take(exp))
x.predecorated();                   emit('predecorated_method', take(exp))
x.__call__();                       emit('dunder_call_explicit', take(exp))
x.__enter__()
x.__exit__(None, None, None)  # one span from `__enter__` to `__exit__` (DEC-22), so close it
emit('dunder_enter_explicit', take(exp))
assert x.Nested().nested_method() == 10; emit('nested_class', take(exp))

decorate(First)
y = First(); y.method();            emit('after_decorating_again', take(exp))

# a second, unrelated class
@decorate_class
class Second:
    def __init__(self):
        pass

    def method(self):
        return 1

    @property
    def prop(self):
        return 2

s = Second();                       emit('second_construct', take(exp))
s.method(); s.prop;                 emit('second_method_and_property', take(exp))

# memory: instances whose methods were accessed vs. never accessed
ref_used = weakref.ref(x)
del x, y
w = First()
ref_unused = weakref.ref(w)
del w
gc.collect()
emit('used_instance_alive_after_del', ref_used() is not None)
emit('unused_instance_alive_after_del', ref_unused() is not None)
''')

DATACLASSES = scenario(__name__, 'dataclasses', r'''
import dataclasses
from tests.impl import decorate
exp = setup_spans()

def dataclass(cls=None, **kwargs):  # v1 drops instrument_dataclasses() (DEC-42): `@otel` over each `@dataclass`
    if cls is None:
        return lambda cls: decorate(dataclasses.dataclass(cls, **kwargs))
    return decorate(dataclasses.dataclass(cls))

@dataclass
class Point:
    x: int
    y: int = 0

    def __post_init__(self):
        self.norm = abs(self.x) + abs(self.y)

    def scaled(self, k):
        return Point(self.x * k, self.y * k)

p = Point(1, 2)
emit('point_fields', [p.x, p.y, p.norm])
emit('construct', take(exp))
q = p.scaled(2)
emit('scaled', [q.x, q.y])
emit('method', take(exp))
emit('equality_still_works', Point(1, 2) == Point(1, 2))
take(exp)

@dataclass(frozen=True)
class Frozen:
    a: int

    def double(self):
        return self.a * 2

f = Frozen(3)
emit('frozen_construct', take(exp))
emit('frozen_double', f.double())
emit('frozen_method', take(exp))
try:
    f.a = 4
except dataclasses.FrozenInstanceError:
    emit('frozen_still_frozen', True)
take(exp)
''')


NO_SOURCE = scenario(__name__, 'class_without_source', r'''
from tests.impl import decorate
exp = setup_spans()
decorate_class = lambda cls: decorate(cls, properties=True)
namespace = {}
source = "class NoSource:\n    def m(self):\n        return 1\n    @property\n    def p(self):\n        return 2\n"
exec(compile(source, '<generated>', 'exec'), namespace)  # like a frozen app: no source file to read
NoSource = decorate_class(namespace['NoSource'])
instance = NoSource()
emit('method', instance.m())
emit('method_spans', names(exp))
try:
    emit('property', instance.p)
except Exception as e:
    emit('property_error', f'{type(e).__name__}: {e}')
''')


@pytest.fixture(scope='module')
def classes():
    return CLASSES.result()


@pytest.fixture(scope='module')
def dataclasses_result():
    return DATACLASSES.result()


def names(records):
    return [r['name'] for r in records]


# ----------------------------------------------------------------------------------------------------------------------
# the first instrumented class
# ----------------------------------------------------------------------------------------------------------------------

def test_class_decoration_is_in_place_and_idempotent(classes):
    assert classes['decorate_returns_same_class'] is True
    assert classes['decorate_twice_returns_same_class'] is True


def test_constructor_spans(classes):
    assert names(classes['construct']) == [span('First.__new__'), span('First.__init__')]
    assert all(r['status'] == 'OK' for r in classes['construct'])


def test_method_spans_nest_for_calls_through_self(classes):
    records = classes['method']
    assert sorted(names(records)) == [span('First.helper'), span('First.method')]
    helper = [r for r in records if r['name'].endswith('.helper')][0]
    assert helper['parent'] == span('First.method')


def test_calling_a_method_twice_gives_one_span_per_call(classes):
    assert sorted(names(classes['method_again'])) == [span('First.helper'), span('First.method')]


def test_decorating_the_class_again_adds_no_spans(classes):
    assert sorted(names(classes['after_decorating_again'])) == sorted([
        span('First.__new__'), span('First.__init__'), span('First.method'), span('First.helper')])


def test_async_method(classes):
    assert names(classes['async_method']) == [span('First.amethod')]


def test_raising_method_propagates_and_is_error(classes):
    assert classes['exception_propagates'] is True
    (record,) = classes['raising_method']
    assert record['name'] == span('First.raises')
    assert record['status'] == 'ERROR'


def test_property_span(classes):
    (record,) = classes['property']
    assert record['name'] == span('First.prop')
    assert record['status'] == 'OK'


def test_staticmethod_and_classmethod(classes):
    assert names(classes['staticmethod']) == [span('First.static')]
    assert names(classes['classmethod']) == [span('First.clsmeth')]


def test_dunder_call(classes):
    assert names(classes['call']) == [span('First.__call__')]


def test_plain_attribute_access_is_not_traced(classes):
    assert classes['plain_attributes'] == []


# v0 bug (v0 bug list, 2nd section): a method already instrumented (decorated in the class body, or a dunder /
# __post_init__ wrapped by class instrumentation) was wrapped again when accessed through an instance: two nested spans
@pytest.mark.criterion('AC-11')
@pytest.mark.parametrize('key, name', [
    ('predecorated_method', span('First.predecorated')),
    ('dunder_call_explicit', span('First.__call__')),
    ('dunder_enter_explicit', span('First.__enter__')),
])
def test_already_instrumented_method_accessed_via_instance_gets_one_span(classes, key, name):
    assert names(classes[key]) == [name]


@pytest.mark.parametrize('key, name', [
    ('predecorated_method', span('First.predecorated')),
    ('dunder_call_explicit', span('First.__call__')),
    ('dunder_enter_explicit', span('First.__enter__')),
])
def test_already_instrumented_method_accessed_via_instance_is_traced(classes, key, name):
    # holds before and after the double-span fix above
    assert set(names(classes[key])) == {name}


# v0 bug (v0 bug list, 2nd section): only the first class instrumented in a process got method and property spans
# (_CACHE_GETATTRIBUTE was keyed by object.__getattribute__); nested classes counted as later ones
@pytest.mark.criterion('AC-11')
def test_nested_class_methods_are_traced(classes):
    assert names(classes['nested_class']) == [span('First.Nested.nested_method')]


# ----------------------------------------------------------------------------------------------------------------------
# a second instrumented class
# ----------------------------------------------------------------------------------------------------------------------

def test_second_class_constructor_is_traced(classes):
    assert names(classes['second_construct']) == [span('Second.__init__')]


@pytest.mark.criterion('AC-11')
def test_second_class_methods_and_properties_are_traced(classes):
    assert names(classes['second_method_and_property']) == [span('Second.method'), span('Second.prop')]


# ----------------------------------------------------------------------------------------------------------------------
# no source code available
# ----------------------------------------------------------------------------------------------------------------------

def test_class_without_source_methods_still_work():
    result = NO_SOURCE.result()
    assert result['method'] == 1
    assert result['method_spans'] == ['NoSource.m']  # no module or file to name it after


# v0 bug list "Never crash holes": every property access called inspect.getsourcelines, which raises OSError
@pytest.mark.criterion('AC-11')
def test_class_without_source_property_access_does_not_crash():
    result = NO_SOURCE.result()
    assert result.values.get('property_error') is None
    assert result['property'] == 2


# ----------------------------------------------------------------------------------------------------------------------
# memory
# ----------------------------------------------------------------------------------------------------------------------

def test_instance_without_method_access_is_freed(classes):
    assert classes['unused_instance_alive_after_del'] is False


# v0 bug list "Memory leak in class instrumentation": bound methods were cached forever, keeping their instance alive
@pytest.mark.criterion('AC-11')
def test_instance_is_freed_after_its_methods_were_used(classes):
    assert classes['used_instance_alive_after_del'] is False


# ----------------------------------------------------------------------------------------------------------------------
# dataclasses
# ----------------------------------------------------------------------------------------------------------------------

def test_dataclass_still_behaves_like_a_dataclass(dataclasses_result):
    assert dataclasses_result['point_fields'] == [1, 2, 3]
    assert dataclasses_result['scaled'] == [2, 4]
    assert dataclasses_result['equality_still_works'] is True
    assert dataclasses_result['frozen_double'] == 6
    assert dataclasses_result['frozen_still_frozen'] is True


def test_dataclass_constructor_and_post_init_spans(dataclasses_result):
    records = dataclasses_result['construct']
    assert set(names(records)) == {span('Point.__init__'), span('Point.__post_init__')}
    assert names(records).count(span('Point.__init__')) == 1
    assert any(r['parent'] == span('Point.__init__') for r in records if r['name'].endswith('__post_init__'))


@pytest.mark.criterion('AC-11')
def test_dataclass_post_init_gets_one_span(dataclasses_result):
    assert sorted(names(dataclasses_result['construct'])) == [span('Point.__init__'), span('Point.__post_init__')]


def test_dataclass_method_span(dataclasses_result):
    # `scaled` constructs another Point, so its constructor spans are children of the method span
    records = dataclasses_result['method']
    assert set(names(records)) == {span('Point.__init__'), span('Point.__post_init__'), span('Point.scaled')}
    assert names(records).count(span('Point.scaled')) == 1
    init = [r for r in records if r['name'].endswith('__init__')][0]
    assert init['parent'] == span('Point.scaled')


def test_dataclass_with_arguments_is_instrumented(dataclasses_result):
    # @dataclass(frozen=True) goes through the "decorator factory" path of the scenario's shim
    assert names(dataclasses_result['frozen_construct']) == [span('Frozen.__init__')]


@pytest.mark.criterion('AC-11')
def test_second_dataclass_method_is_traced(dataclasses_result):
    assert names(dataclasses_result['frozen_method']) == [span('Frozen.double')]
