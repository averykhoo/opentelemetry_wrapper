import os
import re
from functools import lru_cache
from typing import List

_DEFAULT_HEADER_ATTRIBUTES = [
    # 'user-agent',
    # 'cookie',

    # headers set in cookiecutter's OPA file
    'x-pf-number',
    'x-client-id',
    'x-preferred-username',
    # 'x-full-name',
    # 'x-given-name',
    # 'x-family-name',
    'x-resource-access',
    # 'x-realm-roles',
    # 'x-groups',

    # headers set by Kong
    # 'authorization',
    # 'x-userinfo',
    # 'x-request-id',

    #  headers set by K8s
    # 'x-real-ip',
    # 'x-forwarded-for',
    # 'x-original-forwarded-for',
]

REGEX_HEADER = re.compile(r'[a-z0-9_-]+', flags=re.I)


@lru_cache
def get_header_attributes() -> List[str]:
    out = set()
    if os.getenv('OTEL_HEADER_ATTRIBUTES') is None:
        headers = _DEFAULT_HEADER_ATTRIBUTES
    else:
        headers = REGEX_HEADER.findall(os.getenv('OTEL_HEADER_ATTRIBUTES').strip())

    for header in headers:
        out.add(header.lower())

    return sorted(out)
