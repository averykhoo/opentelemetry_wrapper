"""
request context from headers (OTW-7, workstream 5; DEC-2, DEC-59, DEC-76)

* request headers (`OTEL_WRAPPER_HEADER_ATTRIBUTES`, default `x-userinfo`) on the server span: a JSON or base64 JSON
  value (Keycloak userinfo, as Kong injects it) is decoded and flattened into `http.request.header.<name>.<claim>`;
  claims matching `OTEL_WRAPPER_HEADER_ATTRIBUTES_EXCLUDE` are dropped before they are recorded (DEC-2). the scrubber
  lets the rest through as-is (`scrubbing.DEFAULT_ALLOW_GLOBS`)
* the raw value is never recorded: a value that looks like base64 but doesn't decode is dropped (the denylist can't
  see into it), and the header is added to upstream's sanitize fields, so `OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_*`
  records `[REDACTED]` for it
* response headers of `requests` calls (`OTEL_WRAPPER_RESPONSE_HEADER_ATTRIBUTES`, default v0's Kong / Envoy list)
  on the client span, as `http.response.header.<name>`

the defaults are in `_env` (`DEFAULT_HEADER_ATTRIBUTES_EXCLUDE`, `DEFAULT_RESPONSE_HEADER_ATTRIBUTES`)

the hooks run on the request path, so they never raise: a failure is reported once per site (DEC-75) and skipped
"""
import base64
import binascii
import fnmatch
import json
import re
from functools import lru_cache
from typing import Any
from typing import Callable
from typing import Dict
from typing import Iterable
from typing import List
from typing import Mapping
from typing import Optional
from typing import Sequence
from typing import Tuple
from typing import Union

from opentelemetry_wrapper.v1._warnings import report

REDACTED = '[REDACTED]'  # what upstream's sanitize fields record

Scalar = Union[bool, str, int, float]
_INT64 = (-(1 << 63), (1 << 63) - 1)
_B64 = re.compile(r'[A-Za-z0-9+/_-]+={0,2}')  # standard or URL-safe alphabet, padded or not
_B64_TOKEN = re.compile(r'[A-Za-z0-9+/_=.-]+')  # base64 segments, possibly dot-separated (a JWT)


# ----------------------------------------------------------------------------------------------------------------------
# decoding
# ----------------------------------------------------------------------------------------------------------------------

def b64decode_any(value: str) -> bytes:
    """standard or URL-safe base64, with or without its padding; the padding is `-len % 4` '=' (v0 appended '=='
    unconditionally, which Python >= 3.11 rejects for 2 lengths in 3)"""
    data = value.rstrip('=')
    data += '=' * (-len(data) % 4)
    if '-' in data or '_' in data:
        return base64.urlsafe_b64decode(data.encode('ascii'))  # validates the alphabet: never mixed with '+' '/'
    return base64.b64decode(data.encode('ascii'), validate=True)


def flatten(value: Any) -> List[Tuple[str, Scalar]]:
    """JSON into (dotted path, scalar) pairs, in document order; nulls dropped, lists as `.[i]` (v0's shape)"""
    out: List[Tuple[str, Scalar]] = []
    stack: List[Tuple[str, Any]] = [('', value)]
    while stack:
        path, node = stack.pop()
        if isinstance(node, dict):
            stack.extend(reversed([(f'{path}.{k}' if path else str(k), v) for k, v in node.items()]))
        elif isinstance(node, list):
            stack.extend(reversed([(f'{path}.[{i}]' if path else f'[{i}]', v) for i, v in enumerate(node)]))
        elif isinstance(node, bool) or isinstance(node, (str, float)):
            out.append((path, node))
        elif isinstance(node, int):  # an attribute is a 64-bit int: a bigger one would fail to export
            out.append((path, node if _INT64[0] <= node <= _INT64[1] else str(node)))
    return out


def _is_container(value: Any) -> bool:
    return isinstance(value, (dict, list))


@lru_cache(maxsize=1024)  # the userinfo of a caller (almost) never changes between its requests
def decode(value: str) -> Optional[Tuple[Tuple[str, Scalar], ...]]:
    """
    a header value as flattened JSON: a JSON object or array, or one base64-encoded (any length, padded or not,
    standard or URL-safe). None when it is neither
    """
    text = value.strip()
    if text[:1] in ('{', '[') and text[-1:] in ('}', ']'):
        try:
            parsed = json.loads(text)
        except ValueError:
            return None
        return tuple(flatten(parsed)) if _is_container(parsed) else None
    if text.startswith('ey') and _B64.fullmatch(text):  # base64 of '{"'
        try:
            parsed = json.loads(b64decode_any(text).decode('utf-8'))
        except (binascii.Error, ValueError):  # UnicodeDecodeError and JSONDecodeError are ValueErrors
            return None
        return tuple(flatten(parsed)) if isinstance(parsed, dict) else None
    return None


def looks_encoded(value: str) -> bool:
    """base64 that may hold claims (`ey...`: base64 of '{"'), a JWT included: never recorded raw"""
    text = value.strip()
    return text.startswith('ey') and _B64_TOKEN.fullmatch(text) is not None


