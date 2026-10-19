"""
`@otel` on classes (OTW-6, DEC-53): the functions in the class's `__dict__` are wrapped once, at decoration time

* never `__getattribute__` (v0 lessons): v0 patched it, keyed its cache on `object.__getattribute__` (so only the first
  class got method spans), wrapped already-instrumented methods again on every access (two spans), cached bound methods
  forever (a leak) and read the source on every property access. Here nothing runs per access, nothing holds an
  instance, and the line comes from the code object
* plain methods, `staticmethod`, `classmethod`, nested classes, and the dunders `__new__`, `__init__`,
  `__post_init__` and `__call__`; never `__repr__`, `__eq__`, `__hash__` and the rest (noisy, and they can recurse).
  Properties and `cached_property` only with `properties=True`. `@otel.ignore` leaves a method out
* inherited methods: the base's function is wrapped into the subclass's `__dict__`, so the base itself is unchanged;
  a method that is already ours (decorated in the body, or from an instrumented base) is left as it is. The copy sits
  in an `_Inherited` descriptor, so a later subclass whose MRO puts another override between this class and the
  member's owner (a diamond, a cooperative mixin) still finds that override, as it would without us: lookup walks the
  MRO past this class on each access (a few dict lookups, no source read, nothing cached). An inherited `__new__` is
  not copied when an `__init__` comes earlier in the MRO, so `inspect.signature(cls)` still reports the `__init__`
* class-based context managers (DEC-22): one span from `__enter__` to `__exit__` (and `__aenter__` / `__aexit__`)
  instead of two method spans, current in between. The pair is wrapped only when both sides are, or already are,
  ours; otherwise (one side from a C base, `@otel.ignore`d, a plain `@otel` method span, the wrong kind) both are left
  alone. An `__enter__` opens no span when the `__exit__` that `type(self)` resolves is not ours (an undecorated
  subclass overriding it), since nothing would close it. Each instance keeps a stack of open spans, keyed by `id` with
  a weak reference (so re-entrant objects work and nothing keeps an instance alive); `__exit__` closes the span that is
  current, or the newest one if it runs in another context, where OTel's `detach` logs instead of raising
* the class is changed in place, for the whole process; a class that can't be changed (a built-in or extension type) is
  returned unchanged with one warning
"""
import copy
import functools
import inspect
import threading
import weakref
from contextvars import ContextVar
from typing import Any
from typing import Dict
from typing import FrozenSet
from typing import List
from typing import Optional
from typing import Tuple

from opentelemetry import trace

from opentelemetry_wrapper.v1 import _decorator
from opentelemetry_wrapper.v1 import _env
from opentelemetry_wrapper.v1 import _introspect
from opentelemetry_wrapper.v1 import _spans

CLASS_MARK = '__opentelemetry_wrapper_class__'  # in the `__dict__` of every class we instrumented (never inherited)
IGNORE = '__opentelemetry_wrapper_ignore__'  # set by `@otel.ignore` on the function a class leaves alone
CM_MARK = '__opentelemetry_wrapper_context_manager__'  # 'sync' / 'async' on each `__enter__` / `__exit__` side we make
DUNDERS = frozenset({'__new__', '__init__', '__post_init__', '__call__'})
CONTEXT_MANAGERS = (('__enter__', '__exit__', False), ('__aenter__', '__aexit__', True))
_CONTEXT_MANAGER_NAMES = frozenset(name for pair in CONTEXT_MANAGERS for name in pair[:2])


def _is_dunder(name: str) -> bool:
    return len(name) > 4 and name.startswith('__') and name.endswith('__')


# ----------------------------------------------------------------------------------------------------------------------
# `@otel.ignore`
# ----------------------------------------------------------------------------------------------------------------------

def _parts(target: Any) -> List[Any]:
    """the functions a class member stands for: itself, and what a static / class method, property or
    `cached_property` holds"""
    parts = [target]
    for attribute in ('__func__', 'fget', 'fset', 'fdel', 'func'):
        part = _introspect._get(target, attribute)
        if part is not None:
            parts.append(part)
    return parts


def ignore(target: Any, notes: List[str]) -> Any:
    """mark `target` (a function, or a static / class method or property over one) so class instrumentation leaves it
    out; returns it unchanged"""
    marked = False
    for part in _parts(target):
        try:
            setattr(part, IGNORE, True)
            marked = True
        except Exception:  # a property or a builtin takes no attributes: its function carries the mark
            pass
    if not marked:
        notes.append(f'@otel.ignore cannot mark {_decorator._short(target)}; returned unchanged')
    return target


