"""
v1 metrics, push and scrape (workstream 9, AC-19): the standalone Prometheus server binds
`OTEL_EXPORTER_PROMETHEUS_HOST`; the FastAPI route is the exact path (`add_route`, never `mount`) and makes no request
span, while `/api/metrics` does; a second worker that cannot bind the port warns once and carries on

the server and the global providers are per process, so every test reads a scenario that ran in its own interpreter
"""
import socket

import pytest

from tests.v0._harness import ASGI_HELPER_SOURCE
from tests.v0._harness import scenario
from tests.v1._prelude import PRELUDE

pytest.importorskip('fastapi')


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


_GET = r'''
import os, socket, urllib.request

PORT = int(os.environ['OTEL_EXPORTER_PROMETHEUS_PORT'])


def get(host, path='/metrics'):
    try:
        with urllib.request.urlopen(f'http://{host}:{PORT}{path}', timeout=5) as response:
            return [response.status, response.read().decode()]
    except OSError as e:
        return [None, type(e).__name__]


def non_loopback_ip():
    ip = socket.gethostbyname(socket.gethostname())
    return None if ip.startswith('127.') else ip
'''

# ----------------------------------------------------------------------------------------------------------------------
# the standalone server binds OTEL_EXPORTER_PROMETHEUS_HOST
# ----------------------------------------------------------------------------------------------------------------------

_SERVER_SCRIPT = PRELUDE + _GET + r'''
from opentelemetry import metrics
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    otel.configure()
emit('warnings', otel_warnings(caught))
metrics.get_meter('test').create_counter('scrape_me').add(3)
server = _config._state.prometheus_server
emit('bound', None if server is None else server.server_address[0])
for path in ('/metrics', '/anything/at/all'):
    status, body = get('127.0.0.1', path)
    emit(path, [status, 'scrape_me_total{' in body and '} 3.0' in body, 'target_info' in body])
ip = non_loopback_ip()
emit('non_loopback_ip', ip)
if ip is not None:
    emit('via_non_loopback_ip', get(ip)[0])
'''

HOST_LOOPBACK = scenario(__name__, 'v1_metrics_host_loopback', _SERVER_SCRIPT,
                         env={'OTEL_EXPORTER_PROMETHEUS_PORT': str(_free_port()),
                              'OTEL_EXPORTER_PROMETHEUS_HOST': '127.0.0.1'})
HOST_ALL = scenario(__name__, 'v1_metrics_host_all', _SERVER_SCRIPT,
                    env={'OTEL_EXPORTER_PROMETHEUS_PORT': str(_free_port()),
                         'OTEL_EXPORTER_PROMETHEUS_HOST': '0.0.0.0'})
HOST_EXPLICIT = scenario(__name__, 'v1_metrics_host_explicit', _SERVER_SCRIPT.replace(
    'otel.configure()', "otel.configure(prometheus_host='0.0.0.0', prometheus_port=PORT)"),
    env={'OTEL_EXPORTER_PROMETHEUS_PORT': str(_free_port()), 'OTEL_EXPORTER_PROMETHEUS_HOST': '127.0.0.1'})
NO_PORT = scenario(__name__, 'v1_metrics_no_port', PRELUDE + r'''
otel.configure()
emit('server', _config._state.prometheus_server)
''')


@pytest.mark.criterion('AC-19')
def test_the_server_binds_the_host_variable_and_serves_metrics_on_every_path():
    result = HOST_LOOPBACK.result()
    assert result['warnings'] == []
    assert result['bound'] == '127.0.0.1'
    for path in ('/metrics', '/anything/at/all'):
        assert result[path] == [200, True, True]  # our meter's counter, and the resource as target_info


@pytest.mark.criterion('AC-19')
def test_a_loopback_host_is_not_reachable_from_outside_and_0000_is():
    loopback, everywhere = HOST_LOOPBACK.result(), HOST_ALL.result()
    if loopback['non_loopback_ip'] is None:
        pytest.skip('no non-loopback address to test with')
    assert loopback['via_non_loopback_ip'] is None
    assert everywhere['bound'] == '0.0.0.0'
    assert everywhere['via_non_loopback_ip'] == 200