# ----------------------------------------------------------------------------------------------------------------------
# the denylist
# ----------------------------------------------------------------------------------------------------------------------

class Denylist:
    """
    glob patterns against the flattened claim path, case-insensitively; a pattern also denies everything under the
    path it matches (`realm_access.roles` denies `realm_access.roles.[0]`)
    """

    def __init__(self, patterns: Iterable[str]):
        self.patterns = tuple(p.strip() for p in patterns if p.strip())
        regexes = [fnmatch.translate(p.lower()) for p in self.patterns]
        self._re = re.compile('|'.join(regexes)) if regexes else None

    def denies(self, path: str) -> bool:
        if self._re is None:
            return False
        low = path.lower()
        if self._re.match(low):
            return True
        for i, ch in enumerate(low):  # every ancestor: the path up to each '.'
            if ch == '.' and self._re.match(low[:i]):
                return True
        return False


# ----------------------------------------------------------------------------------------------------------------------
# request headers: the server span
# ----------------------------------------------------------------------------------------------------------------------

def header_attributes(name: str, value: Any, denylist: Denylist) -> Dict[str, Scalar]:
    """the attributes one request header gives: its claims (minus the denied ones), the value itself when it is
    plain text, nothing when it looks encoded but doesn't decode"""
    if isinstance(value, bytes):
        value = value.decode('latin-1')
    if not isinstance(value, str) or not value:
        return {}
    prefix = f'http.request.header.{name}'
    claims = decode(value)
    if claims is not None:
        return {f'{prefix}.{path}': v for path, v in claims if path and not denylist.denies(path)}
    if looks_encoded(value):
        return {}
    return {prefix: value}


def _scope_headers(scope: Mapping[str, Any]) -> Dict[str, bytes]:
    """an ASGI scope's headers by lowercase name; the last value wins (as v0's `dict(Headers(scope=scope))`)"""
    out: Dict[str, bytes] = {}
    for key, value in scope.get('headers') or ():
        out[key.decode('latin-1').lower()] = value
    return out


def server_request_hook(names: Sequence[str], exclude: Iterable[str]) -> Callable[..., None]:
    """the FastAPI / ASGI `server_request_hook` (span, scope, ...)"""
    names = tuple(n.lower() for n in names)
    denylist = Denylist(exclude)

    def hook(span: Any, scope: Any, *_: Any) -> None:
        try:
            if not names or span is None or not span.is_recording():
                return
            headers = _scope_headers(scope)
            for name in names:
                if name in headers:
                    attributes = header_attributes(name, headers[name], denylist)
                    if attributes:
                        span.set_attributes(attributes)
        except Exception as e:
            report('server_request_hook (request header attributes)', e)

    hook._opentelemetry_wrapper = True  # type: ignore[attr-defined]
    return hook


def sanitize_fields(names: Sequence[str], environ: Mapping[str, str]) -> List[str]:
    """upstream's sanitize fields (regexes, searched case-insensitively) plus our headers, exactly: header capture
    then records `[REDACTED]` for them, never the raw value (passing the list replaces upstream's reading of the env,
    so the user's own fields are kept)"""
    from opentelemetry.util.http import OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SANITIZE_FIELDS
    raw = environ.get(OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SANITIZE_FIELDS) or ''
    fields = [f.strip() for f in raw.split(',') if f.strip()]
    return fields + [f'^{re.escape(n)}$' for n in names]


# ----------------------------------------------------------------------------------------------------------------------
# requests: the client span
# ----------------------------------------------------------------------------------------------------------------------

def requests_request_hook(names: Sequence[str]) -> Callable[..., None]:
    """
    `requests` reads its sanitize fields from the env only, so a forwarded `x-userinfo` captured by
    `OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_CLIENT_REQUEST` is redacted here, before the span ends, the way the
    sanitize fields would have
    """
    from opentelemetry.util.http import normalise_request_header_name
    keys = tuple(normalise_request_header_name(n) for n in names)

    def hook(span: Any, request: Any) -> None:
        try:
            if not keys or span is None or not span.is_recording():
                return
            attributes = getattr(span, 'attributes', None) or {}
            for key in keys:
                if key in attributes:
                    span.set_attribute(key, [REDACTED])
        except Exception as e:
            report('requests request_hook (sanitize forwarded headers)', e)

    hook._opentelemetry_wrapper = True  # type: ignore[attr-defined]
    return hook


def requests_response_hook(names: Sequence[str]) -> Callable[..., None]:
    """the `requests` `response_hook` (span, request, response): the listed response headers, as v0 recorded them"""
    names = tuple(n.lower() for n in names)

    def hook(span: Any, request: Any, response: Any) -> None:
        try:
            if not names or span is None or not span.is_recording():
                return
            headers = getattr(response, 'headers', None)
            if not headers:
                return
            for name in names:
                value = headers.get(name)  # requests' headers are case-insensitive
                if isinstance(value, str):
                    span.set_attribute(f'http.response.header.{name}', value)
        except Exception as e:
            report('requests response_hook (response header attributes)', e)

    hook._opentelemetry_wrapper = True  # type: ignore[attr-defined]
    return hook
