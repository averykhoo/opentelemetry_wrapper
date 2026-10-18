"""
`CodeInfo` (v0/utils/introspect.py): the introspection table in docs/evidence/v1-design-evidence-2026-10-18.md
("Introspection: logfire covers plain functions only") plus the two confirmed bugs in the v0 bug list
("Update CodeInfo")

CodeInfo is internal, and v1 rewrites it (OTW-5, DEC-31: co_qualname, stable attribute keys), so the exact name
format here is v0-specific; the *coverage* (which kinds of callables get a name, file and line) is what v1 has to keep
"""
import asyncio
import functools
import gc
import weakref
from pathlib import Path

import pytest
from asgiref.sync import async_to_sync

from opentelemetry_wrapper.v0.utils.introspect import CodeInfo

pytestmark = pytest.mark.v0_specific

THIS_FILE = Path(__file__)
MOD = f'<{__name__}>.'


# ----------------------------------------------------------------------------------------------------------------------
# the cases from the evidence doc's table, all defined at module level so their names are predictable
# ----------------------------------------------------------------------------------------------------------------------

def plain_function():
    pass


async def async_function():
    pass


def closure_factory():
    def local():
        pass

    return local


module_lambda = lambda: 0  # noqa: E731


def _wraps_decorator(f):
    @functools.wraps(f)
    def inner(*args, **kwargs):
        return f(*args, **kwargs)

    return inner


@_wraps_decorator
def wraps_decorated():
    pass


@functools.lru_cache
def lru_cached(x):
    return x


@functools.singledispatch
def single_dispatched(x):
    return x


class Outer:
    class Inner:
        def method(self):
            pass

    def method(self):
        pass

    @staticmethod
    def static():
        pass

    @classmethod
    def clsmeth(cls):
        pass

    @functools.cached_property
    def cprop(self):
        return 1

    def __call__(self):
        pass


async def converted_coroutine():
    pass


def line_of(func) -> int:
    """`inspect.getsourcelines` line, which for a decorated function is its first decorator's line"""
    return func.__code__.co_firstlineno


CASES = {
    # tag: (object, expected name, expected (class_name, function_name), expected lineno, expect a path)
    'plain function':      (plain_function, f'{MOD}plain_function',
                            (None, 'plain_function'), line_of(plain_function), True),
    'async function':      (async_function, f'{MOD}async_function',
                            (None, 'async_function'), line_of(async_function), True),
    'closure':             (closure_factory(), f'{MOD}closure_factory.<locals>.local',
                            (None, 'closure_factory.<locals>.local'), line_of(closure_factory()), True),
    'lambda':              (module_lambda, f'{MOD}<lambda>', (None, '<lambda>'), line_of(module_lambda), True),
    'staticmethod':        (Outer.static, f'{MOD}Outer.static', ('Outer', 'static'), line_of(Outer.static), True),
    # NOTE: `_unwrap_partial` means to label this '@functools.wraps ...', but its for/else logic never returns that
    # label (the inner loop's `else: break` exits the outer loop), so the wrapper is not unwrapped; the name still
    # matches because @wraps copies __qualname__, and the line comes from inspect.getsourcelines, which unwraps
    'functools.wraps':     (wraps_decorated, f'{MOD}wraps_decorated',
                            (None, 'wraps_decorated'), line_of(wraps_decorated.__wrapped__), True),
    'lru_cache':           (lru_cached, f'@functools.lru_cache {MOD}lru_cached',
                            (None, 'lru_cached'), line_of(lru_cached.__wrapped__), True),
    'singledispatch':      (single_dispatched, f'@functools.singledispatch {MOD}single_dispatched',
                            (None, 'single_dispatched'), line_of(single_dispatched.__wrapped__), True),
    'bound method':        (Outer().method, f'{MOD}Outer.method', ('Outer', 'method'), line_of(Outer.method), True),
    'nested class method': (Outer.Inner().method, f'{MOD}Outer.Inner.method',
                            ('Inner', 'method'), line_of(Outer.Inner.method), True),
    'classmethod':         (Outer.clsmeth, f'{MOD}Outer.clsmeth', ('Outer', 'clsmeth'),
                            line_of(Outer.clsmeth.__func__), True),
    'cached_property':     (Outer.__dict__['cprop'], f'functools.cached_property {MOD}Outer.cprop',
                            ('Outer', 'cprop'), line_of(Outer.__dict__['cprop'].func), True),
    'builtin len':         (len, '<builtins>.len', (None, 'len'), None, False),
    'functools.partial':   (functools.partial(plain_function), f'functools.partial {MOD}plain_function',
                            (None, 'plain_function'), line_of(plain_function), True),
    'asgiref async_to_sync': (async_to_sync(converted_coroutine), f'asgiref.sync.AsyncToSync {MOD}converted_coroutine',
                              (None, 'converted_coroutine'), line_of(converted_coroutine), True),
}


