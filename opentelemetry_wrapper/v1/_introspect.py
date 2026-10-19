"""
introspection (OTW-5, workstream 3): the name, file and line of what a span describes, read from one object

* a decorated target: unwrapped through bound methods, partials, `__wrapped__` chains (with or without
  `functools.wraps`), properties and `cached_property`, so the name, the file and the line always come from the same
  function (v0 took the name from the wrapper and the line from the wrapped). A callable instance is its class's
  `__call__`; a class is itself, with `opentelemetry_wrapper.code.is_class`
* a `with otel:` block: the caller's frame at `__enter__`, cached by (code object, line) (DEC-21); unnamed blocks are
  named after the enclosing function, never a line number (DEC-47)
* stable `code.*` keys (DEC-31), taken from the code object and the module: no source file is read (so a frozen app, a
  deleted file or `exec`'d code works), nothing here raises into the app, and nothing here holds a strong reference
  to a user object (the call-site cache is keyed weakly by code object)
"""
import functools
import inspect
import os
import sys
import threading
import weakref
from types import CodeType
from typing import Any
from typing import Dict
from typing import Optional
from typing import Set
from typing import Tuple

from opentelemetry.semconv.attributes.code_attributes import CODE_FILE_PATH
from opentelemetry.semconv.attributes.code_attributes import CODE_FUNCTION_NAME
from opentelemetry.semconv.attributes.code_attributes import CODE_LINE_NUMBER

from opentelemetry_wrapper.v1._warnings import warn_at_runtime

IS_CLASS = 'opentelemetry_wrapper.code.is_class'  # our own prefix (DEC-31): set when the target is a class

Attributes = Dict[str, Any]
Described = Tuple[str, Attributes]

_MAX_UNWRAP = 100  # a `__wrapped__` loop or an endless chain stops here


def _get(obj: Any, name: str) -> Any:
    """`getattr(obj, name, None)` for objects whose `__getattr__` raises something other than `AttributeError`"""
    try:
        return getattr(obj, name, None)
    except Exception:
        return None


def underlying(target: Any) -> Any:
    """the function whose code a span describes: through bound methods, partials, properties, `cached_property` and
    `__wrapped__` (however it was set); a class stays a class, a callable instance stays an instance"""
    for _ in range(_MAX_UNWRAP):
        if isinstance(target, (staticmethod, classmethod)) or inspect.ismethod(target):
            following = _get(target, '__func__')
        elif isinstance(target, functools.partial):
            following = target.func
        elif isinstance(target, functools.cached_property):
            following = target.func
        elif isinstance(target, property):
            following = next((f for f in (target.fget, target.fset, target.fdel) if f is not None), None)
        elif not isinstance(target, type):
            following = _get(target, '__wrapped__')
        else:
            return target
        if following is None:
            return target
        target = following
    return target


def _absolute(filename: str) -> str:
    """semconv prefers an absolute path; `<string>`, `<frozen ...>` and the like stay as they are"""
    if filename.startswith('<') or os.path.isabs(filename):
        return filename
    try:
        return os.path.abspath(filename)
    except Exception:
        return filename


def _name(module: Any, qualname: str) -> str:
    return f'{module}.{qualname}' if isinstance(module, str) and module else qualname


def _routine(func: Any) -> Optional[Tuple[str, Optional[CodeType]]]:
    """(`module.qualname`, code object or None) of a function, method or builtin; `None` if it is neither"""
    if not inspect.isroutine(func):
        return None
    qualname = _get(func, '__qualname__')
    if not isinstance(qualname, str):
        qualname = _get(func, '__name__')
    if not isinstance(qualname, str):
        return None
    module = _get(func, '__module__')
    if module is None and inspect.isbuiltin(func):
        module = _get(_get(func, '__self__'), '__name__')
    code = _get(func, '__code__')
    return _name(module, qualname), code if isinstance(code, CodeType) else None


