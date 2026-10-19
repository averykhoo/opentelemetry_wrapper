"""
logging (OTW-11, workstream 8): two handlers on the root logger, nothing else (DEC-32, DEC-34, DEC-43)

* OTLP: the `LoggingHandler` of `opentelemetry-instrumentation-logging` (the SDK's is deprecated in 1.44) on our
  `LoggerProvider`, with the stable `code.*` keys; only the handler, never `LoggingInstrumentor`'s record factory. a
  record logged inside a span carries that span's ids (the SDK reads the current context), outside spans zero ids;
  `extra={...}` becomes attributes. `uvicorn.access` records duplicate the request spans, so they are not exported
  (they still reach stderr)
* stderr: one-line JSON (`OTEL_WRAPPER_LOG_FORMAT=json|off`) for log pipelines that are not OTLP. the ids come from a
  `logging.Filter` on this handler that reads the current span and hands the handler a copy of the record, so no
  global log record factory is needed and the OTLP handler never sees our keys as extras. every record's own fields
  are kept (v0's shape), plus `otelTraceID` / `otelSpanID` (`0x`-prefixed lowercase hex, zeros outside spans),
  `otelTraceSampled`, `otelServiceName`, and the local ISO `asctime` with `tz_name` and `tz_utc_offset_seconds`,
  computed per record (so a DST change and a negative offset are right; v0 used `timedelta.seconds`)

the JSON encoder takes anything (v0's "JSON-encode anything": NaN and infinities, complex, `Decimal`, modules,
functions, classes, instances, surplus arguments), never raises and never imports pydantic: a pydantic 2 model is
dumped with `model_dump(mode='json')` only when the app imported pydantic already (DEC-35), its URLs as text, and a
pydantic secret is always `**********`. the line goes through the scrubber (workstream 5b) before it is truncated
(long strings, as v0) and written; the format arguments (`args`) are redacted wherever the message was, since a bare
argument has none of the scrubber's context. neither handler ever raises into the app: a failure is one stderr JSON
line per site (DEC-75)
"""
import copy
import dataclasses
import datetime
import ipaddress
import json
import logging
import sys
import types
import uuid
from collections import deque
from collections.abc import Mapping
from decimal import Decimal
from enum import Enum
from pathlib import PurePath
from re import Pattern
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional

from opentelemetry import trace
from opentelemetry.instrumentation.logging.handler import LoggingHandler

from opentelemetry_wrapper.v1._warnings import report

MAX_STRING_LENGTH = 10000  # v0's: longer string values (not keys) are cut to this length, marker included
TRUNCATED_MARKER = '... (TRUNCATED)'
MAX_DEPTH = 20  # nesting deeper than this is written as `repr`
NOT_EXPORTED_LOGGERS = ('uvicorn.access',)  # and their children: they duplicate the request spans
HANDLER_MARK = '_opentelemetry_wrapper'  # the attribute on our handlers: 'otlp' or 'json'
TRACE_KEYS = ('otelTraceID', 'otelSpanID', 'otelTraceSampled', 'otelServiceName')


# ----------------------------------------------------------------------------------------------------------------------
# JSON-encode anything
# ----------------------------------------------------------------------------------------------------------------------

def _safe_repr(obj: Any) -> str:
    try:
        return repr(obj)
    except Exception:
        try:
            return f'<{type(obj).__module__}.{type(obj).__qualname__} object (repr failed)>'
        except Exception:
            return '<object (repr failed)>'


def _decimal(value: Decimal) -> Any:
    exponent = value.as_tuple().exponent  # an int, or 'n' / 'N' / 'F' (NaN, sNaN, infinity)
    if isinstance(exponent, int) and exponent >= 0:
        return int(value)
    return float(value)  # precision is lost here, but not in `message` (v0)


def _pydantic_model_class() -> Optional[type]:
    """pydantic 2's `BaseModel`, if the app imported it; never imports pydantic (DEC-35); pydantic 1 is absent"""
    main = sys.modules.get('pydantic.main')
    if main is None or pydantic_major_version() != 2:
        return None
    model = getattr(main, 'BaseModel', None)
    return model if isinstance(model, type) else None


SECRET_MASK = '**********'  # pydantic's own mask for a secret's value