@pytest.mark.parametrize('tag', list(CASES))
def test_codeinfo_table(tag):
    obj, name, (class_name, function_name), lineno, has_path = CASES[tag]
    info = CodeInfo(obj)
    assert info.name == name
    assert info.class_name == class_name
    assert info.function_name == function_name
    assert info.lineno == lineno
    assert info.is_class is False
    if has_path:
        assert info.path == THIS_FILE
        assert info.module_name == __name__
    else:
        assert info.path is None
        assert info.module_name == 'builtins'


def test_codeinfo_class():
    info = CodeInfo(Outer)
    assert info.name == f'{MOD}Outer'
    assert info.is_class is True
    assert info.class_name == 'Outer'
    assert info.function_name is None
    assert info.function_qualname is None
    assert info.path == THIS_FILE
    assert info.lineno == THIS_FILE.read_text(encoding='utf-8').splitlines().index('class Outer:') + 1


def test_codeinfo_json_keys():
    assert set(CodeInfo(plain_function).json) == {'name', 'module_name', 'class_name', 'function_name',
                                                  'function_qualname', 'path', 'lineno', 'is_class'}


def test_codeinfo_asyncio_task():
    async def main():
        task = asyncio.ensure_future(async_function())
        info = CodeInfo(task)
        await task
        return info.name

    # inspect.getmodule() can't resolve a coroutine object, so the module falls back to `<file.py:line>`
    assert asyncio.run(main()) == f'asyncio.Task <<{THIS_FILE.name}:{line_of(async_function)}>>.async_function'


# ----------------------------------------------------------------------------------------------------------------------
# known bugs (the v0 bug list, "Bugs (confirmed by running them)" -> "Update CodeInfo (introspect.py)")
# ----------------------------------------------------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason='v0 bug list "Update CodeInfo": callable instances are not resolved '
                                       '(no fallback to type(obj).__call__)')
def test_callable_instance_resolves_to_its_dunder_call():
    info = CodeInfo(Outer())
    assert 'Outer.__call__' in info.name
    assert info.path == THIS_FILE
    assert info.lineno == line_of(Outer.__call__)


def _renaming(f):
    """sets __wrapped__ without functools.wraps, so the result is a *different* function"""

    def other():
        pass

    other.__wrapped__ = f
    return other


@_renaming
def renamed():
    pass


def test_wrapped_without_wraps_is_named_after_the_wrapper():
    info = CodeInfo(renamed)
    assert info.name == f'{MOD}_renaming.<locals>.other'


@pytest.mark.xfail(strict=True, reason='v0 bug list "Update CodeInfo": name and line can come from different functions '
                                       '(inspect.getsourcelines unwraps __wrapped__, the name does not)')
def test_wrapped_without_wraps_line_comes_from_the_same_function_as_the_name():
    info = CodeInfo(renamed)
    assert info.lineno == renamed.__code__.co_firstlineno  # `other`, inside _renaming
    assert info.path == Path(renamed.__code__.co_filename)


# ----------------------------------------------------------------------------------------------------------------------
# v0 bug list "Memory leak in class instrumentation": "CodeInfo ... is an unbounded lru_cache with the same effect"
# ----------------------------------------------------------------------------------------------------------------------

def _make_function():
    def short_lived():
        pass

    return short_lived


@pytest.mark.xfail(strict=True, reason='v0 bug list "Memory leak in class instrumentation": CodeInfo is an unbounded '
                                       'lru_cache (introspect.py:138) that keeps every introspected object alive')
def test_codeinfo_does_not_keep_the_object_alive():
    func = _make_function()
    assert CodeInfo(func).name.endswith('short_lived')
    ref = weakref.ref(func)
    del func
    gc.collect()
    assert ref() is None
