import asyncio
import importlib.util
import inspect
import sys
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
from typing import Dict
from typing import List
from typing import Optional
from typing import Union


@lru_cache(maxsize=None)
@dataclass(unsafe_hash=True, frozen=True)
class CodeInfo:
    code_object: Union[Coroutine, Callable,
                       partial, partialmethod, singledispatchmethod, cached_property,
                       asyncio.Task,
                       type, property]

    unwrap_partial: bool = True
    unwrap_async: bool = True

    _maybe_unsafe__try_very_hard_to_find_class: bool = True

    __cached_cls: List[type] = field(default_factory=list, init=False, repr=False, hash=False, compare=False)
    __cached_function: List[str] = field(default_factory=list, init=False, repr=False, hash=False, compare=False)

    def __post_init__(self):
        assert self.__is_supported_type(self.code_object), type(self.code_object)
        assert isinstance(self.unwrap_partial, bool), self.unwrap_partial
        assert isinstance(self.unwrap_async, bool), self.unwrap_async

    @cached_property
    def json(self) -> Dict[str, Union[str, int, bool, None]]:
        return {
            'name':              self.name,
            'module_name':       self.module_name,
            'class_name':        self.class_name,
            'function_name':     self.function_name,
            'function_qualname': self.function_qualname,
            'path':              str(self.path) if self.path else None,
            'lineno':            self.lineno,
            'is_class':          self.is_class,
        }

    @cached_property
    def is_class(self) -> bool:
        """
        is the unwrapped base object a class?
        """
        return inspect.isclass(self.__unwrapped_code_object)

    @cached_property
    def name(self) -> str:

        _prefixes = ' '.join(self.__unwrapped_prefixes) + ' ' if self.__unwrapped_prefixes else ''
        _module_name = f'<{self.module_name}>.' if self.module_name else ''

        if self.function_qualname:
            _class_name = ''
            _function_name = self.function_qualname
        elif self.function_name:
            _class_name = f'{self.class_name}.' if self.class_name else ''
            _function_name = self.function_name
        elif self.class_name:
            _class_name = self.class_name
            _function_name = '' if self.is_class else '<unknown function>'
        else:
            _class_name = '<unknown class>' if self.is_class else ''
            _function_name = '' if self.is_class else '<unknown function>'

        return f'{_prefixes}{_module_name}{_class_name}{_function_name}'

    @cached_property
    def __code__(self):
        # get the code stuff
        _code = getattr(self.__unwrapped_code_object, '__code__', None)

        # asyncio.Task stores it here
        if _code is None:
            _code = getattr(self.__unwrapped_code_object, 'cr_code', None)

        # sometimes it's in __func__.__code__
        if _code is None:
            _code = getattr(getattr(self.__unwrapped_code_object, '__func__', None), '__code__', None)

        return _code

    @cached_property
    def function_qualname(self) -> Optional[str]:
        # a class does not have a function name
        if self.is_class:
            return None

        # use qualname instead of name if possible, but strip out the class name
        if hasattr(self.__unwrapped_code_object, '__qualname__'):
            return self.__unwrapped_code_object.__qualname__

    @cached_property
    def function_name(self) -> Optional[str]:
        # a class does not have a function name
        if self.is_class:
            return None

        # use qualname instead of name if possible, but strip out the class name
        if self.function_qualname:
            _function_name = self.function_qualname
            if self.class_name:
                if _function_name.startswith(f'{self.class_name}.'):
                    _function_name = _function_name[len(self.class_name) + 1:]
                elif f'.{self.class_name}.' in _function_name:
                    _function_name = _function_name.split(f'.{self.class_name}.', 1)[1]
            return _function_name

        # fallback to name
        if getattr(self.__unwrapped_code_object, '__name__', None):
            return self.__unwrapped_code_object.__name__

        # use the code name
        if self.__code__ is not None:
            if getattr(self.__code__, 'co_name', None):
                return self.__code__.co_name

    @cached_property
    def module(self) -> Optional[ModuleType]:
        module = inspect.getmodule(self.__unwrapped_code_object)
        if module is not None:
            return module

    @cached_property
    def module_name(self) -> Optional[str]:
        if self.module is not None:
            return self.module.__name__

        # fallback to reading from file path
        if self.path is not None:
            _module_name = inspect.getmodulename(str(self.path))
            if _module_name is not None:
                _lineno = f':{self.lineno}' if self.lineno else ''
                return f'<{_module_name}.py{_lineno}>'

    @cached_property
    # flake8: noqa: C901
    def cls(self) -> Optional[type]:
        # if we already are a class
        if self.is_class:
            return self.__unwrapped_code_object

        # get class of method
        if inspect.ismethod(self.__unwrapped_code_object) or \
                (inspect.isbuiltin(self.__unwrapped_code_object) and
                 hasattr(self.__unwrapped_code_object, '__self__')):
            for _attr_name in ('__class__', '__slots__'):
                _attr = getattr(self.__unwrapped_code_object.__self__, _attr_name, None)
                if _attr is not None and hasattr(_attr, '__mro__'):
                    for _cls in inspect.getmro(_attr):
                        if inspect.isclass(_cls) and self.__unwrapped_code_object.__name__ in _cls.__dict__:
                            return _cls

        # get class qualname
        if hasattr(self.__unwrapped_code_object, '__qualname__'):
            _cls_qualname = self.__unwrapped_code_object.__qualname__.split('.<locals>')[0]
            if '.' in _cls_qualname:
                _cls_qualname = _cls_qualname.rsplit('.', 1)[0]
            else:
                _cls_qualname = ''
        else:
            _cls_qualname = ''

        # get class from class qualname
        if _cls_qualname and self.module:
            _cls: Union[ModuleType, type, None] = self.module

            for _cls_name in _cls_qualname.split('.'):
                if _cls is None:
                    break
                _cls = getattr(_cls, _cls_name, None)
            else:
                if _cls is not None:
                    if inspect.isclass(_cls):
                        return _cls

        # one more place to try
        _cls = getattr(self.__unwrapped_code_object, '__objclass__', None)
        if _cls is not None:
            if inspect.isclass(_cls):
                return _cls

        # try harder: load module from path and search inside it to find the class qualname
        if self._maybe_unsafe__try_very_hard_to_find_class and _cls_qualname and not self.module and self.path:
            _temp_module_name = f'__introspected_file__.{self.path}'
            if _temp_module_name in sys.modules:
                _cls = sys.modules[_temp_module_name]
            else:
                spec = importlib.util.spec_from_file_location(_temp_module_name, self.path)
                _cls = importlib.util.module_from_spec(spec)
                sys.modules[_temp_module_name] = _cls
                spec.loader.exec_module(_cls)

            for _cls_name in _cls_qualname.split('.'):
                if _cls is None:
                    break
                _cls = getattr(_cls, _cls_name, None)
            else:
                if _cls is not None:
                    if inspect.isclass(_cls):
                        return _cls

    @cached_property
    def class_name(self) -> Optional[str]:
        if self.cls:
            return self.cls.__name__

    @cached_property
    def path(self) -> Optional[Path]:
        try:
            _source_file = inspect.getsourcefile(self.__unwrapped_code_object)
            if _source_file:
                return Path(_source_file)
        except TypeError:
            pass

        if self.__code__ is not None:
            if getattr(self.__code__, 'co_filename', None):
                return Path(self.__code__.co_filename)

    @cached_property
    def lineno(self) -> Optional[int]:
        try:
            _source_lines = inspect.getsourcelines(self.__unwrapped_code_object)
            if _source_lines:
                return _source_lines[1]
        except (TypeError, OSError):
            pass

        if self.__code__ is not None:
            if getattr(self.__code__, 'co_firstlineno', None):
                return self.__code__.co_firstlineno

    @staticmethod
    def __is_supported_type(code_object) -> bool:
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
    def __unwrapped_prefixes(self) -> List[str]:
        return self.__unwrapped[0]

    @property
    def __unwrapped_code_object(self):
        """
        it is unsafe to expose this externally!
        the potential side-effects (or lack thereof) of calling an unwrapped function are undefined
        """
        return self.__unwrapped[1]
