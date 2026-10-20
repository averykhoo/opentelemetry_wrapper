"""
the no-extras install check (DEC-56, AC-20): run by tests/test_install_core.py (`ci/test.sh core`, after `pip install .` with no extras) in a subprocess from a
directory outside the checkout, so what is imported is the installed package and nothing else was installed beside it
"""
import importlib.metadata
import importlib.util
import sys

import opentelemetry_wrapper
import opentelemetry_wrapper.v1
from opentelemetry_wrapper import otel

assert 'site-packages' in opentelemetry_wrapper.__file__, f'not the installed package: {opentelemetry_wrapper.__file__}'
assert otel is opentelemetry_wrapper.v1.otel
# DEC-96: the lean install. v0 is deleted, and none of its dependencies came with the plain install: no web
# framework, no ORM, no pydantic and no gRPC (DEC-36). `requests` is not checked: the OTLP HTTP exporter needs it
assert importlib.util.find_spec('opentelemetry_wrapper.v0') is None, 'v0 is still installed'
for absent in ('fastapi', 'starlette', 'sqlalchemy', 'pydantic', 'grpc', 'psutil',
               'opentelemetry.exporter.otlp.proto.grpc', 'opentelemetry.instrumentation.fastapi', 'opentelemetry.instrumentation.sqlalchemy',
               'opentelemetry.instrumentation.requests', 'opentelemetry.instrumentation.system_metrics'):
    try:
        found = importlib.util.find_spec(absent) is not None
    except ModuleNotFoundError:  # a missing parent package
        found = False
    assert not found, f'{absent} was installed by the plain install'

# DEC-36: not the opentelemetry-exporter-otlp meta package
try:
    importlib.metadata.version('opentelemetry-exporter-otlp')
except importlib.metadata.PackageNotFoundError:
    pass
else:
    raise AssertionError('the opentelemetry-exporter-otlp meta package was installed')

# py.typed ships, and the pytest plugin is registered under the name `-p no:opentelemetry_wrapper` turns off
assert any(f.name == 'py.typed' for f in importlib.metadata.files('opentelemetry_wrapper') or []), 'py.typed missing'
entry_points = importlib.metadata.entry_points(group='pytest11')
assert any(ep.name == 'opentelemetry_wrapper' and ep.value == 'opentelemetry_wrapper.v1.pytest_plugin'
           for ep in entry_points), list(entry_points)


@otel
def decorated(x):
    return x + 1


assert decorated(1) == 2

with otel('a block'):
    assert decorated(2) == 3

# v0's names are warn-once aliases onto v1 until 2.0 (DEC-96): with no extras, each one works or does nothing, and
# none raises
import opentelemetry_wrapper as root  # noqa: E402
assert root.instrument_decorate(decorated) is decorated  # already decorated: the same function
import logging  # noqa: E402
assert root.instrument_logging(print_json=False) is logging
assert root.instrument_requests() is None  # no [requests] extra: nothing, and one stderr line
assert root.instrument_sqlalchemy() is None
assert root.instrument_sqlalchemy_engine('not an engine') == 'not an engine'
assert root.instrument_fastapi_app('not an app') == 'not an app'
assert root.instrument_system_metrics() is None
assert root.instrument_all(sqlalchemy=True) is None
assert root.instrument_dataclasses() is None
assert decorated(3) == 4

print(f'ok: python {sys.version.split()[0]}, opentelemetry_wrapper {opentelemetry_wrapper.__version__}')