def _pydantic_secret_classes() -> tuple:
    """pydantic's secret types (2's `Secret` / `SecretStr` / `SecretBytes`, and `pydantic.v1`'s), if the app imported
    them; never imports pydantic. whatever the version, a secret is never written as its attributes"""
    classes = []
    for module_name, names in (('pydantic.types', ('_SecretBase', 'SecretStr', 'SecretBytes')),
                               ('pydantic.v1.types', ('SecretStr', 'SecretBytes'))):
        module = sys.modules.get(module_name)
        for name in names:
            cls = getattr(module, name, None) if module is not None else None
            if isinstance(cls, type):
                classes.append(cls)
    return tuple(classes)


def _pydantic_value_classes() -> tuple:
    """pydantic 2's value types that are not models (URLs, `NameEmail`), if the app imported them (DEC-35)"""
    if pydantic_major_version() != 2:
        return ()
    classes = []
    for module_name, names in (('pydantic.networks', ('_BaseUrl', '_BaseMultiHostUrl', 'NameEmail')),
                               ('pydantic_core', ('Url', 'MultiHostUrl'))):
        module = sys.modules.get(module_name)
        for name in names:
            cls = getattr(module, name, None) if module is not None else None
            if isinstance(cls, type):
                classes.append(cls)
    return tuple(classes)


def _pydantic_value(obj: Any) -> Any:
    """a pydantic 2 value type as pydantic writes it to JSON (`to_jsonable_python`), else as text"""
    to_jsonable = getattr(sys.modules.get('pydantic_core'), 'to_jsonable_python', None)
    if to_jsonable is not None:
        try:
            return to_jsonable(obj)
        except Exception:
            pass
    return str(obj)


def pydantic_major_version() -> Optional[int]:
    """the major version of the pydantic the app imported, or None (not imported, or no version found)"""
    version = getattr(sys.modules.get('pydantic.version'), 'VERSION', None)
    if version is None:
        version = getattr(sys.modules.get('pydantic'), 'VERSION', None) if 'pydantic' in sys.modules else None
    try:
        return int(str(version).split('.')[0])
    except (TypeError, ValueError):
        return None


def _name(obj: Any) -> str:
    from opentelemetry_wrapper.v1._introspect import describe
    return describe(obj)[0]  # `module.qualname`, the shape of span names (DEC-47); never raises


_SIMPLE: Dict[type, Callable[[Any], Any]] = {
    complex: str,
    Decimal: _decimal,
    bytes: lambda o: o.decode('latin-1'),
    bytearray: lambda o: bytes(o).decode('latin-1'),
    datetime.datetime: lambda o: o.isoformat(),
    datetime.date: lambda o: o.isoformat(),
    datetime.time: lambda o: o.isoformat(),
    datetime.timedelta: lambda o: o.total_seconds(),
    uuid.UUID: str,
    ipaddress.IPv4Address: str, ipaddress.IPv4Interface: str, ipaddress.IPv4Network: str,
    ipaddress.IPv6Address: str, ipaddress.IPv6Interface: str, ipaddress.IPv6Network: str,
}


def _key(key: Any) -> str:
    """a dict key as JSON writes it (`1` -> "1", `None` -> "null"); anything else, encoded, then as text"""
    encoded = key if isinstance(key, str) else encode(key)
    if isinstance(encoded, str):
        return encoded
    if encoded is None or isinstance(encoded, (bool, int, float)):
        return json.dumps(encoded)
    return _safe_repr(key)


def encode(obj: Any, _depth: int = 0, _path: Optional[set] = None) -> Any:
    """anything to a JSON-able value (str, int, float, bool, None, list, dict with str keys); never raises"""
    try:
        return _encode(obj, _depth, _path if _path is not None else set())
    except Exception:
        return _safe_repr(obj)


def _encode(obj: Any, depth: int, path: set) -> Any:
    if obj is None or isinstance(obj, (str, bool)):
        return obj
    if isinstance(obj, Enum):
        return encode(obj.value, depth + 1, path)
    if isinstance(obj, (int, float)):
        return obj  # NaN and the infinities as JSON's NaN / Infinity (v0)
    for kind in type(obj).__mro__:
        simple = _SIMPLE.get(kind)
        if simple is not None:
            return simple(obj)
    if isinstance(obj, PurePath):
        return str(obj)
    if isinstance(obj, Pattern):
        return obj.pattern
    if isinstance(obj, types.ModuleType):
        return obj.__name__
    if isinstance(obj, BaseException):
        return _safe_repr(obj)
    if isinstance(obj, type) or callable(obj) and not hasattr(obj, '__dict__') or isinstance(obj, (
            types.FunctionType, types.BuiltinFunctionType, types.MethodType, types.LambdaType)):
        return _name(obj)
    if depth >= MAX_DEPTH or id(obj) in path:
        return _safe_repr(obj)
    path.add(id(obj))
    try:
        return _container(obj, depth, path)
    finally:
        path.discard(id(obj))


