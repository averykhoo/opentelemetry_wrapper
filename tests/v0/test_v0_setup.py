"""
global setup: `instrument_all`, `OTEL_WRAPPER_DISABLED`, service name / resource, prometheus port, `requests`

everything that depends on import-time env vars or installs global providers runs in a fresh interpreter
"""
import json
import socket

import pytest

from tests.v0._harness import scenario


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


# ----------------------------------------------------------------------------------------------------------------------
# public API surface (v0 and v1 ship side by side, so v0's names must keep working)
# ----------------------------------------------------------------------------------------------------------------------

PUBLIC_NAMES = ('__version__', 'instrument_all', 'instrument_dataclasses', 'instrument_decorate',
                'instrument_fastapi_app', 'instrument_logging', 'instrument_requests', 'instrument_sqlalchemy',
                'instrument_sqlalchemy_engine')


def test_public_api():
    # the package itself, not the OTW_IMPL adapter: these are v0's own names, which must keep working under v1 too
    import opentelemetry_wrapper as otw
    assert set(PUBLIC_NAMES) <= set(otw.__all__)
    for name in PUBLIC_NAMES:
        assert hasattr(otw, name), name
    for name in PUBLIC_NAMES[1:]:
        assert callable(getattr(otw, name)), name
    assert isinstance(otw.__version__, str)
    assert callable(otw.instrument_system_metrics)  # importable, though missing from __all__ (v0 cleanup, OTW-18)


# ----------------------------------------------------------------------------------------------------------------------
# instrument_all
# ----------------------------------------------------------------------------------------------------------------------

INSTRUMENT_ALL = scenario(__name__, 'instrument_all_twice', r'''
import dataclasses, logging
original_dataclass = dataclasses.dataclass
from tests.impl import setup
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor

root = logging.getLogger()
before = len(root.handlers)
emit('first_call_returns', setup())
emit('second_call_returns', setup())
emit('handlers_added', len(root.handlers) - before)
emit('dataclasses_patched', dataclasses.dataclass is not original_dataclass)
emit('requests_instrumented', RequestsInstrumentor().is_instrumented_by_opentelemetry)
emit('system_metrics_instrumented', SystemMetricsInstrumentor().is_instrumented_by_opentelemetry)
emit('sqlalchemy_instrumented', SQLAlchemyInstrumentor().is_instrumented_by_opentelemetry)
logging.info('after instrument_all')
''', env={'OTEL_EXPORTER_OTLP_HEADER': 'authorization=Bearer s3cr3t-t0ken'})


@pytest.fixture(scope='module')
def instrument_all_result():
    result = INSTRUMENT_ALL.result()
    assert result.returncode == 0, result.describe()
    return result


def _stderr_json(result):
    return [json.loads(line) for line in result.stderr_lines]


def test_instrument_all_twice_does_not_raise_or_duplicate_handlers(instrument_all_result):
    assert instrument_all_result['first_call_returns'] is None
    assert instrument_all_result['second_call_returns'] is None
    assert instrument_all_result['handlers_added'] == 1
    messages = [log['message'] for log in _stderr_json(instrument_all_result)]
    assert messages.count('after instrument_all') == 1


def test_instrument_all_defaults(instrument_all_result):
    assert instrument_all_result['dataclasses_patched'] is True
    assert instrument_all_result['requests_instrumented'] is True
    assert instrument_all_result['system_metrics_instrumented'] is True
    assert instrument_all_result['sqlalchemy_instrumented'] is False  # "too noisy for a default"


def test_instrument_all_logs_its_config_once_as_json(instrument_all_result):
    logs = _stderr_json(instrument_all_result)  # also asserts every stderr line is json
    config_logs = [log for log in logs if isinstance(log['msg'], dict)
                   and 'opentelemetry_wrapper.__version__' in log['msg']]
    assert len(config_logs) == 1
    assert config_logs[0]['name'] == 'opentelemetry_wrapper'
    assert config_logs[0]['msg']['OTEL_EXPORTER_PROMETHEUS_ENDPOINT'] == '/metrics'


@pytest.mark.v0_specific
def test_second_instrument_all_warns_that_system_metrics_are_already_instrumented(instrument_all_result):
    # instrument_system_metrics() has no "already instrumented" guard, unlike the other instrumentors
    logs = _stderr_json(instrument_all_result)
    assert [log['message'] for log in logs].count('Attempting to instrument while already instrumented') == 1


