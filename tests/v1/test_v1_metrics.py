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

ROUTE_OFF = scenario(__name__, 'v1_metrics_route_off', _ROUTE_PRELUDE + r'''
app = otel.instrument(make_app())
emit('visits', visit(app, ['/metrics', '/api/metrics']))
''', env={'OTEL_WRAPPER_PROMETHEUS_PATH': ''})


@pytest.mark.criterion('AC-19')
def test_the_metrics_route_serves_prometheus_without_a_request_span_and_api_metrics_gets_one():
    result = ROUTE.result()
    assert result['routes'] == [['/api/metrics', False], ['/metricsfoo', False], ['/metrics', False]]  # no Mount
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