@pytest.mark.criterion('AC-19')
def test_explicit_host_and_port_beat_the_variables():  # DEC-27: explicit > env > default
    result = HOST_EXPLICIT.result()
    assert result['warnings'] == []
    assert result['bound'] == '0.0.0.0'


def test_no_port_no_server():  # as in v0: the server is opt-in
    assert NO_PORT.result()['server'] is None


# ----------------------------------------------------------------------------------------------------------------------
# a second worker that cannot bind the port warns once and carries on
# ----------------------------------------------------------------------------------------------------------------------

_WORKER = PRELUDE + r'''
import json, logging, sys
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    otel.configure()
    otel.configure()  # the same settings again: a no-op
    otel.instrument(logging)

@otel
def handle():
    return 'handled'

print(json.dumps({'warnings': otel_warnings(caught), 'result': handle(),
                  'spans': [s.name for s in exporter.get_finished_spans()],
                  'server': _config._state.prometheus_server is not None}))
'''

TWO_WORKERS = scenario(__name__, 'v1_metrics_two_workers', PRELUDE + _GET + f'WORKER = {_WORKER!r}\n' + r'''
import json, subprocess, sys
otel.configure()  # the first worker binds the port
emit('first_bound', _config._state.prometheus_server is not None)
second = subprocess.run([sys.executable, '-c', WORKER], capture_output=True, text=True, timeout=60)
emit('second_exit', second.returncode)
emit('second', json.loads(second.stdout.strip().splitlines()[-1]) if second.returncode == 0 else second.stderr)
emit('first_still_serves', get('127.0.0.1')[0])
''', env={'OTEL_EXPORTER_PROMETHEUS_PORT': str(_free_port()), 'OTEL_EXPORTER_PROMETHEUS_HOST': '127.0.0.1'})


@pytest.mark.criterion('AC-19')
def test_a_second_worker_that_cannot_bind_warns_once_and_carries_on():
    result = TWO_WORKERS.result()
    assert result['first_bound'] is True
    assert result['second_exit'] == 0, result['second']
    second = result['second']
    assert len(second['warnings']) == 1, second['warnings']
    assert 'could not listen on 127.0.0.1' in second['warnings'][0]
    assert 'OTLP push' in second['warnings'][0]
    assert second['server'] is False
    assert second['result'] == 'handled' and second['spans'] == ['__main__.handle']  # the worker still traces
    assert result['first_still_serves'] == 200


SWITCHED_OFF = scenario(__name__, 'v1_metrics_switched_off', PRELUDE + r'''
_config.set_exporters_enabled(False)  # what the pytest plugin's opt-in does
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    otel.configure()
emit('warnings', otel_warnings(caught))
emit('server', _config._state.prometheus_server)
''', env={'OTEL_EXPORTER_PROMETHEUS_PORT': str(_free_port())})


def test_a_test_that_switched_exporters_off_binds_no_port():  # DEC-27 rule 3
    result = SWITCHED_OFF.result()
    assert result['warnings'] == [] and result['server'] is None


# ----------------------------------------------------------------------------------------------------------------------
# the FastAPI route: the exact path, no request span; /api/metrics gets one
# ----------------------------------------------------------------------------------------------------------------------

_ROUTE_PRELUDE = ASGI_HELPER_SOURCE + PRELUDE + r'''
from fastapi import FastAPI
from starlette.routing import Mount


def make_app():
    app = FastAPI()

    @app.get('/hello')
    def hello():
        return 'hi'

    @app.get('/api/metrics')
    def api_metrics():
        return 'not prometheus'

    @app.get('/metricsfoo')
    def metricsfoo():
        return 'not prometheus either'

    return app


def server_spans():
    return sorted(s.attributes.get('http.target') for s in exporter.get_finished_spans()
                  if s.kind.name == 'SERVER'
                  and s.instrumentation_scope.name == 'opentelemetry.instrumentation.fastapi')


def visit(app, paths):
    out = {}
    for path in paths:
        exporter.clear()
        response = asgi_request(app, path)
        out[path] = [response.status, '# HELP' in response.text, server_spans()]
    return out
'''

