"""
the adapter between the test suite and the package under test (DEC-38)

the tests never import `opentelemetry_wrapper` names directly; they ask this module, which binds neutral names to
the implementation selected by the `OTW_IMPL` env var: `v0` (the default) or `v1`. plain tests must pass under both,
`@pytest.mark.v0_specific` tests are v0-only (skipped under v1, see `tests/conftest.py`)

    from tests.impl import decorate         # in a scenario script (child interpreter)
    otw.decorate(f)                          # in a test, via the `otw` fixture, which hands out this module

names are resolved lazily, on first access, so that importing this module never imports the package (scenarios
care about what is imported when). under `OTW_IMPL=v1` the names bind to v1's `otel` (OTW-3, below); a name v1
drops (`instrument_dataclasses`) or doesn't have (`__version__`, `__all__`) resolves to a stub that raises
`NotImplementedError` when called, so collection and the rest of the run still work

v1 is imported through `import_v1()`. the package root is v1 (DEC-80) and imports no v0, so nothing is skipped: v0
is imported only when a test asks for a v0 name (v0 installs its tracer provider at import)

the interface:

    neutral name            v0 public name (`opentelemetry_wrapper.<name>`)
    decorate                instrument_decorate
    instrument_app          instrument_fastapi_app
    instrument_engine       instrument_sqlalchemy_engine
    setup                   instrument_all
    instrument_logging      (same)
    instrument_requests     (same)
    instrument_dataclasses  (same)
    instrument_sqlalchemy   (same)
    instrument_system_metrics (same; importable but missing from v0's `__all__`)
    __version__             (same)
    __all__                 v0's `__all__`, translated to the neutral names

    neutral name            v1 (`otel` is `opentelemetry_wrapper.v1.otel`)
    decorate                `otel(f)`, or `otel(f, name=func_name)`; `properties=True` (v1 only): a class's
                            properties too
    instrument_app          `otel.instrument(app)`
    instrument_engine       `otel.instrument(engine)`
    setup                   `otel.instrument()`, plus `otel.instrument(sqlalchemy)` for `sqlalchemy=True`
    instrument_logging      `otel.instrument(logging)`
    instrument_requests     `otel.instrument(requests)`
    instrument_sqlalchemy   `otel.instrument(sqlalchemy)`
    instrument_system_metrics  v1's system metrics integration (part of `otel.instrument()`)
"""
import os
import types
from typing import Any
from typing import Dict
from typing import Mapping
from typing import Optional

IMPLS = ('v0', 'v1')


def selected_impl(environ: Optional[Mapping[str, str]] = None) -> str:
    """the implementation named by `OTW_IMPL` (unset or empty means v0); anything but v0 / v1 is an error"""
    value = (os.environ if environ is None else environ).get('OTW_IMPL') or 'v0'
    if value not in IMPLS:
        raise ValueError(f'OTW_IMPL={value!r} is not valid, expected one of {" or ".join(IMPLS)}')
    return value


IMPL = selected_impl()

# neutral name -> name in the implementation's public api (`opentelemetry_wrapper`)
_V0 = {
    'decorate':                  'instrument_decorate',
    'instrument_app':            'instrument_fastapi_app',
    'instrument_engine':         'instrument_sqlalchemy_engine',
    'setup':                     'instrument_all',
    'instrument_logging':        'instrument_logging',
    'instrument_requests':       'instrument_requests',
    'instrument_dataclasses':    'instrument_dataclasses',
    'instrument_sqlalchemy':     'instrument_sqlalchemy',
    'instrument_system_metrics': 'instrument_system_metrics',
    '__version__':               '__version__',
}


def import_v1() -> types.ModuleType:
    """
    `opentelemetry_wrapper.v1`. importing it (and the package root above it) imports no v0, so v1 is not "configured
    first" by v0's tracer provider unless something in the process asked for a v0 name already, as an app that mixes
    them would
    """
    import opentelemetry_wrapper.v1 as v1
    return v1


def _v1_decorate(func: Any, /, *, func_name: Optional[str] = None, properties: Optional[bool] = None) -> Any:
    """`properties` is v1-only (a class's properties are opt-in, DEC-53): v0 has no such option, so a test passes it
    only under v1"""
    otel = import_v1().otel
    return otel(func, name=func_name, properties=properties)


