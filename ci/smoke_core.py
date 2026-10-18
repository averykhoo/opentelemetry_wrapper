"""
the no-extras install check (DEC-56, AC-20): run by `ci/test.sh core` from a directory outside the checkout, after
`pip install .` (no extras), so what is imported is the installed package and nothing else was installed beside it
"""
import importlib.metadata
import sys

import opentelemetry_wrapper
import opentelemetry_wrapper.v1
from opentelemetry_wrapper.v1 import otel

assert 'site-packages' in opentelemetry_wrapper.__file__, f'not the installed package: {opentelemetry_wrapper.__file__}'

# DEC-36: not the opentelemetry-exporter-otlp meta package. grpcio itself is still installed while the package root
# imports v0 (its otel_providers.py needs the gRPC exporters; ASK-23): once the root stops, assert `grpc` is absent here
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

print(f'ok: python {sys.version.split()[0]}, opentelemetry_wrapper {opentelemetry_wrapper.__version__}')
