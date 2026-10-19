"""
`otel.instrument(x)`: one idempotent, never-crash function per integration (DEC-19, DEC-11)

each records what it already instrumented (weakly, where the target is an object), and swallows a failure with one
warning, at instrumentation time only. an instrumentor's `DependencyConflict` is only logged upstream and produces no
spans, so we check for it and warn ourselves. SQLAlchemy has two ways in (DEC-1): the module, globally, for engines
created later, and each engine, through its own `EngineTracer`. later workstreams extend these: logging's JSON output
(8, `_logging`), the Prometheus route (9, `_prometheus`); the header hooks (5) are `_headers`
"""
import importlib.util
import os
import sys
import types
import weakref
from typing import Any
from typing import Dict
from typing import List
from typing import Mapping
from typing import Optional

from opentelemetry_wrapper.v1 import _config
from opentelemetry_wrapper.v1 import _env
from opentelemetry_wrapper.v1 import _headers
from opentelemetry_wrapper.v1._warnings import warn

MISSING: Any = object()
FASTAPI_EXCLUDE_SPANS = ['send', 'receive']  # verified: only the server span remains

_apps: 'weakref.WeakSet[Any]' = weakref.WeakSet()
_engines: 'weakref.WeakSet[Any]' = weakref.WeakSet()
_engine_ids: set = set()  # fallback for engines that can't be weakly referenced

SQLALCHEMY_COMMENTER_ENV = 'OTEL_WRAPPER_SQLALCHEMY_COMMENTER'
SQLALCHEMY_COMMENTER_FIELDS = ('db_driver', 'db_framework', 'opentelemetry_values')  # upstream's `commenter_options`
# what upstream's `_instrument` names its `db.client.connections.usage` counter (the canary is
# tests/upstream/test_sqlalchemy_engine_tracer.py)
SQLALCHEMY_CONNECTIONS_USAGE = {
    'name': 'db.client.connections.usage', 'unit': 'connections',
    'description': 'The number of connections that are currently in state described by the state attribute.'}


def instrument(target: Any = MISSING) -> Any:
    """instrument a library, an app or an engine (or, with no argument, everything global that's installed)"""
    if _env.disabled():
        return None if target is MISSING else target
    if target is MISSING or _is_integration_target(target) or not callable(target):
        # eagerly: off the first request and out of the event loop (DEC-27). decorating a function or class is the
        # same as `@otel` and never configures. outside the `try` below: its warnings may be error-filtered (DEC-49)
        _config.ensure_configured()
    notes: List[str] = []
    try:
        result = _dispatch(target, notes)
    except Exception as e:
        notes.append(f'otel.instrument({_short(target)}) failed and was skipped: {type(e).__name__}: {e}')
        result = None if target is MISSING else target
    for note in notes:
        warn(note)
    return result


def _short(target: Any) -> str:
    if target is MISSING:
        return ''
    if isinstance(target, types.ModuleType):
        return target.__name__
    return f'<{type(target).__module__}.{type(target).__qualname__} object>'


def _installed(*modules: str) -> bool:
    try:
        return all(importlib.util.find_spec(m) is not None for m in modules)
    except (ImportError, ValueError):
        return False


def _isinstance_of(target: Any, module: str, name: str) -> bool:
    mod = sys.modules.get(module)  # never import a library just to check a type
    cls = getattr(mod, name, None) if mod is not None else None
    return isinstance(cls, type) and isinstance(target, cls)


def _guarded(label: str, step: Any, notes: List[str]) -> None:
    """one integration: a failure in it is one warning, and the next integration still runs"""
    try:
        step(notes)
    except Exception as e:
        notes.append(f'otel.instrument(): {label} failed and was skipped: {type(e).__name__}: {e}')


def _is_integration_target(target: Any) -> bool:
    """a module, an app or an engine: what `instrument` configures for, as opposed to a function or class"""
    return (isinstance(target, types.ModuleType)
            or _isinstance_of(target, 'starlette.applications', 'Starlette')
            or _isinstance_of(target, 'sqlalchemy.engine', 'Engine')
            or _isinstance_of(target, 'sqlalchemy.ext.asyncio', 'AsyncEngine'))


