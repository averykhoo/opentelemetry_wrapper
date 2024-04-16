import asyncio
import importlib.util
import inspect
import sys
from dataclasses import dataclass
from dataclasses import field
from functools import WRAPPER_ASSIGNMENTS
from functools import WRAPPER_UPDATES
from functools import cached_property
from functools import lru_cache
from functools import partial
from functools import partialmethod
from functools import singledispatchmethod
from pathlib import Path
from types import ModuleType
from typing import Any
from typing import Callable
from typing import Coroutine
from typing import Dict
from typing import Generator
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

CodeObjectType = Union[
    Coroutine, Callable,
    partial, partialmethod, singledispatchmethod, cached_property,
    asyncio.Task,
    type, property
]


def _is_function_type(_code_object: CodeObjectType) -> bool:
    if callable(_code_object):
        return True
    if isinstance(_code_object, (Coroutine, Callable)):  # `def` and `async def`
        return True
    if isinstance(_code_object, (partial, partialmethod, singledispatchmethod, cached_property)):  # `functools`
        return True
    if isinstance(_code_object, asyncio.Task):
        return True
    return False


def _unwrap_partial(_code_object: CodeObjectType) -> Tuple[Optional[str], CodeObjectType]:  # NOSONAR (complexity=32)
    # class-based wrappers
    for wrapper_class in (partial, partialmethod, singledispatchmethod, cached_property):
        if isinstance(_code_object, wrapper_class):
            return f'functools.{wrapper_class.__name__}', _code_object.func

    # make best guess about the wrapper
    _wrapped_code = getattr(_code_object, '__wrapped__', None)
    if _is_function_type(_wrapped_code):

        # probably single dispatch
        if all(hasattr(_code_object, _attr) for _attr in {'register', 'dispatch', 'registry', '_clear_cache'}):
            return 'functools.singledispatch', _wrapped_code

        # could be lru_cache or cache (but that's a special_case of lru_cache anyway)
        if all(hasattr(_code_object, _attr) for _attr in {'cache_info', 'cache_clear'}):
            return 'functools.lru_cache', _wrapped_code

        # update_wrapper was probably called, and since it's not internal to functools it's probably via wraps
        if all(getattr(_wrapped_code, _a, None) == getattr(_code_object, _a, None) for _a in WRAPPER_ASSIGNMENTS):
            for _u in WRAPPER_UPDATES:
                # this must be a dict
                if not isinstance(getattr(_code_object, _u, None), dict):
                    break
                # this should be a superset, since the keys probably won't be deleted
                if not set(getattr(_code_object, _u).keys()).issuperset(getattr(_wrapped_code, _u, {}).keys()):
                    break
                # the values should also match, since devs are lazy to update things
                for k, v in getattr(_wrapped_code, _u, {}).items():
                    if getattr(_code_object, _u)[k] != v:
                        break
                else:
                    break
            else:
                return 'functools.wraps', _wrapped_code

    # failed to unwrap
    return None, _code_object


def _unwrap_async(_code_object: CodeObjectType) -> Tuple[Optional[str], CodeObjectType]:
    # unwrap tasks
    if isinstance(_code_object, asyncio.Task):
        return 'asyncio.Task', _code_object.get_coro()

    # attempt to detect asgiref.sync_to_async and asgiref.async_to_sync
    _module = inspect.getmodule(_code_object)
    if getattr(_module, '__name__', None) == 'asgiref.sync':

        # must check this first because it may also have an `awaitable` attribute
        if hasattr(_code_object, 'func'):
            if _is_function_type(_code_object.func):
                return 'asgiref.sync.SynctoAsync', _code_object.func

        if hasattr(_code_object, 'awaitable'):
            if _is_function_type(_code_object.awaitable):
                return 'asgiref.sync.AsyncToSync', _code_object.awaitable

    # failed to unwrap
    return None, _code_object


def unwrap_function(code_object: CodeObjectType,
                    *,
                    unwrap_partial: bool = True,
                    unwrap_async: bool = True,
                    ) -> Generator[Tuple[str, CodeObjectType], Any, None]:
    while True:

        # handle wrappers from functools
        if unwrap_partial:
            _wrapper, code_object = _unwrap_partial(code_object)
            if _wrapper is not None:
                yield _wrapper, code_object
                continue

        # handle async
        if unwrap_async:
            _wrapper, code_object = _unwrap_async(code_object)
            if _wrapper is not None:
                yield _wrapper, code_object
                continue

        # unable to unwrap any further
        return