def _container(obj: Any, depth: int, path: set) -> Any:
    if isinstance(obj, Mapping):
        return {_key(k): encode(v, depth + 1, path) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset, deque)):
        return [encode(item, depth + 1, path) for item in obj]
    model = _pydantic_model_class()
    if model is not None and isinstance(obj, model):
        try:
            return encode(getattr(obj, 'model_dump')(mode='json'), depth + 1, path)
        except Exception:
            pass  # a model that can't dump itself gets the generic encoder
    secrets = _pydantic_secret_classes()
    if secrets and isinstance(obj, secrets):
        return SECRET_MASK  # never its `_secret_value`, and no call into the secret's own code
    values = _pydantic_value_classes()
    if values and isinstance(obj, values):
        return encode(_pydantic_value(obj), depth + 1, path)
    if dataclasses.is_dataclass(obj):
        return {f.name: encode(getattr(obj, f.name, None), depth + 1, path) for f in dataclasses.fields(obj)}
    if callable(obj):  # a callable instance: named like a span, never its contents
        return _name(obj)
    fields = getattr(obj, '__dict__', None)
    if isinstance(fields, Mapping):  # an instance: its attributes (SQLAlchemy's `_sa_*` state left out, as v0)
        return {_key(k): encode(v, depth + 1, path) for k, v in fields.items()
                if not (isinstance(k, str) and k.startswith('_sa'))}
    return _safe_repr(obj)  # e.g. a bare object(), a generator (never consumed)


def truncate(value: Any, limit: int = MAX_STRING_LENGTH) -> Any:
    """long string values (nested in dicts and lists too, not dict keys) cut to `limit`, marker included (v0)"""
    if isinstance(value, str):
        return value if len(value) <= limit else f'{value[:limit - len(TRUNCATED_MARKER)]}{TRUNCATED_MARKER}'[:limit]
    if isinstance(value, dict):
        return {k: truncate(v, limit) for k, v in value.items()}
    if isinstance(value, list):
        return [truncate(v, limit) for v in value]
    return value


# ----------------------------------------------------------------------------------------------------------------------
# the stderr JSON handler
# ----------------------------------------------------------------------------------------------------------------------

def message_of(record: logging.LogRecord) -> str:
    """`record.getMessage()`, or (bad format arguments, a failing `__str__`) v0's `MSG=... ARGS=...`"""
    try:
        return record.getMessage()
    except Exception:
        return f'MSG={_safe_repr(record.msg)} ARGS={_safe_repr(record.args)}'


def _scrub(data: Dict[str, Any]) -> Any:
    from opentelemetry_wrapper.v1 import scrubbing
    return scrubbing.scrub_mapping(data)  # never raises: what fails to scrub is replaced (fail closed, DEC-74)


def _scrub_args(args: Any, encoded: Any, message: str, scrubbed_message: Any) -> Any:
    """the format arguments, redacted where the message was: a bare argument has none of the context the scrubber
    keys on (`password=`, `Bearer `), which sits in the format string, so an argument is kept only when the scrubbed
    message is the message itself, or still shows the argument's text. fails closed: what can't be matched up is
    redacted"""
    from opentelemetry_wrapper.v1.scrubbing import REDACTED
    if isinstance(scrubbed_message, str) and scrubbed_message == message:
        return encoded  # nothing in the message was redacted (the arguments are scrubbed on their own already)

    def seen(arg: Any) -> bool:
        try:
            return isinstance(scrubbed_message, str) and str(arg) in scrubbed_message
        except Exception:
            return False

    try:
        if isinstance(args, Mapping) and isinstance(encoded, dict) and len(args) == len(encoded):
            return {k: (v if seen(arg) else REDACTED) for (k, v), arg in zip(encoded.items(), args.values())}
        if isinstance(args, (tuple, list)) and isinstance(encoded, list) and len(args) == len(encoded):
            return [v if seen(arg) else REDACTED for v, arg in zip(encoded, args)]
        if args is None or args == () or args == {}:
            return encoded
    except Exception:
        pass
    return REDACTED


