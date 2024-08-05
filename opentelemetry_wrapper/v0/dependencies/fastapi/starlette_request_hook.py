import logging

from opentelemetry.trace import Span

from opentelemetry_wrapper.v0.config.otel_headers import OTEL_HEADER_ATTRIBUTES
from opentelemetry_wrapper.v0.utils.extract_json_header import extract_json_header

try:
    from starlette.datastructures import Headers
    from starlette.types import Scope


    def request_hook(span: Span, scope: Scope, *_) -> None:
        """
        add span attributes from headers based on requests we're getting from users
        following the convention from: https://opentelemetry.io/docs/specs/semconv/attributes-registry/http/
        note: RFC 7230 says header keys and values should be ASCII

        the *_ exists to catch `message`, which is an (undocumented!) argument starting in otel-sdk 1.26
        message type: starlette.types.Message
        (before v1.26, otel-sdk called it with only span and scope)
        """
        headers = dict(Headers(scope=scope))  # keys are lowercase latin-1 (ascii)
        for header_name in OTEL_HEADER_ATTRIBUTES:
            header_value = headers.get(header_name.lower())

            # special case: handle the userinfo header (and other similar json headers)
            _header_data = extract_json_header(header_value)
            if _header_data:
                for k, v in _header_data.items():
                    span.set_attribute(f'http.request.header.{header_name}.{k}', v)
                continue

            # all other headers
            if isinstance(header_value, (bool, str, bytes, int, float)):
                span.set_attribute(f'http.request.header.{header_name}', header_value)
except ImportError:
    def request_hook(*_, **__) -> None:
        return
