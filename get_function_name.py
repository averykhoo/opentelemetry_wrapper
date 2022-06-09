import asyncio
import inspect
import os
from functools import lru_cache
from functools import partial
from typing import Callable
from typing import Coroutine
from typing import Union


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
        raise TypeError(func)

    # get the module
    module = inspect.getmodule(func)
    _module_name = f'<{module.__name__}>.' if module is not None else ''

    # attempt to fallback to filename if no module is found
    if not _module_name:
        _code = getattr(func, '__code__', getattr(func, 'cr_code', None))
        if getattr(_code, 'co_filename', None):
            if inspect.getmodulename(_code.co_filename):
                _module_name = f'<{os.path.basename(_code.co_filename)}.py>.'

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

    # actual class name
    _class_name = f'{cls.__name__}.' if cls is not None else ''

    # use qualname instead of name if we couldn't find the class
    _function_name = func.__name__ if _class_name else func.__qualname__

    # return full name
    return f'{_module_name}{_class_name}{_function_name}'


if __name__ == '__main__':
    class A:
        async def test(self):
            print(1)


    b = lambda x: x + 1


    def c():
        def d(y):
            return y * y

        return d


    # print(get_function_name(A().test))
    # print(get_function_name(asyncio.ensure_future(A().test())))
    # print(dir(asyncio.ensure_future(A().test()).get_coro().cr_code))
    # print(inspect.getsourcefile(asyncio.ensure_future(A().test()).get_coro().cr_code))
    # print(inspect.getmodulename(asyncio.ensure_future(A().test()).get_coro().cr_code.co_filename))
    # print(asyncio.ensure_future(A().test()).get_coro().cr_code.co_firstlineno)
    # print(get_function_name(asyncio.ensure_future(A().test()).get_coro()))
    # print(get_function_name(b))
    # print(get_function_name(c))
    # print(dir(b))
    # print(dir(b.__code__))
    # print(b.__code__.co_firstlineno)

    # print(inspect.getsourcelines(d))
    for f in [A, A().test, asyncio.ensure_future(A().test()), asyncio.ensure_future(A().test()).get_coro(), b, c, c(),
              iter]:
        print(get_function_name(f))
        # print(f.__code__)
