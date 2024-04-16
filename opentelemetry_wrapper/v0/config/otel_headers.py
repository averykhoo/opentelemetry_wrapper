"""
all these settings will be (manually) logged at the INFO level if you call `instrument_all()`
"""
import os
from typing import List
from typing import Optional
from typing import Tuple

from opentelemetry_wrapper.v0.config.otel_exporter_otlp import getenv_otel_exporter_otlp_endpoint
from opentelemetry_wrapper.v0.config.otel_exporter_otlp import getenv_otel_exporter_otlp_header
from opentelemetry_wrapper.v0.config.otel_exporter_otlp import getenv_otel_exporter_otlp_insecure
from opentelemetry_wrapper.v0.config.otel_header_attributes import get_header_attributes
from opentelemetry_wrapper.v0.config.otel_log_level import get_log_level
from opentelemetry_wrapper.v0.config.otel_service_name import get_default_service_name
from opentelemetry_wrapper.v0.config.otel_service_name import get_k8s_namespace
from opentelemetry_wrapper.v0.config.otel_service_name import getenv_otel_service_name
from opentelemetry_wrapper.v0.config.otel_service_name import getenv_otel_service_namespace
from opentelemetry_wrapper.v0.config.otel_wrapper_prometheus_exporter import get_prometheus_endpoint
from opentelemetry_wrapper.v0.config.otel_wrapper_prometheus_exporter import get_prometheus_port

# global flag to override opentelemetry and not do anything
# because opentelemetry is too verbose in tests
# naming / terminology based on:
# https://opentelemetry.io/docs/reference/specification/sdk-environment-variables/#:~:text=OTEL_SDK_DISABLED
OTEL_WRAPPER_DISABLED: bool = os.getenv('OTEL_WRAPPER_DISABLED', 'false').casefold().strip() == 'true'

# tries these things, in order:
# 1. `OTEL_SERVICE_NAME` env var
# 2. `service.name` property from `OTEL_RESOURCE_ATTRIBUTES` env var
# 3. if running in k8s, returns {namespace}/{pod_name}
# 4. otherwise, f'{_username}{_hostname}{_namespace}{_filename}' (which technically breaks OpenTelemetry spec)
# 5. if all the above fails, falls back to 'unknown_service'
OTEL_SERVICE_NAME: str = getenv_otel_service_name() or get_default_service_name() or 'unknown_service'
OTEL_SERVICE_NAMESPACE: Optional[str] = getenv_otel_service_namespace() or get_k8s_namespace() or None

# exporting to OTLP, e.g. tempo for visualization in grafana
OTEL_EXPORTER_OTLP_ENDPOINT: str = getenv_otel_exporter_otlp_endpoint()
OTEL_EXPORTER_OTLP_HEADER: Tuple[Tuple[str, str], ...] = getenv_otel_exporter_otlp_header()
OTEL_EXPORTER_OTLP_INSECURE: Optional[bool] = getenv_otel_exporter_otlp_insecure()

OTEL_LOG_LEVEL: int = get_log_level()

OTEL_HEADER_ATTRIBUTES: List[str] = get_header_attributes()

OTEL_EXPORTER_PROMETHEUS_PORT: Optional[int] = get_prometheus_port()
OTEL_EXPORTER_PROMETHEUS_ENDPOINT: Optional[str] = get_prometheus_endpoint()
