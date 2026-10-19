"""
`instrument_fastapi_app`: request spans, `x-userinfo` flattening (request hook + extract_json_header), `/metrics`

httpx (and so FastAPI's TestClient) is not installed, so apps are driven with a hand-built ASGI scope
(`_harness.asgi_request`). apps are instrumented per object, so this is safe in-process; env-dependent behaviour
(the prometheus path is read at import time) runs in fresh interpreters
"""
import base64
import json

import pytest

from tests import impl
from tests.v0._harness import REPO_ROOT
from tests.v0._harness import asgi_request
from tests.v0._harness import scenario

fastapi = pytest.importorskip('fastapi')
IMPL_IS_V0 = impl.IMPL == 'v0'


def make_app():
    app = fastapi.FastAPI()

    @app.get('/hello')
    def hello():
        return 'hi'

    @app.get('/items/{item_id}')
    def item(item_id: int):
        return {'item_id': item_id}

    @app.get('/api/metrics')
    def api_metrics():
        return 'not prometheus'

    @app.get('/metricsfoo')
    def metricsfoo():
        return 'not prometheus either'

    @app.get('/fail')
    def fail():
        raise RuntimeError('handler failed')

    return app


def server_spans(records):
    return [r for r in records if r['kind'] == 'SERVER']


# ----------------------------------------------------------------------------------------------------------------------
# spans and idempotency
# ----------------------------------------------------------------------------------------------------------------------

def test_instrumenting_returns_the_same_app(otw, spans):
    app = make_app()
    assert otw.instrument_app(app) is app


def test_request_spans(otw, spans):
    app = otw.instrument_app(make_app())
    spans.clear()
    response = asgi_request(app, '/hello')
    assert response.status == 200
    assert response.text == '"hi"'

    records = spans.records()
    assert sorted(r['name'] for r in records) == ['GET /hello', 'GET /hello http send', 'GET /hello http send']
    (server,) = server_spans(records)
    assert server['parent'] is None
    assert server['attributes']['http.route'] == '/hello'
    assert server['attributes']['http.status_code'] == 200
    assert all(r['parent'] == 'GET /hello' for r in records if r is not server)


def test_span_name_uses_the_route_template(otw, spans):
    app = otw.instrument_app(make_app())
    spans.clear()
    assert asgi_request(app, '/items/42').status == 200
    (server,) = server_spans(spans.records())
    assert server['name'] == 'GET /items/{item_id}'
    assert server['attributes']['http.target'] == '/items/42'


def test_instrumenting_twice_does_not_duplicate_spans_or_raise(otw, spans):
    app = make_app()
    assert otw.instrument_app(app) is app
    assert otw.instrument_app(app) is app
    spans.clear()
    assert asgi_request(app, '/hello').status == 200
    assert sorted(spans.names()) == ['GET /hello', 'GET /hello http send', 'GET /hello http send']


def test_handler_exception_marks_server_span_as_error(otw, spans):
    app = otw.instrument_app(make_app())
    spans.clear()
    with pytest.raises(RuntimeError, match='handler failed'):  # no ServerErrorMiddleware response without a server
        asgi_request(app, '/fail')
    (server,) = server_spans(spans.records())
    assert server['status'] == 'ERROR'


def test_non_fastapi_objects_are_returned_unchanged(otw):
    from starlette.applications import Starlette
    starlette_app = Starlette()
    assert otw.instrument_app(starlette_app) is starlette_app
    assert otw.instrument_app('not an app') == 'not an app'
    assert otw.instrument_app(None) is None


@pytest.mark.v0_specific
def test_instrumenting_emits_a_span_for_the_instrument_call_itself(otw, spans):
    otw.instrument_app(make_app())
    assert spans.names(include_library_spans=True) == [
        '<opentelemetry_wrapper.v0.dependencies.opentelemetry.instrument_fastapi>.instrument_fastapi_app']


# ----------------------------------------------------------------------------------------------------------------------
# headers (default OTEL_HEADER_ATTRIBUTES = x-userinfo)
# ----------------------------------------------------------------------------------------------------------------------

USERINFO = {  # Keycloak-style userinfo, as injected by Kong; json length chosen so v0 can decode it (see below)
    'sub': 'f1b2c3', 'email': 'a@example.com', 'email_verified': True, 'preferred_username': 'ann',
    'realm_access': {'roles': ['admin', 'user']}, 'auth_time': 1700000000, 'session_state': None,
}


def userinfo_header(obj) -> str:
    """base64 without padding, like Kong; padded with a dummy field to a length v0 decodes (python >= 3.11 bug)"""
    obj = dict(obj, pad='')
    while len(json.dumps(obj).encode()) % 3 != 1:
        obj['pad'] += 'x'
    return base64.b64encode(json.dumps(obj).encode()).decode().rstrip('=')