class TraceContextFilter(logging.Filter):
    """the current span's ids on a copy of the record (the other handlers see the record unchanged)"""

    def __init__(self, service_name: str = ''):
        super().__init__()
        self.service_name = service_name

    def filter(self, record: logging.LogRecord) -> Any:
        try:
            context = trace.get_current_span().get_span_context()
            record = copy.copy(record)
            record.otelTraceID = f'0x{context.trace_id:032x}'
            record.otelSpanID = f'0x{context.span_id:016x}'
            record.otelTraceSampled = context.trace_flags.sampled
            record.otelServiceName = self.service_name
        except Exception as e:  # the line is still written, without the ids
            report('logging.trace_context', e)
        return record


class JsonFormatter(logging.Formatter):
    """a record to one line of JSON: never raises, never more than one line"""

    def format(self, record: logging.LogRecord) -> str:
        try:
            return self._format(record)
        except Exception as e:
            report('logging.json_format', e)
            try:
                return json.dumps({'message': _safe_repr(message_of(record))[:MAX_STRING_LENGTH],
                                   'levelname': str(getattr(record, 'levelname', '')),
                                   'opentelemetry_wrapper': 'this log record could not be encoded'})
            except Exception:
                return '{"opentelemetry_wrapper": "this log record could not be encoded"}'

    def _format(self, record: logging.LogRecord) -> str:
        data: Dict[str, Any] = dict(vars(record))
        data['message'] = message_of(record)
        moment = datetime.datetime.fromtimestamp(record.created, datetime.timezone.utc).astimezone()  # this record's
        offset = moment.utcoffset()
        data['asctime'] = moment.isoformat(timespec='microseconds')
        data['tz_name'] = moment.tzname()
        data['tz_utc_offset_seconds'] = int(offset.total_seconds()) if offset is not None else 0
        if record.exc_info and not data.get('exc_text'):
            data['exc_text'] = self.formatException(record.exc_info)
        if record.stack_info:
            data['stack_info'] = self.formatStack(record.stack_info)
        encoded = {_key(k): encode(v) for k, v in data.items()}
        scrubbed = dict(_scrub(encoded))
        if 'args' in scrubbed:
            scrubbed['args'] = _scrub_args(record.args, scrubbed['args'], data['message'], scrubbed.get('message'))
        return json.dumps(truncate(scrubbed), ensure_ascii=False, allow_nan=True)


class JsonHandler(logging.Handler):
    """one JSON line per record on the current `sys.stderr` (so a redirected or captured stderr is followed)"""

    def __init__(self, service_name: str = ''):
        super().__init__()
        self.setFormatter(JsonFormatter())
        self.addFilter(TraceContextFilter(service_name))

    def handle(self, record: logging.LogRecord) -> Any:  # formats outside the handler's lock; only the write is in it
        try:
            kept = self.filter(record)
            if not kept:
                return kept
            if isinstance(kept, logging.LogRecord):
                record = kept
            line = self.format(record) + '\n'
            with self.lock:  # type: ignore[union-attr]
                stream = sys.stderr if sys.stderr is not None else sys.__stderr__
                if stream is not None:
                    stream.write(line)
                    stream.flush()
            return kept
        except Exception as e:
            report('logging.json_write', e)
            return False

    def emit(self, record: logging.LogRecord) -> None:
        self.handle(record)

    def flush(self) -> None:
        try:
            stream = sys.stderr if sys.stderr is not None else sys.__stderr__
            if stream is not None:
                stream.flush()
        except Exception:
            pass


# ----------------------------------------------------------------------------------------------------------------------
# the OTLP handler
# ----------------------------------------------------------------------------------------------------------------------

_RECORD_FIELDS = frozenset(vars(logging.LogRecord('', 0, '', 0, '', (), None))) | {'message', 'asctime'}
_PRIMITIVES = (str, bool, int, float, bytes, type(None))


def _text(value: Any) -> str:
    """`str(value)` as a plain `str`, or its repr when `__str__` fails"""
    try:
        return str.__str__(str(value))
    except Exception:
        return _safe_repr(value)


def _attribute_key(key: Any) -> str:
    """a key the SDK takes (a non-empty `str`): `1` -> "1", `None` -> "null", `''` -> "''" """
    text = key if isinstance(key, str) else _key(key)
    return str.__str__(text) if text else _safe_repr(key)


