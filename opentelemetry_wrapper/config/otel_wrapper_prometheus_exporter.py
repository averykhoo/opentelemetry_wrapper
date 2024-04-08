import os
import warnings
from typing import Optional


def get_prometheus_port() -> Optional[int]:
    out = os.getenv('OTEL_EXPORTER_PROMETHEUS_PORT', '').strip()

    if not out.isdigit():
        warnings.warn(f'`OTEL_EXPORTER_PROMETHEUS_PORT` is non-numeric, and will be ignored: {out!r}')
        return None

    if int(out) < 1024:
        warnings.warn(f'`OTEL_EXPORTER_PROMETHEUS_PORT` is smaller than expected: {out}')

    return int(out)