def _v1_module(name: str):
    def instrument(*args: Any, **kwargs: Any) -> Any:  # v0's options have no v1 equivalent per call (PLAN, logging)
        import importlib
        return import_v1().otel.instrument(importlib.import_module(name))

    instrument.__name__ = instrument.__qualname__ = f'instrument_{name}'
    return instrument


def _v1_setup(dataclasses: bool = True, logging: bool = True, requests: bool = True, sqlalchemy: bool = False,
              system_metrics: bool = True, log_json: bool = True, clobber_other_log_handlers: bool = False) -> None:
    otel = import_v1().otel
    if logging and requests and system_metrics:
        otel.instrument()
    else:
        if logging:
            _v1_module('logging')()
        if requests:
            _v1_module('requests')()
        if system_metrics:
            _v1_system_metrics()
    if sqlalchemy:
        _v1_module('sqlalchemy')()


def _v1_system_metrics(*args: Any, **kwargs: Any) -> None:
    import_v1()
    from opentelemetry_wrapper.v1._instrument import instrument_system_metrics
    instrument_system_metrics([])


_V1: Dict[str, Any] = {
    'decorate':                  _v1_decorate,
    'instrument_app':            lambda app: import_v1().otel.instrument(app),  # noqa: E272
    'instrument_engine':         lambda engine, *args, **kwargs: import_v1().otel.instrument(engine),  # noqa: E272
    'setup':                     _v1_setup,
    'instrument_logging':        _v1_module('logging'),
    'instrument_requests':       _v1_module('requests'),
    'instrument_sqlalchemy':     _v1_module('sqlalchemy'),
    'instrument_system_metrics': _v1_system_metrics,
}


def span_exporter() -> Any:
    """under v1: an in-memory span exporter that receives every span v1 finishes (through v1's test sink, the one
    the pytest plugin uses); v0's capture stays with its callers (`tests/conftest.py`, `tests/v0/_child.py`)"""
    require_v1('span_exporter')
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    import_v1()
    from opentelemetry_wrapper.v1 import _config
    exporter = InMemorySpanExporter()
    _config.add_span_sink(exporter)
    return exporter


_NAMES = tuple(_V0) + ('__all__',)


def load() -> None:
    """
    import the package under test, for its import-time side effects: v0 installs the tracer provider. v1 installs
    nothing at import and configures implicitly, from env vars, at the first span or `otel.instrument` (DEC-27), so
    under v1 this does that implicit configuration (a no-op when something configured already, or when disabled)
    """
    if IMPL == 'v1':
        import_v1()
        from opentelemetry_wrapper.v1 import _config
        _config.ensure_configured()
        return
    import opentelemetry_wrapper
    opentelemetry_wrapper.instrument_decorate  # noqa: B018 - the root loads v0 lazily, on the first v0 name


def require_v0(what: str) -> None:
    """for test helpers that reach into v0 internals: fail clearly under v1 instead of importing v0 by accident"""
    if IMPL != 'v0':
        raise NotImplementedError(f'{what} uses v0 internals, and OTW_IMPL={IMPL} has no binding for it yet')


def require_v1(what: str) -> None:
    if IMPL != 'v1':
        raise NotImplementedError(f'{what} is v1-only, and OTW_IMPL={IMPL}')


def _unbound(name: str):
    def stub(*args: Any, **kwargs: Any):
        raise NotImplementedError(f'tests.impl.{name} (v0: {_V0.get(name, name)}): '
                                  f'OTW_IMPL={IMPL} has no binding for it yet')

    stub.__name__ = stub.__qualname__ = name
    return stub


def _resolve(name: str) -> Any:
    if IMPL == 'v0':
        import opentelemetry_wrapper as package
        if name == '__all__':
            neutral_by_v0 = {v0_name: neutral for neutral, v0_name in _V0.items()}
            return [neutral_by_v0.get(v0_name, v0_name) for v0_name in package.__all__]
        return getattr(package, _V0[name])
    if name in _V1:
        return _V1[name]
    if name in ('__version__', '__all__'):  # not callable, so a stub cannot stand in for them
        raise NotImplementedError(f'tests.impl.{name}: OTW_IMPL={IMPL} has no binding for it yet')
    return _unbound(name)


def __getattr__(name: str) -> Any:  # PEP 562: called only for names not found the normal way
    if name not in _NAMES:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
    value = _resolve(name)
    globals()[name] = value  # resolved once
    return value