def _ignored(member: Any) -> bool:
    return any(_introspect._get(part, IGNORE) is True for part in _parts(member))


# ----------------------------------------------------------------------------------------------------------------------
# classes
# ----------------------------------------------------------------------------------------------------------------------

def instrument_class(cls: type, name: Optional[str], attributes: Optional[dict], properties: bool,
                     notes: List[str]) -> type:
    """wrap the members of `cls` in place (see the module docstring); idempotent per class, never raises"""
    if CLASS_MARK in vars(cls):
        return cls
    try:
        setattr(cls, CLASS_MARK, True)  # first, so a class that can't be changed is caught before anything is
    except Exception:
        notes.append(f'@otel cannot instrument {_decorator._short(cls)}: it is a built-in or extension type, or it '
                     f'refuses new attributes; returned unchanged')
        return cls

    members: Dict[str, Tuple[type, Any]] = {}  # name -> (the class it comes from, its raw value), as lookup finds it
    for klass in cls.__mro__:
        if klass is object:
            continue
        for attribute, value in list(vars(klass).items()):
            members.setdefault(attribute, (klass, value))

    for attribute, (owner, value) in members.items():
        if attribute in _CONTEXT_MANAGER_NAMES:
            continue
        span_name = f'{name}.{attribute}' if name else None
        try:
            if isinstance(value, type):
                if owner is cls and _nested(cls, value, attribute):
                    instrument_class(value, span_name, attributes, properties, notes)
                continue
            if attribute == '__new__' and owner is not cls and _init_first(cls, members):
                continue  # copied, it would hide the `__init__` from `inspect.signature(cls)`
            new = _wrap_member(attribute, value, span_name, attributes, properties, notes)
            if new is not None:
                setattr(cls, attribute, new if owner is cls else _inherited(cls, attribute, value, new))
        except Exception as e:
            notes.append(f'@otel could not instrument {cls.__qualname__}.{attribute}: {type(e).__name__}: {e}')

    for enter_name, exit_name, is_async in CONTEXT_MANAGERS:
        if enter_name not in members or exit_name not in members:
            continue
        sides = ((enter_name, True), (exit_name, False))
        kind = 'async' if is_async else 'sync'
        # both sides or neither: an `__enter__` span with no `__exit__` of ours would never end, and stay current
        if not all(_wrappable_side(members[a][1], is_async) or _context_manager_kind(members[a][1]) == kind
                   for a, _ in sides):
            continue
        for attribute, entering in sides:
            owner, value = members[attribute]
            if not _wrappable_side(value, is_async):
                continue  # already one of ours (from an instrumented base)
            try:
                span_name = f'{name}.{enter_name}' if name else None
                new = _context_manager_side(value, entering, is_async, span_name, attributes, exit_name)
                setattr(cls, attribute, new if owner is cls else _inherited(cls, attribute, value, new))
            except Exception as e:
                notes.append(f'@otel could not instrument {cls.__qualname__}.{attribute}: {type(e).__name__}: {e}')
    return cls


def _init_first(cls: type, members: Dict[str, Tuple[type, Any]]) -> bool:
    """an `__init__` comes before the `__new__` in the MRO: `inspect.signature(cls)` reports that `__init__`"""
    if '__init__' not in members:
        return False
    mro = cls.__mro__
    return mro.index(members['__init__'][0]) < mro.index(members['__new__'][0])


class _Inherited:
    """an inherited member wrapped into the class that inherits it (`cls`). Lookup through a class whose MRO has
    another class's `name` between `cls` and the member's owner (a diamond: `class D(Cls, Other)`) finds that one,
    unwrapped, as it would without us; otherwise the wrapped copy. Likewise when the base's member was replaced"""
    __slots__ = ('cls', 'name', 'value', 'wrapped')

    def __init__(self, cls: type, name: str, value: Any, wrapped: Any) -> None:
        self.cls, self.name, self.value, self.wrapped = cls, name, value, wrapped

    def _target(self, owner: Any) -> Any:
        try:
            mro = owner.__mro__
            i = mro.index(self.cls)
        except Exception:
            return self.wrapped
        for klass in mro[i + 1:]:
            namespace = vars(klass)
            if self.name in namespace:
                found = namespace[self.name]
                return self.wrapped if found is self.value else found
        return self.wrapped

    def __get__(self, instance: Any, owner: Any = None) -> Any:
        if owner is None:
            owner = type(instance)
        target = self._target(owner)
        get = getattr(type(target), '__get__', None)
        return target if get is None else get(target, instance, owner)

    @property
    def __isabstractmethod__(self) -> bool:
        return bool(getattr(self.value, '__isabstractmethod__', False))

    def __repr__(self) -> str:
        return f'<inherited {self.wrapped!r}>'


