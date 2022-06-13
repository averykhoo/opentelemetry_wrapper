import asyncio
import inspect
import json
from dataclasses import dataclass
from dataclasses import field
from functools import cached_property
from functools import lru_cache
from functools import partial
from functools import partialmethod
from functools import singledispatchmethod
from pathlib import Path
from types import ModuleType
from typing import Callable
from typing import Coroutine
from typing import List
from typing import Optional
from typing import Union


class NotAFunctionError(TypeError):
    pass


@lru_cache(maxsize=None)
@dataclass(unsafe_hash=True, frozen=True)
class CodeInfo:
    code_object: Union[Coroutine, Callable,
                       partial, partialmethod, singledispatchmethod, cached_property,
                       asyncio.Task,
                       type, property]

    unwrap_partial: bool = True
    unwrap_async: bool = True

    __cached_module: List[str] = field(default_factory=list, init=False, repr=False, hash=False, compare=False)
    __cached_cls: List[type] = field(default_factory=list, init=False, repr=False, hash=False, compare=False)
    __cached_function: List[str] = field(default_factory=list, init=False, repr=False, hash=False, compare=False)
    __cached_path: List[Path] = field(default_factory=list, init=False, repr=False, hash=False, compare=False)
    __cached_lineno: List[int] = field(default_factory=list, init=False, repr=False, hash=False, compare=False)

    def __post_init__(self):
        # sanity checks
        assert self.__is_supported_type(self.code_object), type(self.code_object)
        assert isinstance(self.unwrap_partial, bool), self.unwrap_partial
        assert isinstance(self.unwrap_async, bool), self.unwrap_async

        # parse the data
        self._try_to_get_info()

    @property
    def json(self):
        return {
            'name':          self.name,
            'module_name':   self.module_name,
            'class_name':    self.class_name,
            'function_name': self.function_name,
            'path':          str(self.path),
            'lineno':        self.lineno,
        }

    @property
    def name(self) -> str:
        _prefixes = ' '.join(self.__unwrapped_prefixes) + ' ' if self.__unwrapped_prefixes else ''
        _module_name = f'<{self.module_name}>.' if self.module_name else ''
        _class_name = f'{self.class_name}.' if self.class_name else ''
        _function_name = self.function_name or ''

        return f'{_prefixes}{_module_name}{_class_name}{_function_name}'

    @property
    def function_name(self) -> Optional[str]:
        if self.__cached_function:
            return self.__cached_function[0]

    @property
    def module_name(self) -> Optional[str]:
        if self.__cached_module:
            return self.__cached_module[0]

        # fallback to reading from file path
        if self.__cached_path:
            _module_name = inspect.getmodulename(str(self.__cached_path))
            if _module_name is not None:
                return f'"{_module_name}.py"'

    @property
    def cls(self) -> Optional[type]:
        if self.__cached_cls:
            return self.__cached_cls[0]

    @property
    def class_name(self) -> Optional[str]:
        if self.cls:
            return self.cls.__name__

    @property
    def path(self) -> Optional[Path]:
        if self.__cached_path:
            return self.__cached_path[0]

    @property
    def lineno(self) -> Optional[int]:
        if self.__cached_lineno:
            return self.__cached_lineno[0]

    @staticmethod
    def __is_supported_type(code_object):
        if callable(code_object):
            return True
        if isinstance(code_object, (Callable, Coroutine, cached_property)):
            return True
        if isinstance(code_object, asyncio.Task):
            return True

        return False

    @cached_property
    def __unwrapped(self):
        _code_object = self.code_object
        _prefixes = []

        # unwrap recursively
        while True:

            # handle wrappers from functools
            if self.unwrap_partial:

                # class-based wrappers
                if isinstance(_code_object, partial):
                    _prefixes.append('partial')
                    _code_object = _code_object.func
                    continue
                if isinstance(_code_object, partialmethod):
                    _prefixes.append('partialmethod')
                    _code_object = _code_object.func
                    continue
                if isinstance(_code_object, singledispatchmethod):
                    _prefixes.append('singledispatchmethod')
                    _code_object = _code_object.func
                    continue
                if isinstance(_code_object, cached_property):
                    _prefixes.append('cached_property')
                    _code_object = _code_object.func
                    continue

                # make a best guess about the wrapper
                if hasattr(_code_object, '__wrapped__'):
                    if self.__is_supported_type(_code_object.__wrapped__):
                        if all(hasattr(_code_object, _attr) for _attr in
                               {'register', 'dispatch', 'registry', '_clear_cache'}):
                            _prefixes.append('singledispatch')
                        elif all(hasattr(_code_object, _attr) for _attr in {'cache_info', 'cache_clear'}):
                            _prefixes.append('lru_cache')
                        _code_object = _code_object.__wrapped__
                        continue

            # handle async
            if self.unwrap_async:

                # unwrap tasks
                if isinstance(_code_object, asyncio.Task):
                    _prefixes.append('Task')
                    _code_object = _code_object.get_coro()
                    continue

                # attempt to detect asgiref.sync_to_async and asgiref.async_to_sync
                _module = inspect.getmodule(_code_object)
                if hasattr(_module, '__name__') and _module.__name__ == 'asgiref.sync':

                    # must check this first because it may also have an `awaitable` attribute
                    if hasattr(_code_object, 'func'):
                        if self.__is_supported_type(_code_object.func):
                            _prefixes.append('SynctoAsync')
                            _code_object = _code_object.func
                            continue

                    if hasattr(_code_object, 'awaitable'):
                        if self.__is_supported_type(_code_object.awaitable):
                            _prefixes.append('AsyncToSync')
                            _code_object = _code_object.awaitable
                            continue

            # unable to unwrap any further
            break

        return _prefixes, _code_object

    @property
    def __unwrapped_prefixes(self):
        return self.__unwrapped[0]

    @property
    def __unwrapped_code_object(self):
        """
        it is unsafe to expose this externally!
        the potential side-effects (or lack thereof) of calling an unwrapped function are undefined
        """
        return self.__unwrapped[1]

    def _try_to_get_info(self):
        # get module
        module = inspect.getmodule(self.__unwrapped_code_object)
        if module is not None:
            self.__cached_module.append(module.__name__)

        # if we already have a class
        if inspect.isclass(self.__unwrapped_code_object):
            self.__cached_cls.append(self.__unwrapped_code_object)

        # get class of method
        elif inspect.ismethod(self.__unwrapped_code_object) or \
                (inspect.isbuiltin(self.__unwrapped_code_object) and
                 hasattr(self.__unwrapped_code_object, '__self__')):
            if getattr(self.__unwrapped_code_object.__self__, '__class__', None) is not None:
                for _cls in inspect.getmro(self.__unwrapped_code_object.__self__.__class__):
                    if self.__unwrapped_code_object.__name__ in _cls.__dict__:
                        self.__cached_cls.append(_cls)
                        break
            elif getattr(self.__unwrapped_code_object.__self__, '__slots__', None) is not None:
                for _cls in inspect.getmro(self.__unwrapped_code_object.__self__.__slots__):
                    if self.__unwrapped_code_object.__name__ in _cls.__dict__:
                        self.__cached_cls.append(_cls)
                        break

        # get class of unbound method somewhere in a class
        elif inspect.isfunction(self.__unwrapped_code_object):
            if hasattr(self.__unwrapped_code_object, '__qualname__'):
                _cls_qualname = self.__unwrapped_code_object.__qualname__.split('.<locals>')[0].rsplit('.', 1)[0]
                _cls: Union[ModuleType, type, None] = module
                for _cls_name in _cls_qualname.split('.'):
                    if _cls is None:
                        break
                    _cls = getattr(_cls, _cls_name, None)
                else:
                    if _cls is not None:
                        self.__cached_cls.append(_cls)

        # last-ditch attempt to get a class
        _cls = getattr(self.__unwrapped_code_object, '__objclass__', None)
        if _cls is not None:
            self.__cached_cls.append(_cls)

        # use qualname instead of name if possible, which should already contain a class
        if not inspect.isclass(self.__unwrapped_code_object):
            if hasattr(self.__unwrapped_code_object, '__qualname__'):
                _function_name = self.__unwrapped_code_object.__qualname__
                if self.class_name and _function_name.startswith(self.class_name + '.'):
                    _function_name = _function_name[len(self.class_name)+1:]
                self.__cached_function.append(_function_name)
            if getattr(self.__unwrapped_code_object, '__name__', None):
                self.__cached_function.append(self.__unwrapped_code_object.__name__)

        # get the code stuff
        _code = getattr(self.__unwrapped_code_object, '__code__', None)
        if _code is None:
            _code = getattr(self.__unwrapped_code_object, 'cr_code', None)  # asyncio.Task
        if _code is not None:
            if getattr(_code, 'co_filename', None):
                self.__cached_path.append(Path(_code.co_filename))
            if getattr(_code, 'co_firstlineno', None):
                self.__cached_lineno.append(_code.co_firstlineno)
            if getattr(_code, 'co_name', None):
                self.__cached_lineno.append(_code.co_name)


if __name__ == '__main__':
    class A:
        class B:
            def c(self, a):
                @lru_cache
                def d(x):
                    return x + 1

                return partial(d, x=1)

            e = partialmethod(c, a=2)

        async def f(self):
            pass


    print(json.dumps(CodeInfo(asyncio.ensure_future(A().f()).get_coro()).json, indent=4))
    print(json.dumps(CodeInfo(A).json, indent=4))
    print(json.dumps(CodeInfo(A().f).json, indent=4))
    print(json.dumps(CodeInfo(A().B().c).json, indent=4))
    print(json.dumps(CodeInfo(A().B().c(1)).json, indent=4))