def _class(cls: type) -> Tuple[str, Attributes]:
    module, qualname = _get(cls, '__module__'), _get(cls, '__qualname__') or cls.__name__
    name = _name(module, qualname)
    attributes: Attributes = {CODE_FUNCTION_NAME: name, IS_CLASS: True}
    filename = _get(sys.modules.get(module) if isinstance(module, str) else None, '__file__')
    if isinstance(filename, str):
        attributes[CODE_FILE_PATH] = _absolute(filename)
    line = vars(cls).get('__firstlineno__')  # 3.13+; earlier, the class line is only in the source, so none is given
    if isinstance(line, int):
        attributes[CODE_LINE_NUMBER] = line
    return name, attributes


def describe(target: Any) -> Described:
    """the span name `module.qualname` (the shape of DEC-47) and the stable `code.*` attributes of `target`; never
    raises"""
    try:
        return _describe(target)
    except Exception:
        try:
            name = f'{type(target).__module__}.{type(target).__qualname__}'
        except Exception:
            name = 'unknown'
        return name, {CODE_FUNCTION_NAME: name}


def _describe(target: Any) -> Described:
    func = underlying(target)
    if isinstance(func, type):
        return _class(func)
    found = _routine(func)
    if found is None and callable(func):  # a callable instance: its class's `__call__`, never its repr (cardinality)
        found = _routine(underlying(_get(type(func), '__call__')))
        if found is None:
            found = f'{type(func).__module__}.{type(func).__qualname__}.__call__', None
    if found is None:
        found = f'{type(func).__module__}.{type(func).__qualname__}', None
    name, code = found
    attributes: Attributes = {CODE_FUNCTION_NAME: name}
    if code is not None:
        attributes[CODE_FILE_PATH] = _absolute(code.co_filename)
        attributes[CODE_LINE_NUMBER] = code.co_firstlineno
    return name, attributes


# ----------------------------------------------------------------------------------------------------------------------
# call sites: `with otel:` blocks
# ----------------------------------------------------------------------------------------------------------------------

class _Site:
    """what is known of one code object: its blocks by line, and the lines of its unnamed blocks"""
    __slots__ = ('ref', 'described', 'unnamed_lines')

    def __init__(self, ref: 'weakref.ref[CodeType]'):
        self.ref = ref
        self.described: Dict[int, Described] = {}
        self.unnamed_lines: Set[int] = set()


# keyed by `id(code)`, not by the code object: code objects compare equal by value (not by file), and a strong key
# would keep a function's code alive forever. the entry goes with the code object, through the weakref callback
_sites: Dict[int, _Site] = {}
_sites_lock = threading.Lock()


def _site(code: CodeType) -> _Site:
    key = id(code)
    site = _sites.get(key)
    if site is None or site.ref() is not code:
        site = _Site(weakref.ref(code, lambda _, key=key: _sites.pop(key, None)))
        _sites[key] = site
    return site


def _described(frame: Any, site: _Site) -> Described:
    code, line = frame.f_code, frame.f_lineno
    described = site.described.get(line)
    if described is None:
        name = _name(frame.f_globals.get('__name__') or '<unknown>', code.co_qualname)
        described = name, {CODE_FUNCTION_NAME: name, CODE_FILE_PATH: _absolute(code.co_filename),
                           CODE_LINE_NUMBER: line}
        site.described[line] = described
    return described


def call_site(frame: Any) -> Described:
    """a `with otel('name'):` block: the code attributes of the caller's frame (the name is the user's)"""
    with _sites_lock:
        return _described(frame, _site(frame.f_code))


def unnamed_call_site(frame: Any) -> Described:
    """an unnamed `with otel:` block: named after the enclosing function, never a line number (DEC-47); a second
    unnamed block in one function is reported once"""
    code, line = frame.f_code, frame.f_lineno
    with _sites_lock:
        site = _site(code)
        described = _described(frame, site)
        added = line not in site.unnamed_lines
        site.unnamed_lines.add(line)
        second = added and len(site.unnamed_lines) == 2
    if second:
        name = described[0]
        # runtime: stderr once, never `warnings.warn`, which an error filter would raise into the app (DEC-81)
        warn_at_runtime(f'two unnamed `with otel:` blocks in {name} share the span name {name!r}; '
                        f'name them, e.g. `with otel(\'load settings\'):`',
                        key=('unnamed', name, code.co_filename, code.co_firstlineno))
    return described
