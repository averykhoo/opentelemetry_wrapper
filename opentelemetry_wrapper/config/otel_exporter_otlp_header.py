import os
import re
import string
import warnings
from typing import Tuple

VALID_HTTP_HEADER_CHARS = ''.join(string.printable.split()) + ' '
REGEX_HTTP_HEADER = re.compile(f'[{re.escape(VALID_HTTP_HEADER_CHARS)}]+')


def getenv_otel_exporter_otlp_header() -> Tuple[Tuple[str, str], ...]:
    out = []
    for header in REGEX_HTTP_HEADER.findall(os.getenv('OTEL_EXPORTER_OTLP_HEADER', '')):
        header_name, _, header_value = header.partition('=')
        if _:
            out.append((header_name, header_value))
        else:
            warnings.warn(f'invalid OTEL_EXPORTER_OTLP_HEADER key=value pair (missing "=" delimiter): "{header}"')
    return tuple(out)
