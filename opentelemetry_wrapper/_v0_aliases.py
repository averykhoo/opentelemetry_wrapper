"""
v0's root names, kept from 1.0.0 to 2.0 as thin aliases onto v1 (DEC-96; v0 itself is deleted)

each alias does what its v1 replacement does (README.md § Upgrading from v0) and, the first time any code calls it,
writes one stderr JSON line naming that replacement (DEC-81's once-only channel, never `warnings.warn`, so no warnings
filter turns it into an exception). options v1 no longer takes are accepted and ignored, with one more line naming
what replaced them (DEC-43). an alias never raises (never crash first): a failure inside one is reported once on
stderr and the alias returns what it was given, and the warnings v1 itself issues on the way (a renamed variable, a
missing extra) go to stderr too, inside `runtime()`: v0 never warned, so an app run with `-W error` must not start
crashing at startup because it upgraded (unlike `otel.instrument`, where an error filter may raise, DEC-49).
`instrument_dataclasses()` does nothing (DEC-42)
"""
import functools
import importlib
from typing import Any
from typing import Callable
from typing import Optional
from typing import TypeVar

from opentelemetry_wrapper.v1 import _env
from opentelemetry_wrapper.v1._otel import otel
from opentelemetry_wrapper.v1._warnings import _caller_site
from opentelemetry_wrapper.v1._warnings import report
from opentelemetry_wrapper.v1._warnings import runtime
from opentelemetry_wrapper.v1._warnings import warn_at_runtime

__all__ = ('instrument_all', 'instrument_dataclasses', 'instrument_decorate', 'instrument_fastapi_app',
           'instrument_logging', 'instrument_requests', 'instrument_sqlalchemy', 'instrument_sqlalchemy_engine',
           'instrument_system_metrics')

F = TypeVar('F', bound=Callable[..., Any])
MISSING: Any = object()
REMOVED_AT = 'deprecated since 1.0.0 and removed in 2.0'


def _tell(key: str, message: str) -> None:
    """one stderr line per key per process, naming where it was first used; nothing while the wrapper is disabled"""
    try:
        if _env.disabled():
            return
        path, line = _caller_site()
        warn_at_runtime(f'{message} (first used at {path}:{line})', key=('v0 alias', key), anywhere=True)
    except Exception:  # never raise into the app
        pass


def _alias(advice: str, fallback: Callable[..., Any]) -> Callable[[F], F]:
    """the decorated function is the alias of v0's root name of the same name; `advice` says what to write instead; on
    a failure the alias returns `fallback(*args, **kwargs)` (what it was given, or None)"""

    def decorator(body: F) -> F:
        name = body.__name__

        @functools.wraps(body)
        def alias(*args: Any, **kwargs: Any) -> Any:
            _tell(name, f'opentelemetry_wrapper.{name} is {REMOVED_AT}: {advice}')
            try:
                with runtime():  # v1's own warnings: once-only stderr lines, never an exception (DEC-81)
                    return body(*args, **kwargs)
            except Exception as e:
                report(f'v0 alias {name}', e)
                try:
                    return fallback(*args, **kwargs)
                except Exception:
                    return None

        alias.__module__ = 'opentelemetry_wrapper'
        return alias  # type: ignore[return-value]

    return decorator


def _none(*_args: Any, **_kwargs: Any) -> None:
    return None


def _first(target: Any = None, *_args: Any, **_kwargs: Any) -> Any:
    return target


def _decorate_fallback(func: Any = MISSING, *_args: Any, **_kwargs: Any) -> Any:
    return (lambda f: f) if func is MISSING else func


def _given(**options: Any) -> str:
    return ', '.join(name for name, value in options.items() if value is not MISSING)


def _import(name: str, extra: str, caller: str) -> Any:
    """the library, or None (and one stderr line) when it or its instrumentation is not installed"""
    from opentelemetry_wrapper.v1._instrument import _installed
    try:
        module = importlib.import_module(name)
    except ImportError as e:
        problem = f'{name} cannot be imported ({e})'
    else:
        if _installed(f'opentelemetry.instrumentation.{name}'):
            return module
        problem = f'opentelemetry-instrumentation-{name} is not installed'
    _tell(f'{caller} missing', f'{caller} did nothing: {problem}. Install opentelemetry_wrapper[{extra}]')
    return None