@pytest.mark.xfail(strict=True, reason='v0 bug list "Secrets in logs" (from reading the code, reproduced here): '
                                       'instrument_all() logs OTEL_EXPORTER_OTLP_HEADER verbatim (__init__.py:71)')
def test_instrument_all_does_not_log_otlp_header_values(instrument_all_result):
    assert 's3cr3t-t0ken' not in instrument_all_result.stderr


# ----------------------------------------------------------------------------------------------------------------------
# OTEL_WRAPPER_DISABLED
# ----------------------------------------------------------------------------------------------------------------------

DISABLED = scenario(__name__, 'disabled', r'''
import asyncio, dataclasses, logging
original_dataclass = dataclasses.dataclass
from tests import impl as otw
otw.load()
from fastapi import FastAPI
from sqlalchemy import create_engine
exp = setup_spans()

def f():
    return 1

async def g():
    return 2

class C:
    def m(self):
        return 3

emit('function_returned_unchanged', otw.decorate(f) is f)
emit('coroutine_returned_unchanged', otw.decorate(g) is g)
emit('class_returned_unchanged', otw.decorate(C) is C
                                 and C.__getattribute__ is object.__getattribute__)
otw.decorate(f)(); asyncio.run(otw.decorate(g)()); otw.decorate(C)().m()

root = logging.getLogger()
before = len(root.handlers)
otw.setup()
otw.instrument_logging()
emit('handlers_added', len(root.handlers) - before)
emit('dataclasses_patched', dataclasses.dataclass is not original_dataclass)

app = FastAPI()
emit('app_returned_unchanged', otw.instrument_app(app) is app)
emit('metrics_route_added', any(route.path == '/metrics' for route in app.router.routes))
engine = create_engine('sqlite://')
emit('engine_returned_unchanged', otw.instrument_engine(engine) is engine)
otw.instrument_sqlalchemy(); otw.instrument_requests(); otw.instrument_dataclasses()
emit('spans', take(exp, include_library_spans=True))
''', env={'OTEL_WRAPPER_DISABLED': ' True '})


def test_disabled_makes_every_entry_point_a_no_op():
    result = DISABLED.result()
    assert result['function_returned_unchanged'] is True
    assert result['coroutine_returned_unchanged'] is True
    assert result['class_returned_unchanged'] is True
    assert result['handlers_added'] == 0
    assert result['dataclasses_patched'] is False
    assert result['app_returned_unchanged'] is True
    assert result['metrics_route_added'] is False
    assert result['engine_returned_unchanged'] is True
    assert result['spans'] == []


# ----------------------------------------------------------------------------------------------------------------------
# service name / resource
# ----------------------------------------------------------------------------------------------------------------------

_RESOURCE_SCRIPT = r'''
from opentelemetry import trace
from tests import impl
impl.load()  # installs the tracer provider
emit('resource', dict(trace.get_tracer_provider().resource.attributes))
'''

SERVICE_FROM_ENV = scenario(__name__, 'service_name_env', _RESOURCE_SCRIPT,
                            env={'OTEL_SERVICE_NAME': 'my-service', 'OTEL_SERVICE_NAMESPACE': 'my-namespace'})
SERVICE_FROM_RESOURCE_ATTRIBUTES = scenario(__name__, 'service_name_resource_attributes', _RESOURCE_SCRIPT, env={
    'OTEL_RESOURCE_ATTRIBUTES': 'service.name=from-attributes,service.namespace=ns-from-attributes,team=core'})
SERVICE_DEFAULT = scenario(__name__, 'service_name_default', _RESOURCE_SCRIPT)


def test_service_name_and_namespace_from_env():
    resource = SERVICE_FROM_ENV.result()['resource']
    assert resource['service.name'] == 'my-service'
    assert resource['service.namespace'] == 'my-namespace'
    assert resource['telemetry.sdk.language'] == 'python'


def test_service_name_and_namespace_from_otel_resource_attributes():
    resource = SERVICE_FROM_RESOURCE_ATTRIBUTES.result()['resource']
    assert resource['service.name'] == 'from-attributes'
    assert resource['service.namespace'] == 'ns-from-attributes'
    assert resource['team'] == 'core'  # Resource.create() merges OTEL_RESOURCE_ATTRIBUTES


