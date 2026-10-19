"""
the no-extras install check (DEC-56, AC-20): run by tests/test_install_core.py (`ci/test.sh core`, after `pip install .` with no extras) in a subprocess from a
directory outside the checkout, so what is imported is the installed package and nothing else was installed beside it
"""
import importlib.metadata
import sys

import opentelemetry_wrapper
import opentelemetry_wrapper.v1
from opentelemetry_wrapper import otel

assert 'site-packages' in opentelemetry_wrapper.__file__, f'not the installed package: {opentelemetry_wrapper.__file__}'
assert otel is opentelemetry_wrapper.v1.otel
# DEC-80: the root is v1 and imports no v0 (v0's names load lazily, on first access)
assert not [m for m in sys.modules if m.startswith('opentelemetry_wrapper.v0')], 'importing the root imported v0'

# DEC-36: not the opentelemetry-exporter-otlp meta package. grpcio itself is still installed, because v0's
# otel_providers.py needs the gRPC exporters and v0's dependencies stay core until 1.0.0 (DEC-80): once v0 is deleted,
# assert `grpc` is absent here
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

# v0's names still resolve from the root (DEC-80), last: the first one imports v0 and runs its import-time setup
from opentelemetry_wrapper import instrument_decorate  # noqa: E402
assert callable(instrument_decorate)
assert 'opentelemetry_wrapper.v0.config.otel_headers' in sys.modules

print(f'ok: python {sys.version.split()[0]}, opentelemetry_wrapper {opentelemetry_wrapper.__version__}')
