"""
this was written before I discovered the pydantic.validate_call decorator, it's almost the same:
* supports both pydantic v1 and v2 (with minor behavioral differences)
* also caches successful type check results when the input is hashable
* supports `typing.TypedDict`
* automatically typechecks return values if the return type is declared
"""
import asyncio
import dataclasses
import inspect
import typing
from collections import defaultdict
from collections.abc import Hashable
from functools import lru_cache
from functools import partial
from functools import wraps

import typing_extensions
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import ValidationError

try:
    from pydantic import TypeAdapter  # v2


    @lru_cache(maxsize=None)
    def _get_pydantic_type_checker(type_annotation, *, strict=True, allow_caching=True):
        # noinspection PyUnresolvedReferences,PyProtectedMember
        if isinstance(type_annotation, typing._TypedDictMeta):
            type_annotation = typing_extensions.TypedDict(type_annotation.__name__, type_annotation.__annotations__)
            type_adapter = TypeAdapter(type_annotation)
        elif isinstance(type_annotation, typing_extensions._TypedDictMeta):
            type_adapter = TypeAdapter(type_annotation)
        elif issubclass(type_annotation, BaseModel):
            type_adapter = TypeAdapter(type_annotation)
        elif dataclasses.is_dataclass(type_annotation):
            type_adapter = TypeAdapter(type_annotation)
        else:
            type_adapter = TypeAdapter(type_annotation, config=ConfigDict(arbitrary_types_allowed=True))
        cached_type_adapter_validate_python = lru_cache(maxsize=4096)(type_adapter.validate_python)

        @wraps(type_adapter.validate_python)
        def type_checker(value):
            if allow_caching and isinstance(value, Hashable):
                return cached_type_adapter_validate_python(value, strict=strict)
            return type_adapter.validate_python(value, strict=strict)

        type_checker.__type_adapter__ = type_adapter
        return type_checker


except ImportError:
    # WARNING:
    # type checking works slightly differently on pydantic v1!
    # this was hacked together for backwards compat
    from pydantic.config import get_config
    from pydantic.validators import find_validators  # v1


    @lru_cache(maxsize=None)
    def _get_pydantic_type_checker(type_annotation, *, strict=True, allow_caching=True):
        # noinspection PyUnresolvedReferences,PyProtectedMember
        if isinstance(type_annotation, typing._TypedDictMeta):
            type_annotation = typing_extensions.TypedDict(type_annotation.__name__, type_annotation.__annotations__)
        _base_config = get_config(ConfigDict(arbitrary_types_allowed=True))
        for type_validator in find_validators(type_annotation, config=_base_config):
            cached_type_validator = lru_cache(maxsize=4096)(type_validator)

            @wraps(type_validator)
            def type_checker(value):
                if allow_caching and isinstance(value, Hashable):
                    if strict and value != cached_type_validator(value):
                        raise TypeError(f'expected {cached_type_validator(value)!r}, got {value!r}')
                    return type_validator(value)
                if strict and value != type_validator(value):
                    raise TypeError(f'expected {type_validator(value)!r}, got {value!r}')
                return type_validator(value)

            return type_checker


def check_type(value, type_annotation, *, label='', strict=True, allow_caching=True):
    """
    check that a `value` is of type `type_annotation`, optionally coercing it

    warning:
        a known edge case when `allow_caching=True` is that `int` and `float` types will be converted to each other

        see: https://stackoverflow.com/a/32211042


    :param value: to be checked
    :param type_annotation: what the value is supposed to be, e.g. `int` or `str | None`
    :param label: describes the value in the raised `TypeError` (useful when using `check_type(...)` programmatically)
    :param strict: if `False`, will attempt to coerce `value` to `type_annotation`
    :param allow_caching: if `False`, will not cache successful results
    :return: the input `value`, coerced to `type_annotation` if `strict=False`
    """
    try:
        return _get_pydantic_type_checker(type_annotation, strict=strict, allow_caching=allow_caching)(value)
    except ValidationError as e:
        if str(label).strip():
            label = f' for {label!s}'
        raise TypeError(f'Typecheck failed{str(label).rstrip()}! Expected {type_annotation}, got {value!r}') from e