def _dispatch(target: Any, notes: List[str]) -> Any:
    if target is MISSING:  # DEC-11: logging, requests, system metrics; never apps, engines or SQLAlchemy
        _guarded('logging', instrument_logging, notes)
        if _installed('requests', 'opentelemetry.instrumentation.requests'):
            _guarded('requests', instrument_requests, notes)
        if _installed('psutil', 'opentelemetry.instrumentation.system_metrics'):
            _guarded('system metrics', instrument_system_metrics, notes)
        return None
    if isinstance(target, types.ModuleType):
        handler = {'logging': instrument_logging, 'requests': instrument_requests,
                   'sqlalchemy': instrument_sqlalchemy}.get(target.__name__)
        if handler is None:
            notes.append(f'otel.instrument({target.__name__}) is not supported (supported modules: logging, requests, '
                         f'sqlalchemy); nothing was instrumented')
        else:
            handler(notes)
        return target
    if _isinstance_of(target, 'starlette.applications', 'Starlette'):
        return instrument_app(target, notes)
    if (_isinstance_of(target, 'sqlalchemy.engine', 'Engine')
            or _isinstance_of(target, 'sqlalchemy.ext.asyncio', 'AsyncEngine')):
        return instrument_engine(target, notes)
    if callable(target):  # functions and classes: the same as `@otel`
        from opentelemetry_wrapper.v1._decorator import decorate
        return decorate(target)
    notes.append(f'otel.instrument() cannot instrument {_short(target)}; returned unchanged')
    return target


def _run_instrumentor(instrumentor: Any, what: str, notes: List[str], **kwargs: Any) -> None:
    from opentelemetry.instrumentation.dependencies import get_dependency_conflicts
    if instrumentor.is_instrumented_by_opentelemetry:
        return
    conflict = get_dependency_conflicts(instrumentor.instrumentation_dependencies())
    if conflict is not None:
        notes.append(f'{what} was not instrumented: {conflict}. (upstream only logs this, and produces no spans)')
        return
    instrumentor.instrument(**kwargs)


def instrument_logging(notes: List[str]) -> None:
    """two handlers on the root logger, each once: OTLP log records and (unless `log_format` is off) one-line JSON on
    stderr (`_logging`, workstream 8); the level is the configured one"""
    from opentelemetry_wrapper.v1 import _logging
    _logging.instrument(_config.logger_provider(), _config.settings().log_format, notes)
    _config.mark_logging_instrumented()


def instrument_requests(notes: List[str]) -> None:
    """client spans, with the listed response headers (upstream latency, OTW-7); a forwarded x-userinfo that header
    capture records is redacted"""
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    settings = _config.settings()
    _run_instrumentor(RequestsInstrumentor(), 'requests', notes,
                      request_hook=_headers.requests_request_hook(settings.header_attributes),
                      response_hook=_headers.requests_response_hook(settings.response_header_attributes))


def instrument_system_metrics(notes: List[str]) -> None:
    from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor
    _run_instrumentor(SystemMetricsInstrumentor(), 'system metrics', notes)


def _sqlalchemy_instrumentation_missing(what: str, error: ImportError, notes: List[str]) -> None:
    """the `[sqlalchemy]` extra is missing (or sqlalchemy itself, which the instrumentation imports): one warning"""
    notes.append(f'otel.instrument({what}) did nothing: the SQLAlchemy instrumentation cannot be imported ({error}). '
                 f'Install opentelemetry_wrapper[sqlalchemy]')


def _sqlalchemy_asyncio_available() -> bool:
    try:
        importlib.import_module('sqlalchemy.ext.asyncio')
    except ImportError:
        return False
    return True


def _sqlalchemy_sync_patches_applied() -> bool:
    """upstream's `create_engine` and `Engine.connect` patches are in place (wrapt wrappers have `__wrapped__`)"""
    import sqlalchemy
    from sqlalchemy.engine.base import Engine
    return hasattr(sqlalchemy.create_engine, '__wrapped__') and hasattr(Engine.connect, '__wrapped__')


def instrument_sqlalchemy(notes: List[str]) -> None:
    """every engine created from now on, with `connect` spans (DEC-1); engines that already exist are not reached, so
    they are passed in as well (`instrument_engine`)"""
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    except ImportError as e:
        _sqlalchemy_instrumentation_missing('sqlalchemy', e, notes)
        return
    instrumentor = SQLAlchemyInstrumentor()
    try:
        _run_instrumentor(instrumentor, 'sqlalchemy', notes, **sqlalchemy_commenter(notes))
    except ImportError:
        # without sqlalchemy's asyncio extension (sqlalchemy 2.1 without greenlet), upstream patches `create_engine`
        # and `Engine.connect`, then fails on `sqlalchemy.ext.asyncio.create_async_engine` and never sets its flag:
        # sync engines are traced, and a second call would patch them twice (two `connect` spans, two tracers)
        if _sqlalchemy_asyncio_available() or not _sqlalchemy_sync_patches_applied():
            raise
        instrumentor._is_instrumented_by_opentelemetry = True


