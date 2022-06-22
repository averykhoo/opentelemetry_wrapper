"""
stolen from fastapi.encoders, with a minor edit to force it to always return and never error
ENCODERS_BY_TYPE was taken from pydantic.json
all pydantic-specific code commented out
"""
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
from typing import Set
from typing import Tuple
from typing import Type
from typing import Union
from uuid import UUID

from opentelemetry_wrapper.utils.introspect import CodeInfo

SetIntStr = Set[Union[int, str]]
DictIntStrAny = Dict[Union[int, str], Any]

isoformat = lambda o: o.isoformat()

ENCODERS_BY_TYPE: Dict[Type[Any], Callable[[Any], Any]] = {
    bytes:                   lambda o: o.decode(),
    datetime.date:           isoformat,
    datetime.datetime:       isoformat,
    datetime.time:           isoformat,
    datetime.timedelta:      lambda td: td.total_seconds(),
    Decimal:                 lambda o: int(o) if o.as_tuple().exponent >= 0 else float(o),
    Enum:                    lambda o: o.value,
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
    Pattern:                 lambda o: o.pattern,
    set:                     list,
    UUID:                    str,
}


def generate_encoders_by_class_tuples(type_encoder_map: Dict[Any, Callable[[Any], Any]],
                                      ) -> Dict[Callable[[Any], Any], Tuple[Any, ...]]:
    encoders_by_class_tuples: Dict[Callable[[Any], Any], Tuple[Any, ...]] = defaultdict(tuple)
    for type_, encoder in type_encoder_map.items():
        encoders_by_class_tuples[encoder] += (type_,)
    return encoders_by_class_tuples


encoders_by_class_tuples = generate_encoders_by_class_tuples(ENCODERS_BY_TYPE)


def jsonable_encoder(obj: Any,
                     include: Optional[Union[SetIntStr, DictIntStrAny]] = None,
                     exclude: Optional[Union[SetIntStr, DictIntStrAny]] = None,
                     by_alias: bool = True,
                     exclude_unset: bool = False,
                     exclude_defaults: bool = False,
                     exclude_none: bool = False,
                     custom_encoder: Optional[Dict[Any, Callable[[Any], Any]]] = None,
                     sqlalchemy_safe: bool = True,
                     ) -> Any:
    custom_encoder = custom_encoder or {}
    if custom_encoder:
        if type(obj) in custom_encoder:
            return custom_encoder[type(obj)](obj)
        else:
            for encoder_type, encoder_instance in custom_encoder.items():
                if isinstance(obj, encoder_type):
                    return encoder_instance(obj)
    if include is not None and not isinstance(include, (set, dict)):
        include = set(include)
    if exclude is not None and not isinstance(exclude, (set, dict)):
        exclude = set(exclude)
    # if isinstance(obj, BaseModel):
    #     encoder = getattr(obj.__config__, "json_encoders", {})
    #     if custom_encoder:
    #         encoder.update(custom_encoder)
    #     obj_dict = obj.dict(
    #         include=include,  # type: ignore # in Pydantic
    #         exclude=exclude,  # type: ignore # in Pydantic
    #         by_alias=by_alias,
    #         exclude_unset=exclude_unset,
    #         exclude_none=exclude_none,
    #         exclude_defaults=exclude_defaults,
    #     )
    #     if "__root__" in obj_dict:
    #         obj_dict = obj_dict["__root__"]
    #     return jsonable_encoder(
    #         obj_dict,
    #         exclude_none=exclude_none,
    #         exclude_defaults=exclude_defaults,
    #         custom_encoder=encoder,
    #         sqlalchemy_safe=sqlalchemy_safe,
    #     )
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
            if (
                    (
                            not sqlalchemy_safe
                            or (not isinstance(key, str))
                            or (not key.startswith("_sa"))
                    )
                    and (value is not None or not exclude_none)
                    and ((include and key in include) or not exclude or key not in exclude)
            ):
                encoded_key = jsonable_encoder(
                    key,
                    by_alias=by_alias,
                    exclude_unset=exclude_unset,
                    exclude_none=exclude_none,
                    custom_encoder=custom_encoder,
                    sqlalchemy_safe=sqlalchemy_safe,
                )
                encoded_value = jsonable_encoder(
                    value,
                    by_alias=by_alias,
                    exclude_unset=exclude_unset,
                    exclude_none=exclude_none,
                    custom_encoder=custom_encoder,
                    sqlalchemy_safe=sqlalchemy_safe,
                )
                encoded_dict[encoded_key] = encoded_value
        return encoded_dict
    if isinstance(obj, (list, set, frozenset, GeneratorType, tuple)):
        encoded_list = []
        for item in obj:
            encoded_list.append(
                jsonable_encoder(
                    item,
                    include=include,
                    exclude=exclude,
                    by_alias=by_alias,
                    exclude_unset=exclude_unset,
                    exclude_defaults=exclude_defaults,
                    exclude_none=exclude_none,
                    custom_encoder=custom_encoder,
                    sqlalchemy_safe=sqlalchemy_safe,
                )
            )
        return encoded_list

    if type(obj) in ENCODERS_BY_TYPE:
        return ENCODERS_BY_TYPE[type(obj)](obj)
    for encoder, classes_tuple in encoders_by_class_tuples.items():
        if isinstance(obj, classes_tuple):
            return encoder(obj)

    # EDITS START HERE
    if isinstance(obj, (Coroutine, Callable)):
        return CodeInfo(obj).name

    try:
        data = dict(obj)
    except Exception:
        try:
            data = vars(obj)
        except Exception:
            return repr(obj)
    # EDITS END HERE

    return jsonable_encoder(
        data,
        by_alias=by_alias,
        exclude_unset=exclude_unset,
        exclude_defaults=exclude_defaults,
        exclude_none=exclude_none,
        custom_encoder=custom_encoder,
        sqlalchemy_safe=sqlalchemy_safe,
    )
