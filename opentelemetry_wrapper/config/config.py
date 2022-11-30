import os
from typing import List
from typing import Optional

from opentelemetry_wrapper.config.header_attributes import get_header_attributes
from opentelemetry_wrapper.config.log_level import get_log_level
from opentelemetry_wrapper.config.service_name import get_default_service_name
from opentelemetry_wrapper.config.service_name import get_k8s_namespace
from opentelemetry_wrapper.config.service_name import getenv_otel_service_name

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
OTEL_SERVICE_NAMESPACE: Optional[str] = get_k8s_namespace() or None

# enable exporting to tempo for visualization in grafana
OTEL_EXPORTER_OTLP_ENDPOINT: str = os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', '').strip()

OTEL_LOG_LEVEL: int = get_log_level()

OTEL_HEADER_ATTRIBUTES: List[str] = get_header_attributes()