def header_attributes(record):
    return {k: v for k, v in record['attributes'].items() if k.startswith('http.request.header')}


@pytest.fixture
def app(otw):
    return otw.instrument_app(make_app())


def test_base64_userinfo_is_flattened_onto_the_server_span(app, spans):
    spans.clear()
    assert asgi_request(app, '/hello', headers=[('x-userinfo', userinfo_header(USERINFO))]).status == 200
    records = spans.records()
    (server,) = server_spans(records)
    attributes = header_attributes(server)
    attributes.pop('http.request.header.x-userinfo.pad')
    assert attributes == {
        'http.request.header.x-userinfo.sub':                    'f1b2c3',
        'http.request.header.x-userinfo.email':                  'a@example.com',
        'http.request.header.x-userinfo.email_verified':         True,
        'http.request.header.x-userinfo.preferred_username':     'ann',
        'http.request.header.x-userinfo.realm_access.roles.[0]': 'admin',
        'http.request.header.x-userinfo.realm_access.roles.[1]': 'user',
        'http.request.header.x-userinfo.auth_time':              1700000000,
    }
    # only the server span gets them
    assert all(not header_attributes(r) for r in records if r is not server)


@pytest.mark.xfail(IMPL_IS_V0, strict=True,
                   reason='found by this suite (v0 bug list, 2nd section): base64 userinfo whose json length is not 1 '
                          'mod 3 is not decoded on python >= 3.11 (see test_v0_extract_json_header.py), so it is '
                          'recorded raw instead of flattened; v1 decodes it (OTW-7)')
def test_base64_userinfo_of_another_length_is_flattened(app, spans):
    obj = dict(USERINFO, pad='')
    while len(json.dumps(obj).encode()) % 3 != 2:
        obj['pad'] += 'x'
    header = base64.b64encode(json.dumps(obj).encode()).decode().rstrip('=')
    spans.clear()
    asgi_request(app, '/hello', headers=[('x-userinfo', header)])
    (server,) = server_spans(spans.records())
    assert header_attributes(server).get('http.request.header.x-userinfo.sub') == 'f1b2c3'


def test_plain_json_userinfo_is_flattened(app, spans):
    spans.clear()
    asgi_request(app, '/hello', headers=[('x-userinfo', '{"a": {"b": 1}, "c": [true, 2.5]}')])
    (server,) = server_spans(spans.records())
    assert header_attributes(server) == {'http.request.header.x-userinfo.a.b':   1,
                                         'http.request.header.x-userinfo.c.[0]': True,
                                         'http.request.header.x-userinfo.c.[1]': 2.5}


def test_undecodable_userinfo_is_recorded_raw(app, spans):
    spans.clear()
    asgi_request(app, '/hello', headers=[('x-userinfo', 'just text')])
    (server,) = server_spans(spans.records())
    assert header_attributes(server) == {'http.request.header.x-userinfo': 'just text'}


@pytest.mark.v0_specific  # v1 never records a value that looks encoded but doesn't decode (AC-33, OTW-7)
def test_jwt_userinfo_is_recorded_raw(app, spans):
    jwt = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.signature'
    spans.clear()
    asgi_request(app, '/hello', headers=[('x-userinfo', jwt)])
    (server,) = server_spans(spans.records())
    assert header_attributes(server) == {'http.request.header.x-userinfo': jwt}


def test_other_headers_are_not_captured_by_default(app, spans):
    spans.clear()
    asgi_request(app, '/hello', headers=[('x-other', '{"a": 1}'), ('authorization', 'Bearer secret')])
    (server,) = server_spans(spans.records())
    assert header_attributes(server) == {}


def test_no_header_no_attributes(app, spans):
    spans.clear()
    asgi_request(app, '/hello')
    (server,) = server_spans(spans.records())
    assert header_attributes(server) == {}


# ----------------------------------------------------------------------------------------------------------------------
# prometheus /metrics (default OTEL_EXPORTER_PROMETHEUS_ENDPOINT=/metrics)
# ----------------------------------------------------------------------------------------------------------------------

def test_metrics_route_serves_prometheus_text_including_http_server_metrics(app, spans):
    assert asgi_request(app, '/hello').status == 200  # so there is at least one http_server data point
    response = asgi_request(app, '/metrics')
    assert response.status == 200
    assert response.headers['content-type'].startswith('text/plain')
    assert '# TYPE http_server_duration_milliseconds histogram' in response.text
    assert 'http_server_active_requests' in response.text


def test_metrics_route_is_not_traced(app, spans):
    spans.clear()
    assert asgi_request(app, '/metrics').status == 200
    assert spans.names() == []


def test_metrics_route_is_added_once_even_when_instrumented_twice(otw):
    app = make_app()
    otw.instrument_app(app)
    otw.instrument_app(app)
    assert [route.path for route in app.router.routes].count('/metrics') == 1


