from typing import Any
from typing import Union
from urllib.parse import parse_qs

from opentelemetry_wrapper.v0.config.otel_headers import OTEL_EXPORTER_PROMETHEUS_ENDPOINT

try:
    from fastapi import FastAPI
    from fastapi import Request
    from fastapi import Response
    from fastapi.responses import RedirectResponse
    from fastapi.routing import APIRouter
    from prometheus_client import CollectorRegistry
    from prometheus_client import make_asgi_app
    from prometheus_client import REGISTRY
    from prometheus_client.exposition import _bake_output


    def mount_prometheus(app: Any):
        """
        if OTEL_EXPORTER_PROMETHEUS_ENDPOINT ends with '/', it will mount the prometheus app
        otherwise, it creates a custom FastAPI endpoint that returns the same thing as the prometheus app
        """
        if not OTEL_EXPORTER_PROMETHEUS_ENDPOINT:
            return

        if isinstance(app, FastAPI):
            _router: Union[APIRouter, None] = getattr(app, 'router', None)
            if not isinstance(_router, APIRouter):
                return
            if any(route.path == OTEL_EXPORTER_PROMETHEUS_ENDPOINT for route in _router.routes):
                return

            # if you submit
            if OTEL_EXPORTER_PROMETHEUS_ENDPOINT.endswith('/'):
                async def redirect_metrics():
                    """
                    Explicitly redirect (for example) `/metrics` to `/metrics/`
                    Without this, the 307 redirect changes the base url, which breaks when using a forward proxy
                    """
                    return RedirectResponse(OTEL_EXPORTER_PROMETHEUS_ENDPOINT)

                app.get(OTEL_EXPORTER_PROMETHEUS_ENDPOINT.rstrip('/'), include_in_schema=False)(redirect_metrics)
                app.mount(OTEL_EXPORTER_PROMETHEUS_ENDPOINT.rstrip('/'), make_asgi_app())

            else:
                def prometheus_metrics_endpoint(request: Request):
                    _, headers, output = _bake_output(registry=REGISTRY,
                                                      accept_header=','.join(request.headers.getlist('accept')),
                                                      accept_encoding_header='',  # don't support gzip
                                                      params=parse_qs(request.scope.get('query_string', b'')),
                                                      disable_compression=True)

                    # Return output
                    return Response(content=output,
                                    headers=dict(headers))

                app.get(OTEL_EXPORTER_PROMETHEUS_ENDPOINT, include_in_schema=False)(prometheus_metrics_endpoint)

except ImportError:
    def mount_prometheus(_):
        return