class _InheritedData(_Inherited):
    """`_Inherited` for a data descriptor (a property), which must stay one: an instance `__dict__` never hides it"""
    __slots__ = ()

    def __set__(self, instance: Any, value: Any) -> None:
        target = self._target(type(instance))
        setter = getattr(type(target), '__set__', None)
        if setter is None:  # what it resolves to is no data descriptor: as Python would, set it on the instance
            instance.__dict__[self.name] = value
        else:
            setter(target, instance, value)

    def __delete__(self, instance: Any) -> None:
        target = self._target(type(instance))
        deleter = getattr(type(target), '__delete__', None)
        if deleter is None:
            del instance.__dict__[self.name]
        else:
            deleter(target, instance)


setattr(_Inherited, _decorator.MARK, True)  # ours: a subclass's instrumentation leaves the copy as it is


def _inherited(cls: type, name: str, value: Any, wrapped: Any) -> _Inherited:
    data = hasattr(type(wrapped), '__set__') or hasattr(type(wrapped), '__delete__')
    return (_InheritedData if data else _Inherited)(cls, name, value, wrapped)


def _nested(cls: type, value: type, attribute: str) -> bool:
    """a class defined in the body of `cls` (not one it merely refers to, like `error = ValueError`)"""
    return (_introspect._get(value, '__qualname__') == f'{cls.__qualname__}.{attribute}'
            and _introspect._get(value, '__module__') == _introspect._get(cls, '__module__'))


def _wrap_member(attribute: str, value: Any, span_name: Optional[str], attributes: Optional[dict], properties: bool,
                 notes: List[str]) -> Optional[Any]:
    """the wrapped member, or None to leave it as it is"""
    if _is_dunder(attribute) and attribute not in DUNDERS:
        return None
    if isinstance(value, (staticmethod, classmethod)):
        wrappable = inspect.isfunction(value.__func__)
    elif isinstance(value, (property, functools.cached_property)):
        wrappable = properties
    else:
        wrappable = inspect.isfunction(value)
    if not wrappable or _ignored(value) or _decorator.is_instrumented(value):
        return None
    if isinstance(value, functools.cached_property):
        if _decorator.is_instrumented(value.func):
            return None
        new = copy.copy(value)  # a copy, so a base's descriptor is never changed; keeps `attrname`
        new.func = _decorator._decorate(value.func, span_name, attributes, notes)
        return new
    new = _decorator._decorate(value, span_name, attributes, notes)
    if isinstance(value, property) and all(a is b for a, b in zip(_parts(value)[1:], _parts(new)[1:])):
        return None  # its functions were all ours already
    return new if new is not value else None


# ----------------------------------------------------------------------------------------------------------------------
# class-based context managers: one span per `__enter__` -> `__exit__`
# ----------------------------------------------------------------------------------------------------------------------

_lock = threading.RLock()  # re-entrant: a weakref callback can run during a collection while we hold it
_stacks: Dict[int, list] = {}  # id(instance) -> [weakref to it or None, [scope or None, ...]]
# the (id(instance), side) pairs whose wrapped `__enter__` / `__exit__` is running in this context: a nested call of
# the same side for the same instance (`super().__enter__()` from an override) is passed straight through
_busy: ContextVar[FrozenSet[Tuple[int, bool]]] = ContextVar('opentelemetry_wrapper_cm_busy', default=frozenset())


def _wrappable_side(value: Any, is_async: bool) -> bool:
    if not inspect.isfunction(value) or _ignored(value) or _decorator.is_instrumented(value):
        return False
    return inspect.iscoroutinefunction(value) if is_async else not inspect.iscoroutinefunction(value)


def _context_manager_kind(value: Any) -> Optional[str]:
    """'sync' / 'async' for an `__enter__` / `__exit__` side we made (or the `_Inherited` copy of one), else None"""
    if isinstance(value, _Inherited):
        value = value.wrapped
    kind = getattr(value, CM_MARK, None) if inspect.isfunction(value) else None
    return kind if kind in ('sync', 'async') else None


def _exit_is_ours(instance: Any, exit_name: str, kind: str) -> bool:
    """the `__exit__` (`__aexit__`) that `with` will call on `instance` is one of ours, so a span opened now ends"""
    try:
        return _context_manager_kind(getattr(type(instance), exit_name, None)) == kind
    except Exception:
        return False


