import os
import re
import string
import warnings
from typing import Optional


def get_prometheus_port() -> Optional[int]:
    out = os.getenv('OTEL_EXPORTER_PROMETHEUS_PORT', '').strip()

    if not out:
        return None

    if not out.isdigit():
        warnings.warn(f'`OTEL_EXPORTER_PROMETHEUS_PORT` is non-numeric, and will be ignored: {out!r}')
        return None

    if int(out) < 1024:
        warnings.warn(f'`OTEL_EXPORTER_PROMETHEUS_PORT` is smaller than expected: {out}')

    return int(out)


def get_prometheus_endpoint() -> Optional[str]:
    out = os.getenv('OTEL_EXPORTER_PROMETHEUS_ENDPOINT', '').strip()

    if not out:
        return None

    if not out.startswith('/'):
        warnings.warn(f'`OTEL_EXPORTER_PROMETHEUS_ENDPOINT` does not start with "/", and will be ignored: {out!r}')
        return None

    out = out.rstrip('/')

    if not out:
        warnings.warn(f'`OTEL_EXPORTER_PROMETHEUS_ENDPOINT` is "/" (i.e. root), and will be ignored: {out!r}')
        return None

    if '//' in out:
        warnings.warn(f'`OTEL_EXPORTER_PROMETHEUS_ENDPOINT` contains "//", and will be ignored: {out!r}')
        return None

    if len(out.split()) > 1:
        warnings.warn(f'`OTEL_EXPORTER_PROMETHEUS_ENDPOINT` contains whitespace, and will be ignored: {out!r}')
        return None

    if not set(out).issubset(string.printable):
        warnings.warn(f'`OTEL_EXPORTER_PROMETHEUS_ENDPOINT` contains non-ASCII, and will be ignored: {out!r}')
        return None

    if not re.fullmatch(r'(/[a-zA-Z0-9_-]+)+', out):
        warnings.warn(f'`OTEL_EXPORTER_PROMETHEUS_ENDPOINT` contains punctuation, and will be ignored: {out!r}')
        return None

    return out