def _attribute(value: Any, depth: int = 0) -> Any:
    """an extra the SDK takes as an attribute value without a warning (a warning reaches the root logger, so it would
    be a second line, and the SDK would export the value as None): what it would turn into text itself (`str`), turned
    into text here, where a failing `__str__` is caught; keys are non-empty `str`; primitives are their exact base type
    and a sequence's items share one type (the SDK compares `type(item)`), else its items are text"""
    if value is None:
        return None
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, int):
        return int.__int__(value)  # an `IntEnum` member, say, as a plain `int`
    if isinstance(value, float):
        return float.__float__(value)
    if isinstance(value, str):
        return str.__str__(value)
    if isinstance(value, bytes):
        return bytes.__bytes__(value)
    if depth < MAX_DEPTH and isinstance(value, Mapping):
        return {_attribute_key(k): _attribute(v, depth + 1) for k, v in value.items()}
    if depth < MAX_DEPTH and isinstance(value, (list, tuple)):
        items = [_attribute(v, depth + 1) for v in value]
        if len({list if isinstance(v, (list, tuple)) else type(v) for v in items if v is not None}) > 1:
            items = [v if v is None or isinstance(v, str) else _text(original) for v, original in zip(items, value)]
        return items
    return _text(value)


def _with_safe_extras(record: logging.LogRecord) -> logging.LogRecord:
    """the record, or a copy whose extras all have valid keys and attribute values"""
    if all(isinstance(k, str) and k and (k in _RECORD_FIELDS or isinstance(v, _PRIMITIVES))
           for k, v in vars(record).items()):
        return record
    record = copy.copy(record)
    fields = vars(record)
    for bad in [k for k in fields if not (isinstance(k, str) and k)]:  # `extra={1: ...}`: the stdlib keeps the key
        value = fields.pop(bad)
        fields.setdefault(_attribute_key(bad), value)
    for k, v in list(fields.items()):
        if k not in _RECORD_FIELDS and not isinstance(v, _PRIMITIVES):
            try:
                fields[k] = _attribute(v)
            except Exception:
                fields[k] = _safe_repr(v)
    return record


def exported(record: logging.LogRecord) -> bool:
    """not from a logger whose records duplicate spans (`uvicorn.access` and its children)"""
    name = getattr(record, 'name', '') or ''
    return not any(name == n or name.startswith(n + '.') for n in NOT_EXPORTED_LOGGERS)


class OtlpHandler(LoggingHandler):
    """contrib's handler, with the stable `code.*` keys, that never raises into the app (a record whose message
    can't be formatted is exported with v0's `MSG=... ARGS=...` body instead)"""

    def __init__(self, logger_provider: Any = None):
        if logger_provider is None:
            super().__init__(log_code_attributes=True)
        else:
            super().__init__(logger_provider=logger_provider, log_code_attributes=True)
        self.addFilter(exported)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            try:
                record.getMessage()
            except Exception:
                record = copy.copy(record)
                record.msg, record.args = message_of(record), None
            super().emit(_with_safe_extras(record))
        except Exception as e:
            report('logging.otlp_emit', e)

    def handleError(self, record: logging.LogRecord) -> None:  # never the stdlib's traceback on stderr
        pass


# ----------------------------------------------------------------------------------------------------------------------
# instrumenting
# ----------------------------------------------------------------------------------------------------------------------

def _service_name() -> str:
    try:
        resource = getattr(trace.get_tracer_provider(), 'resource', None)
        value = resource.attributes.get('service.name', '') if resource is not None else ''
        return value if isinstance(value, str) else str(value)
    except Exception:
        return ''


def ours(handler: logging.Handler) -> Optional[str]:
    """'otlp' or 'json' for one of our handlers, else None"""
    mark = getattr(handler, HANDLER_MARK, None)
    return mark if mark in ('otlp', 'json') else None


def instrument(logger_provider: Any, log_format: str, notes: List[str]) -> None:
    """our two handlers on the root logger, each at most once; `log_format='off'`: no JSON handler"""
    root = logging.getLogger()
    present = {ours(h) for h in root.handlers}
    if 'otlp' not in present:
        otlp = OtlpHandler(logger_provider)
        setattr(otlp, HANDLER_MARK, 'otlp')
        root.addHandler(otlp)
    if log_format == 'json' and 'json' not in present:
        if pydantic_major_version() == 1:
            notes.append('pydantic 1 is not supported by the JSON logs on stderr: its models are written as their '
                         'attributes. Upgrade to pydantic 2')
        from opentelemetry_wrapper.v1 import _config
        _config.use_auto_scrubbing_engine()  # the same scrubber as the exporters (DEC-83)
        handler = JsonHandler(_service_name())
        setattr(handler, HANDLER_MARK, 'json')
        root.addHandler(handler)
