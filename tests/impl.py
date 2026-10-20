"""
the adapter between the characterization suite (`tests/v0`) and the package (DEC-38)

`tests/v0` was written against v0's api and now characterizes what v1 keeps of v0's behaviour, so it asks this module
for neutral names, which bind to v1's `otel`; the v1 tests import v1 through `import_v1()`

    from tests.impl import decorate         # in a scenario script (child interpreter)
    otw.decorate(f)                          # in a test, via the `otw` fixture, which hands out this module

importing this module never imports the package (scenarios care about what is imported when): each name imports v1
when it is called. v0's `instrument_dataclasses` has no neutral name, as v1 drops it (DEC-42)

    neutral name               v1 (`otel` is `opentelemetry_wrapper.v1.otel`)       v0 name it stands for
    decorate                   `otel(f)`, or `otel(f, name=func_name)`;              instrument_decorate
                               `properties=True`: a class's properties too (DEC-53)
    instrument_app             `otel.instrument(app)`                                instrument_fastapi_app
    instrument_engine          `otel.instrument(engine)`                             instrument_sqlalchemy_engine
    setup                      `otel.instrument()`, plus                             instrument_all
                               `otel.instrument(sqlalchemy)` for `sqlalchemy=True`
    instrument_logging         `otel.instrument(logging)`                            (same)
    instrument_requests        `otel.instrument(requests)`                           (same)
    instrument_sqlalchemy      `otel.instrument(sqlalchemy)`                         (same)
    instrument_system_metrics  v1's system metrics integration (part of             (same)
                               `otel.instrument()`)
"""
import importlib
import types
from typing import Any
from typing import Optional


def import_v1() -> types.ModuleType:
    """`opentelemetry_wrapper.v1`"""
    import opentelemetry_wrapper.v1 as v1
    return v1


def decorate(func: Any, /, *, func_name: Optional[str] = None, properties: Optional[bool] = None) -> Any:
    return import_v1().otel(func, name=func_name, properties=properties)


def _instrument_module(name: str):
    def instrument(*args: Any, **kwargs: Any) -> Any:  # v0's options have no v1 equivalent per call (DEC-43)
        return import_v1().otel.instrument(importlib.import_module(name))

    instrument.__name__ = instrument.__qualname__ = f'instrument_{name}'
    return instrument


instrument_logging = _instrument_module('logging')
instrument_requests = _instrument_module('requests')
instrument_sqlalchemy = _instrument_module('sqlalchemy')


def instrument_app(app: Any) -> Any:
    return import_v1().otel.instrument(app)


def instrument_engine(engine: Any, *args: Any, **kwargs: Any) -> Any:
    return import_v1().otel.instrument(engine)


def instrument_system_metrics(*args: Any, **kwargs: Any) -> None:
    import_v1()
    from opentelemetry_wrapper.v1._instrument import instrument_system_metrics as instrument
    instrument([])


def setup(dataclasses: bool = True, logging: bool = True, requests: bool = True, sqlalchemy: bool = False,
          system_metrics: bool = True, log_json: bool = True, clobber_other_log_handlers: bool = False) -> None:
    """v0's `instrument_all` signature; `dataclasses`, `log_json` and `clobber_other_log_handlers` do nothing in v1"""
    if logging and requests and system_metrics:
        import_v1().otel.instrument()
    else:
        if logging:
            instrument_logging()
        if requests:
            instrument_requests()
        if system_metrics:
            instrument_system_metrics()
    if sqlalchemy:
        instrument_sqlalchemy()


def span_exporter() -> Any:
    """an in-memory span exporter that receives every span v1 finishes (through v1's test sink, the one the pytest
    plugin uses)"""
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    import_v1()
    from opentelemetry_wrapper.v1 import _config
    exporter = InMemorySpanExporter()
    _config.add_span_sink(exporter)
    return exporter


def load() -> None:
    """
    configure the package as it would at its first span or `otel.instrument`: v1 installs nothing at import and
    configures implicitly, from env vars (DEC-27). a no-op when something configured already, or when disabled
    """
    import_v1()
    from opentelemetry_wrapper.v1 import _config
    _config.ensure_configured()