# noinspection PyBroadException
@lru_cache(maxsize=None)
@dataclass(unsafe_hash=True, frozen=True)
class CodeInfo:
    code_object: CodeObjectType

    unwrap_partial: bool = True
    unwrap_async: bool = True

    _maybe_unsafe__try_very_hard_to_find_class: bool = True

    __cached_cls: List[type] = field(default_factory=list, init=False, repr=False, hash=False, compare=False)
    __cached_function: List[str] = field(default_factory=list, init=False, repr=False, hash=False, compare=False)

    # __cached_varname: List[str] = field(default_factory=list, init=False, repr=False, hash=False, compare=False)

    def __post_init__(self):
        assert self.__is_supported_type(self.code_object), type(self.code_object)
        assert isinstance(self.unwrap_partial, bool), self.unwrap_partial
        assert isinstance(self.unwrap_async, bool), self.unwrap_async
        # try:
        #     self.__cached_varname.append('')
        #     for i in range(4, 9):
        #         self.__cached_varname.append(varname.nameof(self.code_object, frame=i))
        # except Exception:
        #     pass

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
        try:
            return inspect.isclass(self._unwrapped_code_object)
        except Exception:
            return False

    # @cached_property
    # def varname_nameof(self) -> str:
    #     return self.__cached_varname[-1]

    @cached_property
    def name(self) -> str:
        try:
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

            # if _function_name == '<lambda>':
            #     _varname = f'{self.varname_nameof} = ' if self.varname_nameof else ''
            # else:
            #     _varname = ''

            return f'{_prefixes}{_module_name}{_class_name}{_function_name}'
        except Exception:
            return '<unknown class>' if self.is_class else '<unknown function>'

    @cached_property
    def __code__(self):
        # get the code stuff
        _code = getattr(self._unwrapped_code_object, '__code__', None)

        # asyncio.Task stores it here
        if _code is None:
            _code = getattr(self._unwrapped_code_object, 'cr_code', None)

        # sometimes it's in __func__.__code__
        if _code is None:
            _code = getattr(getattr(self._unwrapped_code_object, '__func__', None), '__code__', None)

        return _code

    @cached_property
    def function_qualname(self) -> Optional[str]:
        try:
            # a class does not have a function name
            if self.is_class:
                return None

            # use qualname instead of name if possible, but strip out the class name
            if hasattr(self._unwrapped_code_object, '__qualname__'):
                return self._unwrapped_code_object.__qualname__
        except Exception:
            pass

        return None

    @cached_property
    def function_name(self) -> Optional[str]:
        try:
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
            if getattr(self._unwrapped_code_object, '__name__', None):
                return self._unwrapped_code_object.__name__

            # use the code name
            if self.__code__ is not None:
                if getattr(self.__code__, 'co_name', None):
                    return self.__code__.co_name
        except Exception:
            pass

        return None

    @cached_property
    def module(self) -> Optional[ModuleType]:
        try:
            return inspect.getmodule(self._unwrapped_code_object)
        except Exception:
            return None

    @cached_property
    def module_name(self) -> Optional[str]:
        try:
            if self.module is not None:
                return self.module.__name__

            # fallback to reading from file path
            if self.path is not None:
                _module_name = inspect.getmodulename(str(self.path))
                if _module_name is not None:
                    _lineno = f':{self.lineno}' if self.lineno else ''
                    return f'<{_module_name}.py{_lineno}>'
        except Exception:
            pass

        return None

    @cached_property
    def cls(self) -> Optional[type]:
        try:
            # if we already are a class
            # NOTE: this does not unwrap classes, only functions
            # TODO: unwrap classes too
            if self.is_class:
                return self._unwrapped_code_object

            # get class of method
            if inspect.ismethod(self._unwrapped_code_object) or \
                    (inspect.isbuiltin(self._unwrapped_code_object) and
                     hasattr(self._unwrapped_code_object, '__self__')):
                for _attr_name in ('__class__', '__slots__'):
                    _attr = getattr(self._unwrapped_code_object.__self__, _attr_name, None)
                    if _attr is not None and hasattr(_attr, '__mro__'):
                        for _mro_cls in inspect.getmro(_attr):
                            if inspect.isclass(_mro_cls):
                                if self._unwrapped_code_object.__name__ in _mro_cls.__dict__:
                                    return _mro_cls

            # get class qualname
            if hasattr(self._unwrapped_code_object, '__qualname__'):
                _cls_qualname = self._unwrapped_code_object.__qualname__.split('.<locals>')[0]
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
            _cls = getattr(self._unwrapped_code_object, '__objclass__', None)
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
                    if spec is not None:
                        _cls = importlib.util.module_from_spec(spec)
                        sys.modules[_temp_module_name] = _cls
                        if spec.loader is not None:
                            spec.loader.exec_module(_cls)

                for _cls_name in _cls_qualname.split('.'):
                    if _cls is None:
                        break
                    _cls = getattr(_cls, _cls_name, None)
                else:
                    if _cls is not None:
                        if inspect.isclass(_cls):
                            return _cls
        except Exception:
            pass

        return None

    @cached_property
    def class_name(self) -> Optional[str]:
        try:
            if self.cls:
                return self.cls.__name__
        except Exception:
            pass

        return None

    @cached_property
    def path(self) -> Optional[Path]:
        try:
            try:
                _source_file = inspect.getsourcefile(self._unwrapped_code_object)
                if _source_file:
                    return Path(_source_file)
            except TypeError:
                pass

            if self.__code__ is not None:
                if getattr(self.__code__, 'co_filename', None):
                    return Path(self.__code__.co_filename)
        except Exception:
            pass

        return None

    @cached_property
    def lineno(self) -> Optional[int]:
        try:
            try:
                _source_lines = inspect.getsourcelines(self._unwrapped_code_object)
                if _source_lines:
                    return _source_lines[1]
            except (TypeError, OSError):
                pass

            if self.__code__ is not None:
                if getattr(self.__code__, 'co_firstlineno', None):
                    return self.__code__.co_firstlineno
        except Exception:
            pass

        return None

    @staticmethod
    def __is_supported_type(code_object) -> bool:
        if callable(code_object):
            return True
        if isinstance(code_object, (Callable, Coroutine, cached_property)):  # type: ignore[arg-type]
            return True
        if isinstance(code_object, asyncio.Task):
            return True

        return False

    @cached_property
    def __unwrapped(self):
        _code_object = self.code_object
        _prefixes = []
        for _wrapper, _code_object in unwrap_function(self.code_object,
                                                      unwrap_partial=self.unwrap_partial,
                                                      unwrap_async=self.unwrap_async):
            _prefixes.append(_wrapper)
        return _prefixes, _code_object

    @property
    def __unwrapped_prefixes(self) -> List[str]:
        return self.__unwrapped[0]

    @property
    def _unwrapped_code_object(self):
        """
        it is unsafe to expose this externally!
        the potential side effects (or lack thereof) of calling an unwrapped function are undefined
        """
        return self.__unwrapped[1]
