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
    >>> os.environ['OTEL_EXPORTER_OTLP_ENDPOINT'] = 'https://otel-collector.domain/some-endpoint'
    >>> getenv_otel_exporter_otlp_endpoint()
    'https://otel-collector.domain/some-endpoint'
    >>> os.environ['OTEL_EXPORTER_OTLP_ENDPOINT'] = 'otel-collector/some-endpoint'  # could be pod-local
    >>> getenv_otel_exporter_otlp_endpoint()
    'otel-collector/some-endpoint'
    >>> os.environ['OTEL_EXPORTER_OTLP_ENDPOINT'] = '/otel-collector'  # maybe it's a file? should i raise an error?
    >>> getenv_otel_exporter_otlp_endpoint()
    '/otel-collector'

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
    """
    >>> os.environ['OTEL_EXPORTER_OTLP_HEADER'] = 'some-header=some-value'
    >>> getenv_otel_exporter_otlp_header()
    (('some-header', 'some-value'),)
    >>> os.environ['OTEL_EXPORTER_OTLP_HEADER'] = 'a=b\\tc=d'
    >>> getenv_otel_exporter_otlp_header()
    (('a', 'b'), ('c', 'd'))
    >>> os.environ['OTEL_EXPORTER_OTLP_HEADER_SEPARATOR'] = ';'
    >>> os.environ['OTEL_EXPORTER_OTLP_HEADER'] = 'a=1;b=2;c=3'
    >>> getenv_otel_exporter_otlp_header()
    (('a', '1'), ('b', '2'), ('c', '3'))

    :return:
    """
    out = []
    seen = set()
    header_separator = os.getenv('OTEL_EXPORTER_OTLP_HEADER_SEPARATOR', '\t')
    split_headers = os.getenv('OTEL_EXPORTER_OTLP_HEADER', '').split(header_separator)
    for header in split_headers:
        header_name, _, header_value = header.partition('=')
        if not _:
            _header = f'"{header[:5]}..."' if len(header) > 8 else f'"{header}"'  # truncate long header pairs
            warnings.warn(f'invalid `OTEL_EXPORTER_OTLP_HEADER` key=value pair (missing "=" delimiter): {_header}')
        elif REGEX_HTTP_HEADER_NAME.fullmatch(header_name) is None:
            warnings.warn(f'invalid `OTEL_EXPORTER_OTLP_HEADER` header name: {header_name}')  # value may be sensitive
        elif REGEX_HTTP_HEADER.fullmatch(header_value) is None:
            warnings.warn(f'invalid `OTEL_EXPORTER_OTLP_HEADER` value for header_name: {header}')
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

    >>> getenv_otel_exporter_otlp_insecure() # returns None

    >>> os.environ['OTEL_EXPORTER_OTLP_INSECURE'] = 'invalid' # prints a warning
    >>> getenv_otel_exporter_otlp_insecure()
    False
    >>> os.environ['OTEL_EXPORTER_OTLP_INSECURE'] = 'false'
    >>> getenv_otel_exporter_otlp_insecure()
    False
    >>> os.environ['OTEL_EXPORTER_OTLP_INSECURE'] = 'true'
    >>> getenv_otel_exporter_otlp_insecure()
    True
    >>> os.environ['OTEL_EXPORTER_OTLP_INSECURE'] = 'TRUE'
    >>> getenv_otel_exporter_otlp_insecure()
    True
    >>> os.environ['OTEL_EXPORTER_OTLP_INSECURE'] = 'tRuE'
    >>> getenv_otel_exporter_otlp_insecure()
    True

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