ROUTE = scenario(__name__, 'v1_metrics_route', _ROUTE_PRELUDE + r'''
app = otel.instrument(make_app())
asgi_request(app, '/hello')  # an http.server data point to scrape
emit('routes', [[r.path, isinstance(r, Mount)] for r in app.routes if 'metrics' in r.path])
emit('visits', visit(app, ['/metrics', '/api/metrics', '/metricsfoo', '/hello']))
response = asgi_request(app, '/metrics', headers=[('accept', 'application/openmetrics-text; version=1.0.0')])
emit('openmetrics', [response.headers['content-type'].startswith('application/openmetrics-text'),
                     response.text.rstrip().endswith('# EOF')])
emit('http_metrics', 'http_server_duration_milliseconds' in asgi_request(app, '/metrics').text)
emit('in_schema', '/metrics' in app.openapi()['paths'])
''')

ROUTE_CUSTOM = scenario(__name__, 'v1_metrics_route_custom', _ROUTE_PRELUDE + r'''
app = otel.instrument(make_app())
emit('visits', visit(app, ['/prom/scrape', '/metrics', '/hello', '/api/metrics']))
''', env={'OTEL_WRAPPER_PROMETHEUS_PATH': 'prom//scrape', 'OTEL_PYTHON_FASTAPI_EXCLUDED_URLS': '/hello'})

ROUTE_PLACED = scenario(__name__, 'v1_metrics_route_placed', _ROUTE_PRELUDE + r'''
app = otel.instrument(FastAPI())  # the README's pattern: no routes yet


@app.get('/metrics')  # the app's own, declared after instrument: it wins
def own_metrics():
    return 'mine'


emit('own', visit(app, ['/metrics'])['/metrics'] + [[r.path for r in app.routes].count('/metrics')])

spa = FastAPI()


@spa.get('/{full_path:path}')  # a single-page app's catch-all, declared before instrument
def fallback(full_path: str):
    return 'spa'


otel.instrument(spa)
emit('catch_all', visit(spa, ['/metrics', '/elsewhere']))
''')


def under_root_path(root_path):
    return r'''
def under(app):  # the ASGI server's --root-path, without a proxy that strips it
    async def wrapped(scope, receive, send):
        await app(dict(scope, root_path=%r), receive, send)
    return wrapped
''' % root_path


ROUTE_ROOT_PATH = scenario(__name__, 'v1_metrics_route_root_path', _ROUTE_PRELUDE + under_root_path('/svc') + r'''
emit('server', visit(under(otel.instrument(make_app())), ['/svc/metrics', '/svc/api/metrics', '/svc/hello']))
emit('app', visit(otel.instrument(FastAPI(root_path='/svc/')), ['/svc/metrics', '/metrics']))
''')

_SLASH_SCRIPT = _ROUTE_PRELUDE + under_root_path('/svc') + r'''
def scrape(app, paths):  # visit, plus the redirect a response would carry
    out = {}
    for path in paths:
        exporter.clear()
        response = asgi_request(app, path)
        out[path] = [response.status, response.headers.get('location'), '# HELP' in response.text, server_spans()]
    return out


app = otel.instrument(make_app())
emit('visits', scrape(app, ['/metrics', '/metrics/', '/metrics/foo', '/api/metrics', '/metricsfoo']))
emit('routes', [r.path for r in app.routes if r.path.startswith('/metrics')])
emit('root_path', scrape(under(otel.instrument(make_app())), ['/svc/metrics', '/svc/metrics/', '/svc/metrics/foo']))
emit('app_root_path', scrape(otel.instrument(FastAPI(root_path='/svc')), ['/svc/metrics', '/svc/metrics/']))
own = otel.instrument(FastAPI())


@own.get('/metrics/')  # the app's own, at one of the two forms: the app owns the path, neither form scrapes
def own_metrics():
    return 'mine'


emit('own', scrape(own, ['/metrics', '/metrics/']))
'''

ROUTE_SLASH = scenario(__name__, 'v1_metrics_route_trailing_slash', _SLASH_SCRIPT,
                       env={'OTEL_WRAPPER_PROMETHEUS_PATH': '/metrics/'})
ROUTE_NO_SLASH = scenario(__name__, 'v1_metrics_route_no_trailing_slash', _SLASH_SCRIPT)