def _get_function_type_checkers(function, *, strict=True, allow_caching=True):
    signature = inspect.signature(function)
    type_checkers = defaultdict(lambda: lambda x: x)
    for i, parameter in enumerate(signature.parameters.values()):
        if parameter.annotation is parameter.empty:
            continue
        if parameter.kind in {parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD}:
            type_checkers[i] = partial(check_type,
                                       type_annotation=parameter.annotation,
                                       label=f'arg `{i}` (parameter name `{parameter.name}`)',
                                       strict=strict,
                                       allow_caching=allow_caching)
        if parameter.kind in {parameter.POSITIONAL_OR_KEYWORD, parameter.KEYWORD_ONLY}:
            type_checkers[parameter.name] = partial(check_type,
                                                    type_annotation=parameter.annotation,
                                                    label=f'kwarg `{parameter.name}`',
                                                    strict=strict,
                                                    allow_caching=allow_caching)
    if signature.return_annotation is not signature.empty:
        type_checkers[None] = partial(check_type,
                                      type_annotation=signature.return_annotation,
                                      label='return value',
                                      strict=strict,
                                      allow_caching=allow_caching)
    return type_checkers


def typecheck(func, *, strict=True, allow_caching=True):
    """
    a decorator to validate the input and output arguments of a function

    :param func: the function
    :param strict: if `False`, checks leniently but does not coerce argument or return values
    :param allow_caching: cache successful type checks
    :return: the wrapped function

    TODO: should the values be coerced when `strict=False` hmmm
    """
    # create type checkers for all function params and the return value
    type_checkers = _get_function_type_checkers(func, strict=strict, allow_caching=allow_caching)
    if not type_checkers:
        return func

    # coroutines require an async wrapper
    if asyncio.iscoroutinefunction(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for i, elem in enumerate(args):
                type_checkers[i](elem)
            for k, v in kwargs.items():
                type_checkers[k](v)
            ret = await func(*args, **kwargs)
            type_checkers[None](ret)
            return ret

    # normal functions get a normal decorator
    else:
        @wraps(func)
        def wrapper(*args, **kwargs):
            for i, elem in enumerate(args):
                type_checkers[i](elem)
            for k, v in kwargs.items():
                type_checkers[k](v)
            ret = func(*args, **kwargs)
            type_checkers[None](ret)
            return ret

    # add a way to poke at the type checkers because why not
    wrapper.__type_checkers__ = type_checkers
    return wrapper


if __name__ == '__main__':
    import datetime

    print(repr(check_type('asdf', str)))
    print(repr(check_type('123', str)))
    # print(repr(check_type('123', int)))  # this fails
    # print(repr(check_type('123', float))) # this fails
    print(repr(check_type('123', int, strict=False)))
    print(repr(check_type('123', float, strict=False)))
    # print(repr(check_type(100.0, int))) # this fails
    print(repr(check_type(100, int)))
    print(repr(check_type(100.0, int)))  # this is cached, but maybe shouldn't be
    print(repr(check_type(100, int, allow_caching=False)))
    # print(repr(check_type(100.0, int, allow_caching=False))) # this fails
    # print(repr(check_type(100, 'float')))  # this is coerced, but maybe shouldn't be
    # print(repr(check_type(100.0, 'float')))
    # print(repr(check_type('2024-01-01', datetime.date)))  # this fails
    print(repr(check_type('2024-01-01', datetime.date, strict=False)))


    def square(x: int):
        return x ** 2


    print(repr(square(2.0)))
    print(repr(square(2)))
    print(repr(square(2.5)))
    # print(repr(typecheck(square)(2.0)))  # this fails
    print(repr(typecheck(square)(2)))
    print(repr(typecheck(square)(2.0)))
    # print(repr(typecheck(square)(2.5)))  # this fails

    print(hasattr(typecheck(square), '__type_checkers__'))


    class TestTypedDict1(typing.TypedDict):
        x: int
        y: int


    @typecheck
    def test_typed_dict1(td: TestTypedDict1) -> int:
        return td['x']


    # test_typed_dict1({'x': 1, 'y': 2, 'z': 3}) # fails in v1, passes in v2
    test_typed_dict1({'x': 1, 'y': 2})


    class TestTypedDict2(typing_extensions.TypedDict):
        x: int
        y: int


    @typecheck
    def test_typed_dict2(td: TestTypedDict2) -> int:
        return td['x']


    # test_typed_dict2({'x': 1, 'y': 2, 'z': 3}) # fails in v1, passes in v2
    test_typed_dict2({'x': 1, 'y': 2})


    class TestModel(BaseModel):
        x: int
        y: int


    @typecheck
    def test_typed_dict2(tm: TestModel) -> int:
        return tm.x


    # test_typed_dict2({'x': 1, 'y': 2, 'z': 3}) # fails in v1, passes in v2
    test_typed_dict2(TestModel(x=1, y=2))
