import os
import re
from functools import lru_cache
from typing import List

# todo: don't hardcode this because it's not nice to do that to random people trying out a published library
_DEFAULT_HEADER_ATTRIBUTES = [
    # headers set by the user's browser
    # 'user-agent',
    # 'cookie',

    # headers set by OPA policy
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
    'x-userinfo',
    # 'x-request-id',

    #  headers set by K8s
    # 'x-real-ip',
    # 'x-forwarded-for',
    # 'x-original-forwarded-for',
]

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
