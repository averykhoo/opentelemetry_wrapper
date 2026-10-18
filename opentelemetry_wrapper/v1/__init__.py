"""
opentelemetry_wrapper v1: one `otel` object over the plain OpenTelemetry SDK (epic OTW-1)

    from opentelemetry_wrapper.v1 import otel

importing this module configures nothing: decorating never configures (DEC-27); `otel.instrument(...)` and
`otel.configure(...)` do, eagerly, and otherwise the first span does
"""
from opentelemetry_wrapper.v1._otel import Otel
from opentelemetry_wrapper.v1._otel import otel
from opentelemetry_wrapper.v1._warnings import OtelWrapperWarning

__all__ = ('otel', 'Otel', 'OtelWrapperWarning')