def sqlalchemy_commenter(notes: List[str], environ: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    """`EngineTracer`'s sqlcommenter arguments, from `OTEL_WRAPPER_SQLALCHEMY_COMMENTER` (read at each call, like
    `OTEL_WRAPPER_DISABLED`): unset or `false`, off (upstream's default); `true`, a comment with the driver, the
    framework and the traceparent on every query; or a comma-separated choice of `db_driver`, `db_framework` and
    `opentelemetry_values` (the traceparent), plus `attribute` to record the commented statement on the span too.
    v0's `instrument_sqlalchemy_engine` turned it on by default; v1 leaves the SQL unchanged unless asked"""
    environ = os.environ if environ is None else environ
    raw = (environ.get(SQLALCHEMY_COMMENTER_ENV) or '').strip().casefold()
    if raw in ('', 'false'):
        return {}
    words = [w.strip() for w in raw.split(',') if w.strip()]
    unknown = [w for w in words if w not in SQLALCHEMY_COMMENTER_FIELDS + ('true', 'attribute')]
    if unknown:
        notes.append(f'{SQLALCHEMY_COMMENTER_ENV}: {", ".join(unknown)} not understood (use true, false, or any of '
                     f'{", ".join(SQLALCHEMY_COMMENTER_FIELDS)} and attribute); ignored')
    chosen = SQLALCHEMY_COMMENTER_FIELDS if 'true' in words else [w for w in words if w in SQLALCHEMY_COMMENTER_FIELDS]
    if not chosen:
        if 'attribute' in words:
            notes.append(f'{SQLALCHEMY_COMMENTER_ENV}=attribute needs something to comment with (true, or any of '
                         f'{", ".join(SQLALCHEMY_COMMENTER_FIELDS)}); the sqlcommenter stays off')
        return {}
    return {'enable_commenter': True,
            'commenter_options': {field: field in chosen for field in SQLALCHEMY_COMMENTER_FIELDS},
            'enable_attribute_commenter': 'attribute' in words}


def _root_engine(engine: Any) -> Any:
    """the engine an `OptionEngine` (`engine.execution_options(...)`) was made from, through any number of them. an
    option engine shares its parent's pool and joins its parent's event dispatch: a tracer on the parent traces it
    too, while a tracer on it alone is invisible from the parent, which would then get a second tracer (a leaked span
    and a doubled connection count per query through the option engine). so the tracer goes on the root"""
    for _ in range(100):  # a cycle would be a sqlalchemy bug; never loop on it
        proxied = getattr(engine, '_proxied', None)  # semi-private: the canary is test_sqlalchemy_engine_tracer.py
        if proxied is None or not _isinstance_of(proxied, 'sqlalchemy.engine', 'Engine'):
            break
        engine = proxied
    return engine


def _traced_by_upstream(engine: Any, engine_tracer: type) -> bool:
    """an `EngineTracer` already listens to this engine: `otel.instrument(sqlalchemy)` attached one when it was
    created. a second tracer would start a second span per query and leak the first"""
    listeners = getattr(getattr(engine, 'dispatch', None), 'before_cursor_execute', ())
    return any(isinstance(getattr(listener, '__self__', None), engine_tracer) for listener in listeners)


def _sqlalchemy_tracer_and_counter() -> Any:
    """what upstream's `_instrument` makes: the same instrumentation scope (schema url included), so a passed-in
    engine's spans look like the global instrumentation's, and the `db.client.connections.usage` counter, which is a
    local there, so we create our own from the same meter"""
    from opentelemetry import metrics
    from opentelemetry import trace
    from opentelemetry.instrumentation.sqlalchemy.version import __version__
    schema_url = None
    try:  # semi-private (the canary is tests/upstream/test_sqlalchemy_engine_tracer.py)
        from opentelemetry.instrumentation._semconv import _get_schema_url_for_signal_types
        from opentelemetry.instrumentation._semconv import _OpenTelemetrySemanticConventionStability
        from opentelemetry.instrumentation._semconv import _OpenTelemetryStabilitySignalType
        _OpenTelemetrySemanticConventionStability._initialize()
        schema_url = _get_schema_url_for_signal_types([_OpenTelemetryStabilitySignalType.DATABASE,
                                                       _OpenTelemetryStabilitySignalType.HTTP])
    except Exception:  # an upstream change: the spans lose their schema url, nothing else
        pass
    name = 'opentelemetry.instrumentation.sqlalchemy'
    tracer = trace.get_tracer(name, __version__, schema_url=schema_url)
    meter = metrics.get_meter(name, __version__, schema_url=schema_url)
    connections_usage = meter.create_up_down_counter(**SQLALCHEMY_CONNECTIONS_USAGE)
    return tracer, connections_usage


def instrument_engine(engine: Any, notes: List[str]) -> Any:
    """one engine's queries, once per engine, whether or not it existed before `otel.instrument(sqlalchemy)`; an
    AsyncEngine through its sync engine, an option engine through the engine it was made from. no `connect` spans:
    those come only from the global patch (DEC-1). attaching `EngineTracer` ourselves skips upstream's dependency
    check, and works without sqlalchemy's asyncio extension"""
    sync_engine = _root_engine(getattr(engine, 'sync_engine', engine))
    try:
        if sync_engine in _engines:
            return engine
    except TypeError:
        if id(sync_engine) in _engine_ids:
            return engine
    try:
        from opentelemetry.instrumentation.sqlalchemy.engine import EngineTracer
    except ImportError as e:
        _sqlalchemy_instrumentation_missing(_short(engine), e, notes)
        return engine
    if not _traced_by_upstream(sync_engine, EngineTracer):
        tracer, connections_usage = _sqlalchemy_tracer_and_counter()
        EngineTracer(tracer, sync_engine, connections_usage, **sqlalchemy_commenter(notes))
    try:
        _engines.add(sync_engine)
    except TypeError:
        _engine_ids.add(id(sync_engine))
    return engine


def instrument_app(app: Any, notes: List[str]) -> Any:
    """FastAPI / Starlette: request spans, once per app; an app that already started can't take middleware"""
    if app in _apps or getattr(app, '_is_instrumented_by_opentelemetry', False):
        return app
    if getattr(app, 'middleware_stack', None) is not None:
        notes.append('otel.instrument(app) was called after the app started, when middleware can no longer be added; '
                     'the app is returned uninstrumented. Instrument it before serving requests')
        return app
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.dependencies import get_dependency_conflicts
    conflict = get_dependency_conflicts(FastAPIInstrumentor().instrumentation_dependencies())
    if conflict is not None:
        notes.append(f'the app was not instrumented: {conflict}. (upstream only logs this, and produces no spans)')
        return app
    settings = _config.settings()
    FastAPIInstrumentor.instrument_app(  # the caller's x-userinfo claims on the server span, never the raw value
        app, exclude_spans=FASTAPI_EXCLUDE_SPANS,
        excluded_urls=_excluded_urls(settings.prometheus_path, os.environ),
        server_request_hook=_headers.server_request_hook(settings.header_attributes,
                                                         settings.header_attributes_exclude),
        http_capture_headers_sanitize_fields=_headers.sanitize_fields(settings.header_attributes, os.environ))
    _apps.add(app)
    if settings.prometheus_path:
        _guarded('the Prometheus route', lambda _: _add_prometheus_route(app, settings.prometheus_path), notes)
    return app


def _excluded_urls(prometheus_path: str, environ: Mapping[str, str]) -> Optional[str]:
    """upstream's `excluded_urls`: the app's own choice (`OTEL_PYTHON_FASTAPI_EXCLUDED_URLS`, else
    `OTEL_PYTHON_EXCLUDED_URLS`, which passing the argument would otherwise replace), plus the Prometheus path
    exactly"""
    from opentelemetry_wrapper.v1 import _prometheus
    if not prometheus_path:
        return None  # upstream reads the variables itself
    own = environ.get('OTEL_PYTHON_FASTAPI_EXCLUDED_URLS', environ.get('OTEL_PYTHON_EXCLUDED_URLS', ''))
    return ','.join(part for part in (own.strip(), _prometheus.excluded_url(prometheus_path)) if part)


def _add_prometheus_route(app: Any, path: str) -> None:
    """the scrape route (workstream 9), placed when the app builds its middleware stack (at its first request), not
    now: `app = otel.instrument(FastAPI())` has no routes yet, and the app's own route at that path, declared later,
    must win. the stack it builds (upstream's, request spans included) is wrapped so the scrape makes no request span
    under a `root_path` either (`_prometheus.untraced_under_root_path`)"""
    from opentelemetry_wrapper.v1 import _prometheus
    build = app.build_middleware_stack

    def build_middleware_stack() -> Any:
        _prometheus.place_route(app, path)
        return _prometheus.untraced_under_root_path(build(), path)

    app.build_middleware_stack = build_middleware_stack
