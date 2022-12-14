import dataclasses
import datetime
import ipaddress
from collections import defaultdict
from collections import deque
from decimal import Decimal
from enum import Enum
from pathlib import Path
from pathlib import PurePath
from re import Pattern
from types import GeneratorType
from typing import Any
from typing import Callable
from typing import Coroutine
from typing import Dict
from typing import Optional
from typing import Tuple
from typing import Type
from typing import Union
from uuid import UUID

from opentelemetry_wrapper.utils.introspect import CodeInfo

try:
    fastapi_jsonable_encoder: Optional[Callable]
    from fastapi.encoders import jsonable_encoder as fastapi_jsonable_encoder
except ImportError:
    fastapi_jsonable_encoder = None

try:
    PYDANTIC_ENCODERS: Dict[Type, Callable]
    # noinspection PyProtectedMember
    from pydantic.json import ENCODERS_BY_TYPE as PYDANTIC_ENCODERS
except ImportError:
    PYDANTIC_ENCODERS = dict()


def parse_datetime(o: datetime.date) -> str:
    return o.isoformat()


def parse_bytes(o: bytes) -> str:
    return o.decode(encoding='latin-1')


def parse_timedelta(o: datetime.timedelta) -> float:
    return o.total_seconds()


def parse_decimal(o: Decimal) -> Union[int, float]:
    return int(o) if o.as_tuple().exponent >= 0 else float(o)


def parse_enum(o: Enum) -> Any:
    return o.value


def parse_pattern(o: Pattern) -> str:
    return o.pattern


def parse_function(o: Union[Coroutine, Callable]) -> str:
    return CodeInfo(o).name


ENCODERS_BY_TYPE: Dict[Type[Any], Callable[[Any], Any]] = {
    bytes:                   parse_bytes,
    datetime.date:           parse_datetime,
    datetime.datetime:       parse_datetime,
    datetime.time:           parse_datetime,
    datetime.timedelta:      parse_timedelta,
    Decimal:                 parse_decimal,
    Enum:                    parse_enum,
    frozenset:               list,
    deque:                   list,
    GeneratorType:           list,
    ipaddress.IPv4Address:   str,
    ipaddress.IPv4Interface: str,
    ipaddress.IPv4Network:   str,
    ipaddress.IPv6Address:   str,
    ipaddress.IPv6Interface: str,
    ipaddress.IPv6Network:   str,
    Path:                    str,
    Pattern:                 parse_pattern,
    set:                     list,
    UUID:                    str,
    Coroutine:               parse_function,
    Callable:                parse_function,  # type: ignore[dict-item]
}
for _type, _encoder in PYDANTIC_ENCODERS.items():
    ENCODERS_BY_TYPE.setdefault(_type, _encoder)

encoders_by_class_tuples: Dict[Callable[[Any], Any], Tuple[Any, ...]] = defaultdict(tuple)
for data_type, data_encoder in ENCODERS_BY_TYPE.items():
    encoders_by_class_tuples[data_encoder] += (data_type,)


def jsonable_encoder(obj: Any) -> Any:
    # hand off to the fastapi encoder if we have it
    if fastapi_jsonable_encoder is not None:
        return fastapi_jsonable_encoder(obj, custom_encoder=ENCODERS_BY_TYPE)

    # extremely simplified version of the fastapi jsonable_encoder
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, PurePath):
        return str(obj)
    if isinstance(obj, (str, int, float, type(None))):
        return obj
    if isinstance(obj, dict):
        encoded_dict = {}
        for key, value in obj.items():
            if not isinstance(key, str) or not key.startswith('_sa'):  # sqlalchemy handling
                encoded_dict[jsonable_encoder(key)] = jsonable_encoder(value)
        return encoded_dict
    if isinstance(obj, (list, set, frozenset, GeneratorType, tuple)):
        return [jsonable_encoder(elem) for elem in obj]

    # explicit type check, does not include subclasses
    if type(obj) in ENCODERS_BY_TYPE:
        return ENCODERS_BY_TYPE[type(obj)](obj)

    # instance type check, includes subclasses
    for encoder, classes_tuple in encoders_by_class_tuples.items():
        if isinstance(obj, classes_tuple):
            return encoder(obj)

    # noinspection PyBroadException
    try:
        return jsonable_encoder(dict(obj))
    except Exception:
        pass

    # noinspection PyBroadException
    try:
        return jsonable_encoder(vars(obj))
    except Exception:
        pass

    return repr(obj)
