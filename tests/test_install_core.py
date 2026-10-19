"""
AC-20: `pip install opentelemetry_wrapper` without extras imports and runs `@otel`, and each extra enables its
integration (DEC-35, DEC-36, DEC-57)

two halves, each run where it can be true:
* the no-extras half is the install trial of CI's `extras: none` job (`ci/test.sh core`), which sets
  `OTW_INSTALL_TRIAL=core` after `pip install .`: `ci/smoke_core.py` runs in a subprocess from an empty directory with
  no `PYTHONPATH`, so only the installed package can be imported. Everywhere else it is skipped, since this checkout's
  environment is not a clean install
* the extras half runs wherever the extra is installed (CI's `extras: all` job installs them all and sets
  `OTW_INSTALL_TRIAL=all`, which turns a missing extra from a skip into a failure): `otel.instrument` on a FastAPI app,
  a SQLAlchemy engine, `requests` and (with no argument) system metrics, each producing its spans or metrics
"""
import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from tests.v0._harness import ASGI_HELPER_SOURCE
from tests.v0._harness import clean_env
from tests.v0._harness import scenario
from tests.v1._prelude import PRELUDE

ROOT = Path(__file__).resolve().parents[1]
TRIAL = os.environ.get('OTW_INSTALL_TRIAL', '')


@pytest.mark.criterion('AC-20')
@pytest.mark.skipif(TRIAL != 'core', reason='the no-extras install trial: set OTW_INSTALL_TRIAL=core (ci/test.sh core)')
def test_the_package_installed_without_extras_imports_and_runs_otel():  # AC-20
    env = clean_env({'PYTHONPATH': None})  # only the installed package may be importable
    with tempfile.TemporaryDirectory() as empty:
        done = subprocess.run([sys.executable, str(ROOT / 'ci' / 'smoke_core.py')], cwd=empty, env=env,
                              capture_output=True, text=True, encoding='utf-8', timeout=120)
    assert done.returncode == 0, f'{done.stdout}\n{done.stderr}'
    assert done.stdout.startswith('ok: python '), done.stdout


def _have(*modules):
    return all(importlib.util.find_spec(m) is not None for m in modules)


def _extra(*modules):
    """the test needs these modules: skipped without them, unless every extra is meant to be installed"""
    missing = TRIAL != 'all' and not _have(*modules)
    return pytest.mark.skipif(missing, reason=f'the extra for {modules[0]} is not installed')


def _integration(name, body, *modules):
    return scenario(__name__, f'install_extra_{name}', PRELUDE + ASGI_HELPER_SOURCE + body) \
        if TRIAL == 'all' or _have(*modules) else None


FASTAPI = _integration('fastapi', r'''
from fastapi import FastAPI
app = FastAPI()

@app.get('/hello')
def hello():
    return 'hello'

otel.instrument(app)
emit('status', asgi_request(app, '/hello').status)
# (fastapi 0.142+ makes a server span of its own, under the scope 'fastapi': only the contrib one counts)
emit('server_spans', [s.name for s in exporter.get_finished_spans()
                      if s.kind.name == 'SERVER' and s.instrumentation_scope.name == 'opentelemetry.instrumentation.fastapi'])
''', 'fastapi', 'opentelemetry.instrumentation.fastapi')

SQLALCHEMY = _integration('sqlalchemy', r'''
from sqlalchemy import create_engine, text
engine = create_engine('sqlite:///:memory:')
otel.instrument(engine)
with engine.connect() as c:
    c.execute(text('SELECT 1')).fetchall()
emit('spans', [s.name for s in exporter.get_finished_spans()])
''', 'sqlalchemy', 'opentelemetry.instrumentation.sqlalchemy')

REQUESTS = _integration('requests', r'''
import http.server
import os
import threading

import requests
os.environ['NO_PROXY'] = '127.0.0.1'


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Length', '2')
        self.end_headers()
        self.wfile.write(b'ok')

    def log_message(self, *args):
        pass


server = http.server.HTTPServer(('127.0.0.1', 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
otel.instrument(requests)
emit('status', requests.get(f'http://127.0.0.1:{server.server_port}/x', timeout=10).status_code)
server.shutdown()
emit('spans', [[s.name, s.kind.name] for s in exporter.get_finished_spans()])
''', 'requests', 'opentelemetry.instrumentation.requests')

SYSTEM_METRICS = _integration('system_metrics', r'''
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

reader = InMemoryMetricReader()  # a provider of our own first: the wrapper leaves a configured one alone
metrics.set_meter_provider(MeterProvider(metric_readers=[reader]))
with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    otel.instrument()
data = reader.get_metrics_data()
emit('metrics', sorted({m.name for rm in (data.resource_metrics if data else []) for sm in rm.scope_metrics
                        for m in sm.metrics}))
''', 'psutil', 'opentelemetry.instrumentation.system_metrics')


@pytest.mark.criterion('AC-20')
@_extra('fastapi', 'opentelemetry.instrumentation.fastapi')
def test_the_fastapi_extra_instruments_an_app():  # AC-20
    r = FASTAPI.result()
    assert r['status'] == 200
    assert r['server_spans'], r['server_spans']


@pytest.mark.criterion('AC-20')
@_extra('sqlalchemy', 'opentelemetry.instrumentation.sqlalchemy')
def test_the_sqlalchemy_extra_instruments_an_engine():  # AC-20
    spans = SQLALCHEMY.result()['spans']
    assert any(name.startswith('SELECT') for name in spans), spans


@pytest.mark.criterion('AC-20')
@_extra('requests', 'opentelemetry.instrumentation.requests')
def test_the_requests_extra_instruments_requests():  # AC-20
    r = REQUESTS.result()
    assert r['status'] == 200
    assert ['GET', 'CLIENT'] in r['spans'], r['spans']


@pytest.mark.criterion('AC-20')
@_extra('psutil', 'opentelemetry.instrumentation.system_metrics')
def test_the_system_metrics_extra_exports_system_metrics():  # AC-20
    names = SYSTEM_METRICS.result()['metrics']
    assert any(n.startswith('system.') for n in names), names
