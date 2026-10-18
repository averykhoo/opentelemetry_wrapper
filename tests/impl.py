"""
the adapter between the test suite and the package under test (DEC-38)

the tests never import `opentelemetry_wrapper` names directly; they ask this module, which binds neutral names to
the implementation selected by the `OTW_IMPL` env var: `v0` (the default) or `v1`. plain tests must pass under both,
`@pytest.mark.v0_specific` tests are v0-only (skipped under v1, see `tests/conftest.py`)

    from tests.impl import decorate         # in a scenario script (child interpreter)
    otw.decorate(f)                          # in a test, via the `otw` fixture, which hands out this module

names are resolved lazily, on first access, so that importing this module never imports the package (scenarios
care about what is imported when). v1 does not exist yet, so under `OTW_IMPL=v1` every name resolves to a stub that
raises `NotImplementedError` when called: collection and the rest of the run still work. bind a v1 name by filling
in `_V1` once the v1 api is settled; don't invent it here

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
"""
import os
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
_V1: Dict[str, str] = {}  # nothing is bound yet: v1 has no api

_NAMES = tuple(_V0) + ('__all__',)


def load() -> None:
    """import the package under test, for its import-time side effects (v0 installs the tracer provider)"""
    import opentelemetry_wrapper  # noqa: F401


def require_v0(what: str) -> None:
    """for test helpers that reach into v0 internals: fail clearly under v1 instead of importing v0 by accident"""
    if IMPL != 'v0':
        raise NotImplementedError(f'{what} uses v0 internals, and OTW_IMPL={IMPL} has no binding for it yet')


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
        import opentelemetry_wrapper as package
        return getattr(package, _V1[name])
    if name in ('__version__', '__all__'):  # not callable, so a stub cannot stand in for them
        raise NotImplementedError(f'tests.impl.{name}: OTW_IMPL={IMPL} has no binding for it yet')
    return _unbound(name)


def __getattr__(name: str) -> Any:  # PEP 562: called only for names not found the normal way
    if name not in _NAMES:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
    value = _resolve(name)
    globals()[name] = value  # resolved once
    return value