def _missing(instrumentation: str, extra: str, caller: str) -> bool:
    """the integration's instrumentation is not installed (v0 had it as a core dependency): one stderr line"""
    from opentelemetry_wrapper.v1._instrument import _installed
    if _installed(f'opentelemetry.instrumentation.{instrumentation}'):
        return False
    _tell(f'{caller} missing', f'{caller} did nothing: opentelemetry-instrumentation-{instrumentation} is not '
                               f'installed. Install opentelemetry_wrapper[{extra}]')
    return True


def _is_instance(target: Any, module: str, name: str) -> bool:
    from opentelemetry_wrapper.v1._instrument import _isinstance_of
    return _isinstance_of(target, module, name)


@_alias('use @otel (on a class, @otel(properties=True) to keep the property spans v0 made)', _decorate_fallback)
def instrument_decorate(func: Any = MISSING, /, *, func_name: Optional[str] = None) -> Any:
    """v0's decorator: `@instrument_decorate`, `instrument_decorate(f)`, `partial(instrument_decorate, func_name=.)`;
    a class also gets its properties spanned, as v0 did (DEC-53 makes that opt-in in v1)"""
    if func is MISSING:  # `@instrument_decorate(func_name=...)`: v0 raised a TypeError here
        return lambda f: instrument_decorate(f, func_name=func_name)
    return otel(func, name=func_name, properties=True if isinstance(func, type) else None)


@_alias('use otel.instrument(app)', _first)
def instrument_fastapi_app(app: Any) -> Any:
    """the app, instrumented; anything that is not a Starlette or FastAPI app comes back unchanged, as in v0"""
    if not _is_instance(app, 'starlette.applications', 'Starlette'):
        _tell('instrument_fastapi_app not an app',
              f'instrument_fastapi_app() was given a {type(app).__qualname__}, not a FastAPI or Starlette app; '
              f'nothing was instrumented')
        return app
    if _missing('fastapi', 'fastapi', 'instrument_fastapi_app()'):
        return app
    return otel.instrument(app)


@_alias('use otel.instrument(sqlalchemy)', _none)
def instrument_sqlalchemy() -> Any:
    module = _import('sqlalchemy', 'sqlalchemy', 'instrument_sqlalchemy()')
    return None if module is None else otel.instrument(module)


@_alias('use otel.instrument(engine) (it adds no sqlcommenter comment unless OTEL_WRAPPER_SQLALCHEMY_COMMENTER=true)',
        _first)
def instrument_sqlalchemy_engine(engine: Any, enable_commenter: Any = MISSING,
                                 commenter_options: Any = MISSING) -> Any:
    """the engine, instrumented; anything that is not an Engine or AsyncEngine comes back unchanged, as in v0"""
    given = _given(enable_commenter=enable_commenter, commenter_options=commenter_options)
    if given:
        _tell('instrument_sqlalchemy_engine options',
              f'instrument_sqlalchemy_engine(): {given} ignored: set OTEL_WRAPPER_SQLALCHEMY_COMMENTER=true for the '
              f'sqlcommenter comment, or to a comma-separated list of db_driver, db_framework, opentelemetry_values')
    if not (_is_instance(engine, 'sqlalchemy.engine', 'Engine')
            or _is_instance(engine, 'sqlalchemy.ext.asyncio', 'AsyncEngine')):
        _tell('instrument_sqlalchemy_engine not an engine',
              f'instrument_sqlalchemy_engine() was given a {type(engine).__qualname__}, not a SQLAlchemy Engine or '
              f'AsyncEngine; nothing was instrumented')
        return engine
    if _missing('sqlalchemy', 'sqlalchemy', 'instrument_sqlalchemy_engine()'):
        return engine
    return otel.instrument(engine)


@_alias('use otel.instrument(requests)', _none)
def instrument_requests() -> Any:
    module = _import('requests', 'requests', 'instrument_requests()')
    return None if module is None else otel.instrument(module)


LOGGING_OPTIONS_REPLACED = ('the level is OTEL_WRAPPER_LOG_LEVEL, the JSON lines always go to stderr '
                            '(OTEL_WRAPPER_LOG_FORMAT=off turns them off), and there is no text format, no log file '
                            'and no clobber_other_log_handlers')


