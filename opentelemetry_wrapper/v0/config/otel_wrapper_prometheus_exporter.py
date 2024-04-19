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
        warnings.warn(f'`OTEL_EXPORTER_PROMETHEUS_PORT` is non-numeric, '
                      f'and will be ignored: {out} (i.e. prometheus metric endpoint will not be available)')
        return None

    if int(out) < 1024:
        warnings.warn(f'`OTEL_EXPORTER_PROMETHEUS_PORT` is smaller than expected: {out}')

    return int(out)


def get_prometheus_endpoint() -> Optional[str]:
    """
    allowed:
    * /metrics
    * /metrics/
    * /metrics////
    * /metrics/prometheus
    * ////metrics////prometheus////

    not allowed:
    * /
    * ////
    * anything where the segments don't match `[a-z0-9_-]+`
    """
    out = os.getenv('OTEL_EXPORTER_PROMETHEUS_ENDPOINT', '/metrics').strip()

    if not out:
        return None

    if not out.rstrip('/'):
        warnings.warn(f'`OTEL_EXPORTER_PROMETHEUS_ENDPOINT={out}` is root, '
                      f'and will be ignored (i.e. prometheus metric endpoint will not be available)')
        return None

    if len(out.split()) > 1:
        warnings.warn(f'`OTEL_EXPORTER_PROMETHEUS_ENDPOINT={out}` contains whitespace, '
                      f'and will be ignored (i.e. prometheus metric endpoint will not be available)')
        return None

    if not set(out).issubset(string.printable):
        warnings.warn(f'`OTEL_EXPORTER_PROMETHEUS_ENDPOINT={out}` contains non-ASCII, '
                      f'and will be ignored (i.e. prometheus metric endpoint will not be available)')
        return None

    # fix '//'
    _out = re.sub(r'/+', r'/', out)
    if out != _out:
        warnings.warn(f'`OTEL_EXPORTER_PROMETHEUS_ENDPOINT={out}` contains "//", '
                      f'and will be changed to "{_out}"')
        out = _out

    # make it start with '/'
    if not out.startswith('/'):
        warnings.warn(f'`OTEL_EXPORTER_PROMETHEUS_ENDPOINT={out}` does not start with "/", '
                      f'and will be changed to "/{out}"')
        out = '/' + out

    # validate with a strict regex to catch everything else
    if not re.fullmatch(r'(/[a-zA-Z0-9_-]+)+/?', out):
        warnings.warn(f'`OTEL_EXPORTER_PROMETHEUS_ENDPOINT={out}` is not `[a-z0-9_-]`, '
                      f'and will be ignored (i.e. prometheus metric endpoint will not be available)')
        return None

    return out
