import os
import re
import string
import warnings
from typing import Optional
from typing import Tuple

VALID_HTTP_HEADER_CHARS = ''.join(string.printable.split()) + ' '
REGEX_HTTP_HEADER = re.compile(f'[{re.escape(VALID_HTTP_HEADER_CHARS)}]+')


def getenv_otel_exporter_otlp_endpoint() -> str:
    out = os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', '').strip()
    if '://' not in out:
        warnings.warn(f'missing scheme for `OTEL_EXPORTER_OTLP_ENDPOINT`: "{out}"')
        # out = 'https://' + out  # default to https
    if out.casefold().startswith('http://') and getenv_otel_exporter_otlp_insecure() is False:
        warnings.warn(f'you are requesting for a secure connection to a http service. '
                      f'this is unlikely to succeed: {out}')
    return out


def getenv_otel_exporter_otlp_header() -> Tuple[Tuple[str, str], ...]:
    out = []
    for header in REGEX_HTTP_HEADER.findall(os.getenv('OTEL_EXPORTER_OTLP_HEADER', '')):
        header_name, _, header_value = header.partition('=')
        if _:
            out.append((header_name, header_value))
        else:
            warnings.warn(f'invalid `OTEL_EXPORTER_OTLP_HEADER` key=value pair (missing "=" delimiter): "{header}"')

    # despite having a type signature of Sequence[Tuple[str, str]], opentelemetry does not accept a list of tuples
    # if you try to feed it that, it crashes on startup
    # hence we need to convert it into a tuple instead
    return tuple(out)


def getenv_otel_exporter_otlp_insecure() -> Optional[bool]:
    out = os.getenv('OTEL_EXPORTER_OTLP_INSECURE', '').strip()
    if not out:
        return None
    elif out.casefold() == 'true':
        return True
    elif out.casefold() == 'false':
        return False
    else:
        warnings.warn(f'unexpected value for `OTEL_EXPORTER_OTLP_INSECURE`: {out}')
        return False  # fail secure - random input returns False