ROUTE_OFF = scenario(__name__, 'v1_metrics_route_off', _ROUTE_PRELUDE + r'''
app = otel.instrument(make_app())
emit('visits', visit(app, ['/metrics', '/api/metrics']))
''', env={'OTEL_WRAPPER_PROMETHEUS_PATH': ''})


@pytest.mark.criterion('AC-19')
def test_the_metrics_route_serves_prometheus_without_a_request_span_and_api_metrics_gets_one():
    result = ROUTE.result()
    assert result['routes'] == [['/metrics', False], ['/metrics/', False], ['/api/metrics', False],
                                ['/metricsfoo', False]]  # no Mount
    visits = result['visits']
    assert visits['/metrics'] == [200, True, []]
    assert visits['/api/metrics'] == [200, False, ['/api/metrics']]
    assert visits['/metricsfoo'] == [200, False, ['/metricsfoo']]
    assert visits['/hello'] == [200, False, ['/hello']]
    assert result['http_metrics'] is True
    assert result['openmetrics'] == [True, True]
    assert result['in_schema'] is False


@pytest.mark.criterion('AC-19')
def test_a_custom_path_is_normalised_and_the_apps_own_exclusions_still_apply():
    visits = ROUTE_CUSTOM.result()['visits']
    assert visits['/prom/scrape'] == [200, True, []]
    assert visits['/metrics'] == [404, False, ['/metrics']]
    assert visits['/hello'] == [200, False, []]  # OTEL_PYTHON_FASTAPI_EXCLUDED_URLS is kept, not replaced
    assert visits['/api/metrics'] == [200, False, ['/api/metrics']]


def test_an_empty_path_adds_no_route():
    visits = ROUTE_OFF.result()['visits']
    assert visits['/metrics'] == [404, False, ['/metrics']]
    assert visits['/api/metrics'] == [200, False, ['/api/metrics']]


@pytest.mark.criterion('AC-19')
def test_the_apps_own_route_wins_even_declared_after_instrument_and_ours_beats_a_catch_all():  # review of OTW-12
    result = ROUTE_PLACED.result()
    assert result['own'] == [200, False, [], 1]  # the app's route answers, exactly once, still untraced
    assert result['catch_all']['/metrics'] == [200, True, []]
    assert result['catch_all']['/elsewhere'] == [200, False, ['/elsewhere']]


@pytest.mark.criterion('AC-19')
def test_under_a_root_path_the_scrape_still_makes_no_request_span():  # review of OTW-12
    result = ROUTE_ROOT_PATH.result()
    assert result['server']['/svc/metrics'] == [200, True, []]
    assert result['server']['/svc/api/metrics'] == [200, False, ['/svc/api/metrics']]
    assert result['server']['/svc/hello'] == [200, False, ['/svc/hello']]
    assert result['app'] == {'/svc/metrics': [200, True, []], '/metrics': [200, True, []]}


@pytest.mark.criterion('AC-19')
@pytest.mark.parametrize('scenario_', [ROUTE_SLASH, ROUTE_NO_SLASH], ids=['given /metrics/', 'given /metrics'])
def test_the_scrape_is_served_with_and_without_the_trailing_slash_without_a_redirect(scenario_):  # DEC-92
    result = scenario_.result()
    scrape = [200, None, True, []]  # no redirect, the exposition, no request span
    visits = result['visits']
    assert visits['/metrics'] == scrape and visits['/metrics/'] == scrape
    assert visits['/metrics/foo'] == [404, None, False, ['/metrics/foo']]  # only the two forms are untraced
    assert visits['/api/metrics'] == [200, None, False, ['/api/metrics']]
    assert visits['/metricsfoo'] == [200, None, False, ['/metricsfoo']]
    assert result['routes'] == ['/metrics', '/metrics/', '/metricsfoo']
    root_path = result['root_path']
    assert root_path['/svc/metrics'] == scrape and root_path['/svc/metrics/'] == scrape
    assert root_path['/svc/metrics/foo'] == [404, None, False, ['/svc/metrics/foo']]
    assert result['app_root_path'] == {'/svc/metrics': scrape, '/svc/metrics/': scrape}
    assert result['own']['/metrics'] != scrape, result['own']['/metrics']
    assert result['own']['/metrics/'] == [200, None, False, []]  # the app's route, untraced like the scrape
