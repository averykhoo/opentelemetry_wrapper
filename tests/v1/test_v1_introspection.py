"""
v1's introspection (OTW-5, AC-10, DEC-21, DEC-31, DEC-47): every row of the evidence table gives the right name, file
and line, read from the same object, with no source file and no strong reference to a user object

the table is `docs/evidence/v1-design-evidence-2026-10-18.md` § Introspection. `describe` is pure, so its rows run in
this process; what a span carries (decorators, `with` blocks) and what survives garbage collection run as scenarios
"""
import gc
import inspect
import linecache
import os
import sys
import weakref
from functools import cached_property
from functools import lru_cache
from functools import partial
from functools import singledispatch
from functools import wraps

import pytest

from opentelemetry_wrapper.v1 import _introspect
from tests.v0._harness import scenario
from tests.v1._prelude import PRELUDE

pytestmark = pytest.mark.criterion('AC-10')  # every test here claims the introspection criterion

THIS_FILE = os.path.abspath(__file__)
MODULE = __name__


# ----------------------------------------------------------------------------------------------------------------------
# one object per row of the table, each with a different decorator or none
# ----------------------------------------------------------------------------------------------------------------------

def plain(x):
    return x


async def async_plain(x):
    return x


def make_closure():
    def closure():
        pass

    return closure


closure = make_closure()
lambda_function = lambda: None  # noqa: E731


