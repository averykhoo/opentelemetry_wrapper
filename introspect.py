import asyncio
import inspect
from dataclasses import dataclass
from functools import cached_property
from functools import lru_cache
from functools import partial
from functools import partialmethod
from functools import singledispatchmethod
from pathlib import Path
from types import ModuleType
from typing import Callable
from typing import Coroutine
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

    def __post_init__(self):
        assert self.__is_supported_type(self.code_object)
        assert isinstance(self.unwrap_partial, bool)
        assert isinstance(self.unwrap_async, bool)

    @property
    def name(self) -> Optional[str]:
        raise NotImplementedError

    @property
    def module(self) -> Optional[ModuleType]:
        raise NotImplementedError

    @property
    def path(self) -> Optional[Path]:
        raise NotImplementedError

    @property
    def line_number(self) -> Optional[int]:
        raise NotImplementedError

    @staticmethod
    def __is_supported_type(code_object):
        return isinstance(code_object, (Callable, Coroutine))

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
                    _code_object = _code_object.get_coro()
                    continue

                # attempt to detect asgiref.sync_to_async and asgiref.async_to_sync
                _module = inspect.getmodule(_code_object)
                if hasattr(_module, '__name__') and _module.__name__ == 'asgiref.sync':

                    # must check this first because it may also have an `awaitable` attribute
                    if hasattr(_code_object, 'func'):
                        if self.__is_supported_type(_code_object.func):
                            _prefixes.append('sync_to_async')
                            _code_object = _code_object.func
                            continue

                    if hasattr(_code_object, 'awaitable'):
                        if self.__is_supported_type(_code_object.awaitable):
                            _prefixes.append('async_to_sync')
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
