from typing import Any
from typing import Union

from opentelemetry_wrapper.config.otel_headers import OTEL_EXPORTER_PROMETHEUS_ENDPOINT

try:
    from fastapi import FastAPI
    from fastapi.responses import RedirectResponse
    from fastapi.routing import APIRouter
    from prometheus_client import make_asgi_app


    def mount_prometheus(app: Any):
        """
        currently relies on a redirect hack because of starlette requiring a trailing slash
        TODO: port `make_asgi_app` into a native fastapi route
        """
        if not OTEL_EXPORTER_PROMETHEUS_ENDPOINT:
            return

        if isinstance(app, FastAPI):
            _router: Union[APIRouter, None] = getattr(app, 'router', None)
            if not isinstance(_router, APIRouter):
                return
            if any(route.path == OTEL_EXPORTER_PROMETHEUS_ENDPOINT for route in _router.routes):
                return

            async def redirect_metrics():
                """
                Explicitly redirect `/metrics` to `/metrics/`
                Without this, the redirect changes the base url, which breaks when using a forward proxy
                """
                return RedirectResponse(f'{OTEL_EXPORTER_PROMETHEUS_ENDPOINT}/')

            app.get(OTEL_EXPORTER_PROMETHEUS_ENDPOINT, include_in_schema=False)(redirect_metrics)
            app.mount(OTEL_EXPORTER_PROMETHEUS_ENDPOINT, make_asgi_app())

except ImportError:
    def mount_prometheus(_):
        return
