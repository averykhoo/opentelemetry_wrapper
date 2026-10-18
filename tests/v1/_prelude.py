"""
the source every v1 scenario starts with: v1 imported without the package root (`tests/impl.py:import_v1`), and an
in-memory span exporter registered with v1's test sink (`exporter`), so a scenario sees what would be exported
"""
PRELUDE = r'''
import warnings
from tests.impl import import_v1
v1 = import_v1()
otel = v1.otel
from opentelemetry_wrapper.v1 import _config
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
exporter = InMemorySpanExporter()
_config.add_span_sink(exporter)


def otel_warnings(caught):
    return [str(w.message) for w in caught if issubclass(w.category, v1.OtelWrapperWarning)]
'''