@pytest.mark.v0_specific  # DEC-29: service.name will follow semconv instead
def test_default_service_name_is_user_at_host_and_main_file():
    resource = SERVICE_DEFAULT.result()['resource']
    name = resource['service.name']
    assert '@' in name
    assert name.endswith(':<scenario_service_name_default.py>')
    assert 'service.namespace' not in resource  # not in k8s, nothing configured


# ----------------------------------------------------------------------------------------------------------------------
# prometheus port (standalone metrics server); binds a random free port on localhost only
# ----------------------------------------------------------------------------------------------------------------------

_PORT_SCRIPT = r'''
import os, socket, urllib.request
from tests.impl import instrument_requests
instrument_requests()  # initialises the meter provider, which starts the prometheus server
port = int(os.environ['OTEL_EXPORTER_PROMETHEUS_PORT'])
for path in ('/', '/metrics', '/anything/at/all'):
    with urllib.request.urlopen(f'http://localhost:{port}{path}', timeout=5) as response:
        emit(path, [response.status, '# HELP' in response.read().decode()])
ip = socket.gethostbyname(socket.gethostname())
emit('non_loopback_ip', None if ip.startswith('127.') else ip)
if not ip.startswith('127.'):
    try:
        with urllib.request.urlopen(f'http://{ip}:{port}/metrics', timeout=3) as response:
            emit('reachable_via_non_loopback_ip', response.status == 200)
    except OSError as e:
        emit('reachable_via_non_loopback_ip', False)
'''

PROMETHEUS_PORT = scenario(__name__, 'prometheus_port', _PORT_SCRIPT,
                           env={'OTEL_EXPORTER_PROMETHEUS_PORT': str(_free_port())})
PROMETHEUS_HOST = scenario(__name__, 'prometheus_host', _PORT_SCRIPT,
                           env={'OTEL_EXPORTER_PROMETHEUS_PORT': str(_free_port()),
                                'OTEL_EXPORTER_PROMETHEUS_HOST': '0.0.0.0'})


def test_prometheus_port_serves_metrics_on_every_path():
    result = PROMETHEUS_PORT.result()
    for path in ('/', '/metrics', '/anything/at/all'):
        assert result[path] == [200, True]


@pytest.mark.xfail(strict=True, reason='v0 bug list "Prometheus port only binds to localhost" (from reading the code, '
                                       'reproduced here): otel_providers.py:112 hardcodes addr="localhost" and '
                                       'ignores OTEL_EXPORTER_PROMETHEUS_HOST')
def test_prometheus_host_env_var_is_honoured():
    result = PROMETHEUS_HOST.result()
    if result['non_loopback_ip'] is None:
        pytest.skip('no non-loopback address to test with')  # note: a skip inside a strict xfail is still a skip
    assert result['reachable_via_non_loopback_ip'] is True


# ----------------------------------------------------------------------------------------------------------------------
# requests (in-process: RequestsInstrumentor's patch is global but harmless; no network, a fake transport adapter)
# ----------------------------------------------------------------------------------------------------------------------

def _fake_session():
    import requests
    from requests.adapters import BaseAdapter

    class FakeAdapter(BaseAdapter):
        def send(self, request, **kwargs):
            response = requests.Response()
            response.status_code = 200
            response._content = b'ok'
            response.url = request.url
            response.request = request
            response.headers['X-Process-Time-Seconds'] = '0.5'
            response.headers['X-Kong-Upstream-Latency'] = '12'
            response.headers['X-Unlisted-Header'] = 'nope'
            return response

        def close(self):
            pass

    session = requests.Session()
    session.mount('http://', FakeAdapter())
    return session


def test_requests_client_span_with_response_header_attributes(otw, spans):
    otw.instrument_requests()
    otw.instrument_requests()  # idempotent
    session = _fake_session()
    spans.clear()
    assert session.get('http://example.invalid/some/path').text == 'ok'

    (record,) = spans.records()
    assert record['name'] == 'GET'
    assert record['kind'] == 'CLIENT'
    assert record['attributes']['http.url'] == 'http://example.invalid/some/path'
    assert record['attributes']['http.status_code'] == 200
    headers = {k: v for k, v in record['attributes'].items() if k.startswith('http.response.header.')}
    assert headers == {'http.response.header.x-process-time-seconds': '0.5',
                       'http.response.header.x-kong-upstream-latency': '12'}