def test_existing_metrics_route_is_not_replaced(otw):
    app = fastapi.FastAPI()

    @app.get('/metrics')
    def custom():
        return 'custom'

    otw.instrument_app(app)
    assert [route.path for route in app.router.routes].count('/metrics') == 1
    assert asgi_request(app, '/metrics').text == '"custom"'


@pytest.mark.v0_specific  # v1 excludes the exact path only (v0 lessons, AC-19), so /api/metrics gets a span
def test_metrics_exclusion_also_hides_other_routes_containing_slash_metrics(app, spans):
    # excluded_urls='/metrics' is a regex *search* over the full url, so these unrelated routes get no spans either
    spans.clear()
    assert asgi_request(app, '/api/metrics').text == '"not prometheus"'
    assert asgi_request(app, '/metricsfoo').text == '"not prometheus either"'
    assert spans.names() == []


# ----------------------------------------------------------------------------------------------------------------------
# env-dependent variants and fastapi_main.py, in fresh interpreters
# ----------------------------------------------------------------------------------------------------------------------

_ENDPOINT_SCRIPT = r'''
from fastapi import FastAPI
from tests.impl import instrument_app
from tests.v0._harness import asgi_request
exp = setup_spans()
app = FastAPI()

@app.get('/hello')
def hello():
    return 'hi'

instrument_app(app)
emit('routes', [route.path for route in app.router.routes])
for path in ('/metrics', '/metrics/', '/hello'):
    response = asgi_request(app, path)
    emit(path, {'status': response.status, 'location': response.headers.get('location'),
                'is_prometheus': '# HELP' in response.text})
take(exp)
'''

ENDPOINT_TRAILING_SLASH = scenario(__name__, 'fastapi_metrics_trailing_slash', _ENDPOINT_SCRIPT,
                                   env={'OTEL_EXPORTER_PROMETHEUS_ENDPOINT': '/metrics/'})
ENDPOINT_CUSTOM = scenario(__name__, 'fastapi_metrics_custom', _ENDPOINT_SCRIPT.replace("'/metrics', '/metrics/'",
                                                                                        "'/prom/scrape', '/metrics'"),
                           env={'OTEL_EXPORTER_PROMETHEUS_ENDPOINT': 'prom//scrape'})
ENDPOINT_DISABLED = scenario(__name__, 'fastapi_metrics_disabled', _ENDPOINT_SCRIPT,
                             env={'OTEL_EXPORTER_PROMETHEUS_ENDPOINT': ''})

FASTAPI_MAIN = scenario(__name__, 'fastapi_main_example', r'''
import fastapi_main  # the example app; importing it does not start uvicorn
from tests.v0._harness import asgi_request
exp = setup_spans()
for path in ('/hello', '/hello/world', '/metrics'):
    response = asgi_request(fastapi_main.app, path)
    emit(path, {'status': response.status, 'text': response.text[:200],
                'process_time_header': 'x-process-time-seconds' in response.headers})
emit('spans', take(exp))
''')


def test_trailing_slash_endpoint_mounts_the_prometheus_app_with_a_redirect():
    result = ENDPOINT_TRAILING_SLASH.result()
    assert result['/metrics'] == {'status': 307, 'location': '/metrics/', 'is_prometheus': False}
    assert result['/metrics/'] == {'status': 200, 'location': None, 'is_prometheus': True}
    assert result['/hello']['status'] == 200


def test_endpoint_env_var_is_normalised():
    result = ENDPOINT_CUSTOM.result()
    assert '/prom/scrape' in result['routes']
    assert result['/prom/scrape'] == {'status': 200, 'location': None, 'is_prometheus': True}
    assert result['/metrics']['status'] == 404


def test_empty_endpoint_env_var_disables_the_metrics_route():
    result = ENDPOINT_DISABLED.result()
    assert '/metrics' not in result['routes']
    assert result['/metrics']['status'] == 404
    assert result['/hello']['status'] == 200


def test_fastapi_main_example_app():
    # CLAUDE.md § Gate, outside the gate: `python fastapi_main.py` -> /metrics returns 200. /hello-hello is not
    # covered: it makes a real http request to localhost:8000, which needs the uvicorn server this suite deliberately
    # doesn't run
    assert (REPO_ROOT / 'fastapi_main.py').is_file()
    result = FASTAPI_MAIN.result()
    assert result['/hello'] == {'status': 200, 'text': '"hello"', 'process_time_header': True}
    assert result['/hello/world'] == {'status': 200, 'text': '"hello world"', 'process_time_header': True}
    assert result['/metrics']['status'] == 200
    assert '# HELP' in result['/metrics']['text']
    server_names = sorted(s['name'] for s in result['spans'] if s['kind'] == 'SERVER')
    assert server_names == ['GET /hello', 'GET /hello/{name}']