def _forget(key: int, ref: Any) -> None:
    with _lock:
        entry = _stacks.get(key)
        if entry is not None and entry[0] is ref:
            del _stacks[key]


def _push(instance: Any, scope: Any) -> None:
    key = id(instance)
    with _lock:
        entry = _stacks.get(key)
        if entry is None:
            try:
                ref: Any = weakref.ref(instance, functools.partial(_forget, key))
            except TypeError:  # not weakly referenceable (`__slots__`): the entry goes when its stack is empty
                ref = None
            entry = _stacks[key] = [ref, []]
        entry[1].append(scope)


_NEWEST = object()


def _pop(instance: Any, scope: Any = _NEWEST, current: Any = None) -> Any:
    """remove and return `scope` if given (None included: an enter while disabled), else the open scope whose span is
    `current`, else the newest; None when the instance has none open (an `__exit__` without its `__enter__`)"""
    key = id(instance)
    with _lock:
        entry = _stacks.get(key)
        if entry is None:
            return None
        scopes = entry[1]
        wanted = scope if scope is not _NEWEST else next(
            (s for s in reversed(scopes) if s is not None and s[0] is current), scopes[-1])
        for i in range(len(scopes) - 1, -1, -1):
            if scopes[i] is wanted:
                del scopes[i]
                break
        if not scopes:
            del _stacks[key]
        return wanted


def _exception(args: tuple, kwargs: dict) -> Optional[BaseException]:
    exc = args[1] if len(args) > 1 else kwargs.get('exc_value', kwargs.get('exc_val', kwargs.get('value')))
    return exc if isinstance(exc, BaseException) else None


def _context_manager_side(func: Any, entering: bool, is_async: bool, name: Optional[str],
                          attributes: Optional[dict], exit_name: str) -> Any:
    """`__enter__` (entering) starts a span, makes it current and pushes it on the instance's stack; `__exit__` runs
    with it still current, then pops and ends it, recording the exception unless `__exit__` suppressed it. An
    `__enter__` on an instance whose class resolves an `__exit__` (`exit_name`) that is not ours just runs: no span"""
    kind = 'async' if is_async else 'sync'
    if entering:
        described_name, described = _introspect.describe(func)
        span_name, span_attributes = name or described_name, {**described, **(attributes or {})}
    disabled, start, finish = _env.disabled, _spans.start, _spans.finish

    def opening(self: Any) -> Any:
        scope = None
        if not disabled():
            _decorator.ensure_configured()
            scope = start(span_name, span_attributes)  # attached: current until `__exit__`
        _push(self, scope)  # None when disabled, so enters and exits still pair up
        return scope

    def closing(self: Any) -> Any:
        try:
            current = trace.get_current_span()
        except Exception:
            current = None
        return _pop(self, current=current)

    def ended(scope: Any, result: Any, args: tuple, kwargs: dict) -> None:
        finish(scope, None if result else _exception(args, kwargs))  # a true result suppressed the exception

    if is_async:
        async def wrapper(self, *args, **kwargs):  # type: ignore[no-untyped-def,misc]
            __tracebackhide__ = __traceback_hide__ = True  # noqa: F841
            key, busy = (id(self), entering), _busy.get()
            if key in busy or entering and not _exit_is_ours(self, exit_name, kind):
                return await func(self, *args, **kwargs)
            scope = opening(self) if entering else closing(self)
            token = _busy.set(busy | {key})
            try:
                result = await func(self, *args, **kwargs)
            except BaseException as e:
                _busy.reset(token)
                if entering:
                    _pop(self, scope)  # no `__exit__` follows a failed `__enter__`
                finish(scope, e)
                raise
            _busy.reset(token)
            if not entering:
                ended(scope, result, args, kwargs)
            return result
    else:
        def wrapper(self, *args, **kwargs):  # type: ignore[no-untyped-def,misc]
            __tracebackhide__ = __traceback_hide__ = True  # noqa: F841
            key, busy = (id(self), entering), _busy.get()
            if key in busy or entering and not _exit_is_ours(self, exit_name, kind):
                return func(self, *args, **kwargs)
            scope = opening(self) if entering else closing(self)
            token = _busy.set(busy | {key})
            try:
                result = func(self, *args, **kwargs)
            except BaseException as e:
                _busy.reset(token)
                if entering:
                    _pop(self, scope)
                finish(scope, e)
                raise
            _busy.reset(token)
            if not entering:
                ended(scope, result, args, kwargs)
            return result

    functools.update_wrapper(wrapper, func, updated=('__dict__',))
    setattr(wrapper, _decorator.MARK, True)
    setattr(wrapper, CM_MARK, kind)
    return wrapper
