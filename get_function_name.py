import asyncio
import inspect
import json
from functools import lru_cache
from functools import partial
from functools import partialmethod
from typing import Callable
from typing import Coroutine
from typing import Union

from introspect import CodeInfo


class NotAFunctionError(TypeError):
    pass


@lru_cache(maxsize=None)
def get_function_name(func: Union[Coroutine, Callable, partial, asyncio.Task]) -> str:
    """
    Get the name of a function.
    """

    # recursively un-partial if needed
    if isinstance(func, partial):
        return get_function_name(func.func)

    # recursively pull out of asyncio.Task if needed
    if isinstance(func, asyncio.Task):
        return get_function_name(func.get_coro())

    # sanity check
    if not isinstance(func, (Callable, Coroutine)):
        raise NotAFunctionError(func)

    # get the module
    module = inspect.getmodule(func)
    module_name = module.__name__ if module is not None else ''

    # attempt to fallback to filename if no module is found
    if not module_name:
        _code = getattr(func, '__code__', getattr(func, 'cr_code', None))
        if getattr(_code, 'co_filename', None):
            if inspect.getmodulename(_code.co_filename):
                module_name = inspect.getmodulename(_code.co_filename)
                if getattr(_code, 'co_firstlineno', None):
                    module_name = f'{module_name}.py:{_code.co_firstlineno}'

    # extremely special case to handle asgiref.async_to_sync and asgiref.sync_to_async
    if module_name == 'asgiref.sync':
        try:
            return f'SyncToAsync({get_function_name(getattr(func, "func"))})'
        except (AttributeError, NotAFunctionError):
            pass
        try:
            return f'AsyncToSync({get_function_name(getattr(func, "awaitable"))})'
        except (AttributeError, NotAFunctionError):
            pass

    # get class if it's a bound method
    cls = None
    # noinspection PyUnresolvedReferences
    if inspect.ismethod(func) or (inspect.isbuiltin(func) and
                                  hasattr(func, '__self__') and
                                  getattr(func.__self__, '__class__', None) is not None):
        for _cls in inspect.getmro(func.__self__.__class__):
            if func.__name__ in _cls.__dict__:
                cls = _cls
                break

    # unbound method
    elif module is not None and inspect.isfunction(func):
        _cls = getattr(module, func.__qualname__.split('.<locals>')[0].rsplit('.', 1)[0], None)
        if isinstance(_cls, type):
            cls = _cls

    # not a bound method, so there's probably no class, but we can check just in case
    if cls is None:
        cls = getattr(func, '__objclass__', None)

    # format module name
    _module_name = f'<{module_name}>.' if module_name else ''

    # format class name
    _class_name = f'{cls.__name__}.' if cls is not None else ''

    # use qualname instead of name if possible, which should already contain a class
    _function_name = ''
    if hasattr(func, '__qualname__'):
        _function_name = func.__qualname__
        if _function_name.startswith(_class_name):
            _function_name = _function_name[len(_class_name):]
    if hasattr(func, '__name__') and not _function_name:
        _function_name = func.__name__
    if not _function_name:
        _function_name = '<unknown function>'

    # return full name
    return f'{_module_name}{_class_name}{_function_name}'


from aaaa.bbbb import cccc
from aaaa.bbbb import dddd


class A:
    def __init__(self):
        def e():
            return 1

        self.f = e

    async def test(self):
        print(1)


b = lambda x: x + 1


def c():
    def d(y):
        return y * y

    return d


class Aa:
    class B:
        def c(self, a):
            @lru_cache
            def d(x):
                return x + 1

            return partial(d, x=1)

        e = partialmethod(c, a=2)

    async def f(self):
        pass


if __name__ == '__main__':

    for f in [
        A,
        A().test,
        asyncio.ensure_future(A().test()),
        asyncio.ensure_future(A().test()).get_coro(),
        b,
        c,
        c(),
        A().f,
        iter,
        cccc,
        dddd,
        asyncio.ensure_future(dddd()),
        asyncio.ensure_future(Aa().f()),
        asyncio.ensure_future(Aa().f()).get_coro(),
        Aa,
        Aa().f,
        Aa().B().c,
        Aa().B().c(1),
        Aa().B().e,
    ]:
        print(get_function_name(f))
        print(json.dumps(CodeInfo(f).json, indent=4))
        # print(inspect.getsourcelines(f))
