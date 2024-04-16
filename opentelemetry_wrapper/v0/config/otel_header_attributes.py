import os
import re
from functools import lru_cache
from typing import List

_DEFAULT_HEADER_ATTRIBUTES = ['x-userinfo']

# https://developers.cloudflare.com/rules/transform/request-header-modification/reference/header-format/
REGEX_HEADER = re.compile(r'[a-z0-9_-]+', flags=re.I)


@lru_cache
def get_header_attributes() -> List[str]:
    out = set()
    if os.getenv('OTEL_HEADER_ATTRIBUTES') is None:
        headers = _DEFAULT_HEADER_ATTRIBUTES
    else:
        headers = REGEX_HEADER.findall(os.getenv('OTEL_HEADER_ATTRIBUTES', '').strip())

    for header in headers:
        out.add(header.lower())

    return sorted(out)