@_alias('use otel.instrument(logging)', _none)
def instrument_logging(*, level: Any = MISSING, path: Any = MISSING, stream: Any = MISSING, print_json: Any = MISSING,
                       clobber_other_log_handlers: Any = MISSING, **others: Any) -> Any:
    """v0's options are accepted and ignored (DEC-43): v1 takes its logging settings from the environment"""
    given = _given(level=level, path=path, stream=stream, print_json=print_json,
                   clobber_other_log_handlers=clobber_other_log_handlers, **others)
    if given:
        _tell('instrument_logging options', f'instrument_logging(): {given} ignored: {LOGGING_OPTIONS_REPLACED}')
    import logging
    return otel.instrument(logging)


def _system_metrics(explicit: bool) -> None:
    """`otel.instrument()`'s system-metrics part on its own; `explicit`: say so when the extra is missing"""
    from opentelemetry_wrapper.v1 import _config
    from opentelemetry_wrapper.v1 import _instrument
    from opentelemetry_wrapper.v1._warnings import warn
    if _env.disabled():
        return
    if not _instrument._installed('psutil', 'opentelemetry.instrumentation.system_metrics'):
        if explicit:
            _tell('instrument_system_metrics() missing', 'instrument_system_metrics() did nothing: the system metrics '
                                                         'instrumentation is not installed. Install '
                                                         'opentelemetry_wrapper[system-metrics]')
        return
    _config.ensure_configured()
    notes: list = []
    _instrument._guarded('system metrics', _instrument.instrument_system_metrics, notes)
    for note in notes:
        warn(note)


@_alias('use otel.instrument() (with the [system-metrics] extra)', _none)
def instrument_system_metrics() -> None:
    _system_metrics(explicit=True)


@_alias('use otel.instrument(), and otel.instrument(sqlalchemy) for sqlalchemy=True (dataclasses are not '
        'instrumented: put @otel on the ones you want)', _none)
def instrument_all(dataclasses: bool = True, logging: bool = True, requests: bool = True, sqlalchemy: bool = False,
                   system_metrics: bool = True, log_json: Any = MISSING, clobber_other_log_handlers: Any = MISSING,
                   ) -> None:
    """`otel.instrument()`; v0's switches still choose the parts (`sqlalchemy=True`: `otel.instrument(sqlalchemy)`);
    `dataclasses` does nothing (DEC-42), `log_json` and `clobber_other_log_handlers` are ignored (DEC-43)"""
    given = _given(log_json=log_json, clobber_other_log_handlers=clobber_other_log_handlers)
    if given:
        _tell('instrument_all options', f'instrument_all(): {given} ignored: {LOGGING_OPTIONS_REPLACED}')
    from opentelemetry_wrapper.v1._instrument import _installed
    lost = [extra for extra, wanted, modules in (
        ('requests', requests, ('requests', 'opentelemetry.instrumentation.requests')),
        ('system-metrics', system_metrics, ('psutil', 'opentelemetry.instrumentation.system_metrics')))
        if wanted and not _installed(*modules)]
    if lost:  # v0 had them as core dependencies, and `otel.instrument()` skips them silently
        _tell('instrument_all missing', f'instrument_all(): {" and ".join(lost)} not instrumented: Install '
                                        f'opentelemetry_wrapper[{",".join(lost)}]')
    if logging and requests and system_metrics:
        otel.instrument()
    else:
        if logging:
            import logging as logging_module
            otel.instrument(logging_module)
        if requests:
            if _installed('requests', 'opentelemetry.instrumentation.requests'):  # as `otel.instrument()`: if there
                otel.instrument(importlib.import_module('requests'))
        if system_metrics:
            _system_metrics(explicit=False)
    if sqlalchemy:
        module = _import('sqlalchemy', 'sqlalchemy', 'instrument_all(sqlalchemy=True)')
        if module is not None:
            otel.instrument(module)
    return None


@_alias('it does nothing: put @otel on the dataclasses you want', _none)
def instrument_dataclasses() -> None:
    """does nothing (DEC-42): patching `dataclasses.dataclass` reached only dataclasses decorated after the call"""
    return None
