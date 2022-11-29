import os

from opentelemetry_wrapper.config.service_name import get_default_service_name
from opentelemetry_wrapper.config.service_name import getenv_otel_service_name

# global flag to override opentelemetry and not do anything
# because opentelemetry is too verbose in tests
# naming / terminology based on:
# https://opentelemetry.io/docs/reference/specification/sdk-environment-variables/#:~:text=OTEL_SDK_DISABLED
OTEL_WRAPPER_DISABLED: bool = os.getenv('OTEL_WRAPPER_DISABLED', 'false').casefold().strip() == 'true'

# tries these 3 things, in order:
# 1. `OTEL_SERVICE_NAME` env var
# 2. `service.name` property from `OTEL_RESOURCE_ATTRIBUTES` env var
# 3. `get_default_service_name()` (which technically breaks OpenTelemetry spec)
# if all the above fails, falls back to 'unknown_service'
OTEL_SERVICE_NAME: str = getenv_otel_service_name() or get_default_service_name() or 'unknown_service'

# enable exporting to tempo for visualization in grafana
OTEL_EXPORTER_OTLP_ENDPOINT: str = os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', '').strip()