def passthrough(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


@passthrough
def wrapped_with_wraps():
    pass


def no_wraps(func):
    """a decorator that sets `__wrapped__` by hand, with its own name, module and code"""

    def other_name(*args, **kwargs):
        return func(*args, **kwargs)

    other_name.__wrapped__ = func
    return other_name


@no_wraps
def wrapped_by_hand():
    pass


@no_wraps
@passthrough
@no_wraps
def wrapped_three_deep():
    pass


@lru_cache(maxsize=None)
def cached(x):
    return x


@singledispatch
def dispatched(x):
    return x


@dispatched.register(int)
def _dispatched_int(x):
    return x


class Thing:
    def method(self):
        pass

    @classmethod
    def class_method(cls):
        pass

    @staticmethod
    def static_method():
        pass

    @cached_property
    def lazy(self):
        return 1

    @property
    def prop(self):
        return 1


class Outer:
    class Inner:
        pass


class Callable:
    def __call__(self, x):
        return x


class Child(Callable):
    pass


class WrapperInstance:
    """a callable object that carries `__wrapped__` itself (`update_wrapper` on an instance)"""

    def __init__(self, func):
        self.__wrapped__ = func

    def __call__(self, *args, **kwargs):
        return self.__wrapped__(*args, **kwargs)


class Looping:
    @property
    def __wrapped__(self):
        return self

    def __call__(self):
        pass


class Hostile:
    """everything raises"""

    @property
    def __wrapped__(self):
        raise RuntimeError('boom')

    def __getattr__(self, item):
        raise RuntimeError('boom')

    def __call__(self):
        pass


def code_of(func):
    return func.__code__


# (id, target, expected name, code object whose file and line are expected or None for none)
FUNCTION_ROWS = [
    ('plain function', plain, f'{MODULE}.plain', code_of(plain)),
    ('async function', async_plain, f'{MODULE}.async_plain', code_of(async_plain)),
    ('closure', closure, f'{MODULE}.make_closure.<locals>.closure', code_of(closure)),
    ('lambda', lambda_function, f'{MODULE}.<lambda>', code_of(lambda_function)),
    ('@wraps', wrapped_with_wraps, f'{MODULE}.wrapped_with_wraps', code_of(wrapped_with_wraps.__wrapped__)),
    ('__wrapped__ without @wraps', wrapped_by_hand, f'{MODULE}.wrapped_by_hand', code_of(wrapped_by_hand.__wrapped__)),
    ('three wrappers deep', wrapped_three_deep, f'{MODULE}.wrapped_three_deep',
     code_of(wrapped_three_deep.__wrapped__.__wrapped__.__wrapped__)),
    ('lru_cache', cached, f'{MODULE}.cached', code_of(cached.__wrapped__)),
    ('singledispatch', dispatched, f'{MODULE}.dispatched', code_of(dispatched.__wrapped__)),
    ('singledispatch registration', dispatched.registry[int], f'{MODULE}._dispatched_int',
     code_of(dispatched.registry[int])),
    ('staticmethod (accessed)', Thing.static_method, f'{MODULE}.Thing.static_method', code_of(Thing.static_method)),
    ('staticmethod (in __dict__)', vars(Thing)['static_method'], f'{MODULE}.Thing.static_method',
     code_of(Thing.static_method)),
    ('bound method', Thing().method, f'{MODULE}.Thing.method', code_of(Thing.method)),
    ('unbound method', Thing.method, f'{MODULE}.Thing.method', code_of(Thing.method)),
    ('classmethod (bound)', Thing.class_method, f'{MODULE}.Thing.class_method', code_of(Thing.class_method.__func__)),
    ('classmethod (in __dict__)', vars(Thing)['class_method'], f'{MODULE}.Thing.class_method',
     code_of(Thing.class_method.__func__)),
    ('cached_property', vars(Thing)['lazy'], f'{MODULE}.Thing.lazy', code_of(vars(Thing)['lazy'].func)),
    ('property', vars(Thing)['prop'], f'{MODULE}.Thing.prop', code_of(vars(Thing)['prop'].fget)),
    ('partial', partial(plain, 1), f'{MODULE}.plain', code_of(plain)),
    ('partial of a partial of a bound method', partial(partial(Thing().method)), f'{MODULE}.Thing.method',
     code_of(Thing.method)),
    ('callable instance', Callable(), f'{MODULE}.Callable.__call__', code_of(Callable.__call__)),
    ('callable instance inheriting __call__', Child(), f'{MODULE}.Callable.__call__', code_of(Callable.__call__)),
    ('partial of a callable instance', partial(Callable(), 1), f'{MODULE}.Callable.__call__',
     code_of(Callable.__call__)),
    ('callable instance with __wrapped__', WrapperInstance(plain), f'{MODULE}.plain', code_of(plain)),
    ('wrapper over a callable instance', no_wraps(Callable()), f'{MODULE}.Callable.__call__',
     code_of(Callable.__call__)),
]


def attributes_of(target):
    name, attributes = _introspect.describe(target)
    assert attributes[_introspect.CODE_FUNCTION_NAME] == name
    return name, attributes


@pytest.mark.parametrize('row', FUNCTION_ROWS, ids=[row[0] for row in FUNCTION_ROWS])
def test_every_routine_row_gives_the_right_name_file_and_line_from_one_object(row):  # AC-10
    _, target, expected_name, code = row
    name, attributes = attributes_of(target)
    assert name == expected_name
    assert attributes[_introspect.CODE_FILE_PATH] == THIS_FILE
    assert attributes[_introspect.CODE_LINE_NUMBER] == code.co_firstlineno
    assert set(attributes) == {_introspect.CODE_FUNCTION_NAME, _introspect.CODE_FILE_PATH,
                               _introspect.CODE_LINE_NUMBER}


def test_the_name_and_the_line_never_come_from_different_objects():  # AC-10 (v0 took name and line from two objects)
    name, attributes = attributes_of(wrapped_by_hand)
    assert name.endswith('.wrapped_by_hand') and 'other_name' not in name
    assert attributes[_introspect.CODE_LINE_NUMBER] != code_of(no_wraps(plain)).co_firstlineno
    # a wrapper that names itself and wraps something else: still the wrapped, wholly
    wrapper = no_wraps(plain)
    wrapper.__name__, wrapper.__qualname__, wrapper.__module__ = 'liar', 'liar', 'elsewhere'
    name, attributes = attributes_of(wrapper)
    assert name == f'{MODULE}.plain' and attributes[_introspect.CODE_LINE_NUMBER] == code_of(plain).co_firstlineno


def test_builtin_gives_a_name_and_no_file_or_line():  # AC-10
    name, attributes = attributes_of(len)
    assert name == 'builtins.len'
    assert _introspect.CODE_FILE_PATH not in attributes and _introspect.CODE_LINE_NUMBER not in attributes
    assert attributes_of([].append)[0] == 'list.append'


def test_class_gives_module_qualname_and_the_file_and_never_a_wrong_line():  # AC-10
    name, attributes = attributes_of(Outer.Inner)
    assert name == f'{MODULE}.Outer.Inner'
    assert attributes[_introspect.CODE_FILE_PATH] == THIS_FILE
    assert attributes[_introspect.IS_CLASS] is True
    # `Thing` has methods: on 3.12, which records no class line, their lines would be wrong, so none is given
    thing = attributes_of(Thing)[1]
    if hasattr(Thing, '__firstlineno__'):  # 3.13+
        assert thing[_introspect.CODE_LINE_NUMBER] == Thing.__firstlineno__
    else:
        assert _introspect.CODE_LINE_NUMBER not in thing


def test_class_line_is_the_one_python_records():  # AC-10
    class Local:
        pass

    Local.__firstlineno__ = 4242  # what 3.13+ sets itself
    assert attributes_of(Local)[1][_introspect.CODE_LINE_NUMBER] == 4242


def test_a_routine_is_not_marked_as_a_class():  # AC-10
    assert _introspect.IS_CLASS not in attributes_of(plain)[1]


def test_file_path_is_absolute_when_the_code_has_a_relative_file_name():  # AC-10 (DEC-31: absolute preferred)
    code = compile('def relative():\n    pass\n', os.path.join('some', 'dir', 'file.py'), 'exec')
    namespace = {'__name__': 'fake.module'}
    exec(code, namespace)
    name, attributes = attributes_of(namespace['relative'])
    assert name == 'fake.module.relative'
    assert attributes[_introspect.CODE_FILE_PATH] == os.path.abspath(os.path.join('some', 'dir', 'file.py'))
    assert attributes[_introspect.CODE_LINE_NUMBER] == 1


def test_no_source_file_is_needed(monkeypatch):  # AC-10
    callers = []

    def spy(original):
        def spied(*args, **kwargs):
            frame = sys._getframe(1)
            while frame is not None:  # pytest itself reads source (to print a failure): only our own callers count
                if frame.f_globals.get('__name__', '').startswith('opentelemetry_wrapper'):
                    callers.append(original.__name__)
                    break
                frame = frame.f_back
            return original(*args, **kwargs)

        return spied

    for module, names in ((inspect, ('getsource', 'getsourcelines', 'getsourcefile', 'findsource', 'getfile',
                                     'getabsfile')),
                          (linecache, ('getlines', 'getline', 'updatecache', 'checkcache'))):
        for attr in names:
            monkeypatch.setattr(module, attr, spy(getattr(module, attr)))
    ghost_file = os.path.abspath(os.path.join(os.sep, 'nonexistent', 'ghost.py'))
    code = compile('def ghost():\n    pass\n\n\nclass Ghost:\n    pass\n', ghost_file, 'exec')
    namespace = {'__name__': 'ghost'}
    exec(code, namespace)
    name, attributes = attributes_of(namespace['ghost'])
    assert (name, attributes[_introspect.CODE_FILE_PATH], attributes[_introspect.CODE_LINE_NUMBER]) \
           == ('ghost.ghost', ghost_file, 1)
    for _, target, expected_name, _ in FUNCTION_ROWS:
        assert attributes_of(target)[0] == expected_name
    attributes_of(namespace['Ghost'])
    attributes_of(Outer.Inner)
    assert callers == []


def test_a_hostile_or_endless_wrapped_chain_never_raises():  # AC-10, AC-7
    for target in (Looping(), Hostile(), object(), 42, None):
        name, attributes = _introspect.describe(target)
        assert isinstance(name, str) and name
        assert attributes[_introspect.CODE_FUNCTION_NAME] == name


def test_the_name_has_no_object_address():  # AC-10 (high cardinality, evidence: cached_property)
    for _, target, _, _ in FUNCTION_ROWS:
        assert ' at 0x' not in attributes_of(target)[0]
    assert ' at 0x' not in attributes_of(object())[0]


# ----------------------------------------------------------------------------------------------------------------------
# what spans carry
# ----------------------------------------------------------------------------------------------------------------------

SPANS = scenario(__name__, 'v1_introspection_spans', PRELUDE + r'''
import asyncio, functools, os
from functools import partial, lru_cache

HERE = os.path.abspath(__file__)

def no_wraps(func):
    def other_name(*args, **kwargs):
        return func(*args, **kwargs)
    other_name.__wrapped__ = func
    return other_name

def plain():
    pass

class Callable:
    def __call__(self):
        pass

class Thing:
    def method(self):
        pass

def run():
    pass

expected = {}
for label, target, func in (
        ('plain', plain, plain), ('by hand', no_wraps(plain), plain), ('callable', Callable(), Callable.__call__),
        ('method', Thing().method, Thing.method), ('partial', partial(plain), plain),
        ('lru_cache', lru_cache()(plain), plain)):
    expected[label] = [f'__main__.{func.__qualname__}', func.__code__.co_firstlineno]
    wrapper = otel(target)
    wrapper()
    wrapper2 = otel(wrapper)  # idempotent: no second wrapper
    assert wrapper2 is wrapper
spans = take(exporter)
emit('expected', expected)
emit('decorated', [[s['name'], s['attributes']['code.function.name'], s['attributes']['code.file.path'] == HERE,
                    s['attributes']['code.line.number']] for s in spans])
emit('here_is_absolute', os.path.isabs(HERE))

@otel(name='custom')
def with_name():
    pass
with_name()
emit('custom', take(exporter)[0]['attributes'])
emit('with_name_line', with_name.__wrapped__.__code__.co_firstlineno)
''')


def test_decorated_spans_carry_the_name_file_and_line_of_the_underlying_target():  # AC-10
    result = SPANS.result()
    expected = list(result['expected'].values())
    decorated = result['decorated']
    assert len(decorated) == len(expected)
    for (name, code_name, same_file, line), (expected_name, expected_line) in zip(decorated, expected):
        assert name == code_name == expected_name
        assert same_file is True
        assert line == expected_line


def test_a_custom_span_name_still_carries_the_code_of_the_target():  # AC-10
    attributes = SPANS.result()['custom']
    assert attributes['code.function.name'] == '__main__.with_name'
    assert attributes['code.line.number'] == SPANS.result()['with_name_line']


BLOCKS = scenario(__name__, 'v1_introspection_blocks', PRELUDE + r'''
import asyncio, os
HERE = os.path.abspath(__file__)

def where():
    return sys._getframe(1).f_lineno

import sys

def sync_blocks():
    lines = {}
    lines['unnamed'] = where() + 1
    with otel:
        pass
    lines['named'] = where() + 1
    with otel('named', attributes={'k': 'v'}):
        pass
    lines['empty call'] = where() + 1
    with otel():
        pass
    return lines

async def async_blocks():
    lines = {}
    lines['async named'] = where() + 1
    async with otel('async named'):
        pass
    lines['async unnamed'] = where() + 1
    async with otel:
        pass
    return lines

class Service:
    def handle(self):
        line = where() + 1
        with otel('in method'):
            return line

lines = sync_blocks()
lines.update(asyncio.run(async_blocks()))
lines['in method'] = Service().handle()
lines['module level'] = where() + 1
with otel('module level'):
    pass
spans = {s['name']: s for s in take(exporter)}
emit('lines', lines)
emit('attributes', {name: [s['attributes'].get('code.function.name'), s['attributes'].get('code.file.path') == HERE,
                           s['attributes'].get('code.line.number'), s['attributes'].get('k')]
                    for name, s in spans.items()})

# the same block twice from one line (a loop): one name, same line
for _ in range(2):
    with otel('loop'):
        pass
emit('loop', [[s['attributes']['code.line.number']] for s in take(exporter)])
''')


def test_named_blocks_record_code_attributes_from_the_callers_frame():  # AC-10 (DEC-21, review item 11)
    result = BLOCKS.result()
    attributes = result['attributes']
    assert attributes['named'] == ['__main__.sync_blocks', True, result['lines']['named'], 'v']
    assert attributes['async named'] == ['__main__.async_blocks', True, result['lines']['async named'], None]
    assert attributes['module level'] == ['__main__.<module>', True, result['lines']['module level'], None]


def test_unnamed_blocks_are_named_after_the_enclosing_function_with_the_line_in_the_attribute():  # AC-10 (DEC-47)
    result = BLOCKS.result()
    attributes = result['attributes']
    assert attributes['__main__.sync_blocks'][0] == '__main__.sync_blocks'
    assert attributes['__main__.sync_blocks'][2] in (result['lines']['unnamed'], result['lines']['empty call'])
    assert attributes['__main__.async_blocks'] == ['__main__.async_blocks', True, result['lines']['async unnamed'],
                                                   None]


def test_a_block_in_a_method_gets_the_methods_qualified_name():  # AC-10
    result = BLOCKS.result()
    assert result['attributes']['in method'][:3] == ['__main__.Service.handle', True, result['lines']['in method']]


def test_the_same_block_run_twice_reports_the_same_line():  # AC-10
    assert len({tuple(line) for line in BLOCKS.result()['loop']}) == 1


# ----------------------------------------------------------------------------------------------------------------------
# no strong references to user objects
# ----------------------------------------------------------------------------------------------------------------------

def _dead_after_collect(*refs):
    for _ in range(3):
        gc.collect()
    return [ref() is None for ref in refs]


def test_describing_holds_no_reference_to_a_function_a_class_or_a_callable_instance():  # AC-10
    def make():
        def local_function():
            pass

        class LocalClass:
            def __call__(self):
                pass

        instance = LocalClass()
        for target in (local_function, LocalClass, instance, partial(instance), instance.__call__):
            _introspect.describe(target)
        return weakref.ref(local_function), weakref.ref(LocalClass), weakref.ref(instance)

    assert _dead_after_collect(*make()) == [True, True, True]


def test_decorating_holds_no_reference_to_a_function_a_method_or_a_callable_instance():  # AC-10
    from opentelemetry_wrapper.v1 import otel

    def make():
        def local_function():
            pass

        class LocalClass:
            def __call__(self):
                pass

            def method(self):
                pass

        instance = LocalClass()
        wrappers = [otel(local_function), otel(instance), otel(instance.method), otel(partial(local_function))]
        assert all(w is not None for w in wrappers)
        return weakref.ref(local_function), weakref.ref(LocalClass), weakref.ref(instance), weakref.ref(wrappers[0])

    assert _dead_after_collect(*make()) == [True, True, True, True]


def test_call_site_cache_holds_no_reference_to_code_it_has_seen():  # AC-10
    namespace = {'__name__': 'dynamic'}
    exec(compile('def block(otel):\n    with otel:\n        pass\n    with otel("x"):\n        pass\n',
                 '<dynamic>', 'exec'), namespace)
    block = namespace['block']
    code_ref = weakref.ref(block.__code__)
    function_ref = weakref.ref(block)
    frame_seen = []

    class Probe:  # stands in for `otel`: enters through the real object, recording nothing else
        def __enter__(self):
            frame_seen.append(_introspect.call_site(sys._getframe(1)))
            frame_seen.append(_introspect.unnamed_call_site(sys._getframe(1)))

        def __exit__(self, *args):
            return None

        def __call__(self, name):
            return self

    block(Probe())
    assert len(frame_seen) == 4 and frame_seen[0][0] == 'dynamic.block'
    del block, namespace
    assert _dead_after_collect(code_ref, function_ref) == [True, True]


GC_SCENARIO = scenario(__name__, 'v1_introspection_gc', PRELUDE + r'''
import gc, weakref

def build():
    def local_function():
        return 1

    class LocalClass:
        def __call__(self):
            return 2

        def method(self):
            return 3

    namespace = {'__name__': 'dynamic'}
    exec(compile('def block():\n    with otel("dyn"):\n        return 4\n', '<dynamic>', 'exec'),
         {**namespace, 'otel': otel}, namespace)
    block = namespace['block']
    instance = LocalClass()
    wrappers = [otel(local_function), otel(instance), otel(instance.method), otel(block)]
    results = [w() for w in wrappers]  # calls run, spans are made and ended
    with otel('plain block'):
        pass
    refs = [weakref.ref(x) for x in (local_function, LocalClass, instance, block, block.__code__, wrappers[0])]
    return results, refs

results, refs = build()
for _ in range(3):
    gc.collect()
emit('results', results)
emit('dead', [r() is None for r in refs])
emit('spans', len(take(exporter)))
''')


def test_functions_instances_and_code_are_collectable_after_their_spans_have_run():  # AC-10
    result = GC_SCENARIO.result()
    assert result['results'] == [1, 2, 3, 4]
    assert result['spans'] == 6  # four calls, the block inside the exec'd function, and the plain block
    assert result['dead'] == [True] * 6
