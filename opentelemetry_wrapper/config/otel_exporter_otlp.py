import os
import re
import string
import warnings
from typing import Optional
from typing import Tuple
from urllib.parse import urlparse

# https://developers.cloudflare.com/rules/transform/request-header-modification/reference/header-format/
VALID_HTTP_HEADER_CHARS = ''.join(string.printable.split()) + ' '
REGEX_HTTP_HEADER = re.compile(f'[{re.escape(VALID_HTTP_HEADER_CHARS)}]+')
VALID_HTTP_HEADER_NAME_CHARS = string.digits + string.ascii_letters + '-_'
REGEX_HTTP_HEADER_NAME = re.compile(f'[{re.escape(VALID_HTTP_HEADER_NAME_CHARS)}]+')


def getenv_otel_exporter_otlp_endpoint() -> str:
    """
    get oltp endpoint env var, or an empty string otherwise
    :return: url or empty string
    """
    out = os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', '').strip()

    # no endpoint specified
    if not out:
        return ''

    parsed_url = urlparse(out)

    # check that the url has a scheme
    if not parsed_url.scheme:
        warnings.warn(f'missing scheme for `OTEL_EXPORTER_OTLP_ENDPOINT`: "{out}"')
        parsed_url = urlparse(f'scheme://{out}')

    # check that the url has a domain
    if not parsed_url.hostname:
        warnings.warn(f'missing host for `OTEL_EXPORTER_OTLP_ENDPOINT`: "{out}"')

    # validate the port
    try:
        _ = parsed_url.port
    except ValueError:
        warnings.warn(f'invalid port for `OTEL_EXPORTER_OTLP_ENDPOINT`: "{out}"')

    # check that security config is valid for http
    if parsed_url.scheme.casefold() == 'http' and getenv_otel_exporter_otlp_insecure() is False:
        warnings.warn(f'secure connection to `OTEL_EXPORTER_OTLP_ENDPOINT` likely impossible: {out}')
    return out


def getenv_otel_exporter_otlp_header() -> Tuple[Tuple[str, str], ...]:
    out = []
    seen = set()
    for header in REGEX_HTTP_HEADER.findall(os.getenv('OTEL_EXPORTER_OTLP_HEADER', '')):
        header_name, _, header_value = header.partition('=')
        if not _:
            _header = f'"{header[:5]}..."' if len(header) > 8 else f'"{header}"'  # truncate long header pairs
            warnings.warn(f'invalid `OTEL_EXPORTER_OTLP_HEADER` key=value pair (missing "=" delimiter): {_header}')
        elif REGEX_HTTP_HEADER_NAME.fullmatch(header_name) is None:
            warnings.warn(f'invalid `OTEL_EXPORTER_OTLP_HEADER` header name: {header_name}')  # value may be sensitive
        else:
            out.append((header_name, header_value))

            # check for duplicates, case insensitive pure ascii
            if header_name.lower() in seen:
                warnings.warn(f'duplicate `OTEL_EXPORTER_OTLP_HEADER` header name {header_name}')
            seen.add(header_name.lower())

    # despite having a type signature of Sequence[Tuple[str, str]], opentelemetry does not accept a list of tuples
    # if you try to feed it that, it crashes on startup
    # hence we need to convert it into a tuple of tuples instead
    return tuple(out)


def getenv_otel_exporter_otlp_insecure() -> Optional[bool]:
    """
    check if OTEL_EXPORTER_OTLP_INSECURE=True
    defaults to secure (i.e. `False`) if invalid
    returns None if unset, since that's falsy

    :return: True if insecure; False if secure; None if unset
    """
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
