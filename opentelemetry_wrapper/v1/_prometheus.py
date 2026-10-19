"""
Prometheus scrape (workstream 9): the standalone server and the FastAPI route, both serving `prometheus_client`'s
global registry, where our `PrometheusMetricReader` (built at configure time, `_config`) registers itself

* the server binds `OTEL_EXPORTER_PROMETHEUS_HOST` (default `localhost`; `0.0.0.0` in Kubernetes, where Prometheus
  scrapes the pod IP), on `OTEL_EXPORTER_PROMETHEUS_PORT`, and serves metrics on every path, like
  `prometheus_client.start_http_server`. it is built from public pieces rather than by `start_http_server`, which sets
  `SO_REUSEADDR`: on Windows that lets a second worker bind a port the first one holds, silently, so scrapes reach
  either. here the second worker fails to bind on every platform, and the caller warns once
* the route is `app.add_route(path, ...)`, never `app.mount`: a mount serves everything under `path/` and redirects
  `path` there, which an exact-path exclusion from request spans would miss
* several workers per container each have their own metrics; only one binds the port, and the route answers from
  whichever worker took the request. in multi-worker deployments use OTLP push, or one worker per container
"""
import os
import re
import socket
import threading
from socketserver import ThreadingMixIn
from typing import Any
from typing import Tuple
from urllib.parse import parse_qs
from wsgiref.simple_server import WSGIRequestHandler
from wsgiref.simple_server import WSGIServer


class _QuietHandler(WSGIRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - the base class's name
        pass  # wsgiref logs every request to stderr, which must stay one JSON line per record


def _address_family(host: str, port: int) -> Tuple[int, str]:
    """the family and address to bind for a host name or address (IPv6 hosts included)"""
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM, flags=socket.AI_PASSIVE)
    family, _, _, _, sockaddr = infos[0]
    return family, sockaddr[0]


def start_server(host: str, port: int) -> Any:
    """serve `prometheus_client`'s global registry on `host:port` from a daemon thread; raises `OSError` when the
    address can't be bound (another worker holds it)"""
    from prometheus_client import REGISTRY
    from prometheus_client import make_wsgi_app

    family, address = _address_family(host, port)

    class Server(ThreadingMixIn, WSGIServer):
        address_family = family
        daemon_threads = True
        allow_reuse_address = os.name != 'nt'  # posix: restart over TIME_WAIT; never steals a listening port

        def server_bind(self) -> None:
            if os.name == 'nt' and hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):  # nor can anyone steal ours
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            super().server_bind()

    server = Server((address, port), _QuietHandler)
    server.set_app(make_wsgi_app(REGISTRY))
    thread = threading.Thread(target=server.serve_forever, name='otel-wrapper-prometheus', daemon=True)
    thread.start()
    return server


def excluded_url(path: str) -> str:
    """a regex for upstream's `excluded_urls` that matches the request url of exactly this path: upstream searches
    `scheme://host` + the scope's path, so `/api/metrics` and `/metricsfoo` still get request spans. (an app served
    under a `root_path` has it in the scope's path too: `untraced_under_root_path` handles that)"""
    return f'^[^:/]+://[^/]*{re.escape(path)}$'


def endpoint(request: Any) -> Any:
    """the route: the registry's exposition in the format the scraper accepts (`name[]` restricts it, like
    `prometheus_client`'s own app). sync, so Starlette runs it in a worker thread, off the event loop"""
    from prometheus_client import REGISTRY
    from prometheus_client.exposition import choose_encoder
    from starlette.responses import Response
    encoder, content_type = choose_encoder(','.join(request.headers.getlist('accept')))
    names = parse_qs(request.url.query).get('name[]')
    registry = REGISTRY.restricted_registry(names) if names else REGISTRY
    return Response(content=encoder(registry), headers={'Content-Type': content_type})


def has_route(app: Any, path: str) -> bool:
    return any(getattr(route, 'path', None) == path for route in getattr(app, 'routes', ()))


def place_route(app: Any, path: str) -> None:
    """the scrape route, unless the app has its own at exactly that path; first among the routes, so a catch-all
    such as a single-page app's `/{full_path:path}` can't answer the scrape instead (Starlette takes the first)"""
    from starlette.routing import Route
    if not has_route(app, path):
        app.router.routes.insert(0, Route(path, endpoint=endpoint, include_in_schema=False))


class untraced_under_root_path:  # noqa: N801 - a middleware, named for what it does
    """the outermost ASGI layer: a scrape of `root_path` + `path` (uvicorn `--root-path`, `FastAPI(root_path=...)`)
    reaches the stack with `path` alone, which upstream's exact-path exclusion matches, so it makes no request span
    either; Starlette's routing still finds the route (a path outside the root path is routed as it is). the wrapped
    stack is `.app`, as in every Starlette middleware: FastAPI walks that chain to find upstream's middleware, and
    without it adds its own request spans too"""

    def __init__(self, app: Any, path: str) -> None:
        self.app = app
        self.path = path

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        root_path = (scope.get('root_path') or '').rstrip('/')
        if root_path and scope.get('type') == 'http' and scope.get('path') == root_path + self.path:
            scope = dict(scope, path=self.path)
        await self.app(scope, receive, send)
