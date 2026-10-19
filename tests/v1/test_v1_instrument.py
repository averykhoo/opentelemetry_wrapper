"""
v1 `otel.instrument(...)`: idempotent (AC-6), never crashes (AC-7), configures eagerly (AC-3), and does nothing when
disabled (AC-4); OTW-3's trap: an app that already started can't take middleware

global OpenTelemetry state cannot be reset, so every test reads a scenario that ran in its own interpreter
"""
import pytest

from tests.v0._harness import ASGI_HELPER_SOURCE
from tests.v0._harness import scenario

pytest.importorskip('fastapi')
pytest.importorskip('sqlalchemy')

PRELUDE = ASGI_HELPER_SOURCE + r'''
import json
import logging
import warnings

from tests.impl import import_v1
v1 = import_v1()  # opentelemetry_wrapper.v1 (neither it nor the package root imports v0)
otel = v1.otel
from opentelemetry_wrapper.v1 import OtelWrapperWarning
from opentelemetry_wrapper.v1 import _config
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
exporter = InMemorySpanExporter()
_config.add_span_sink(exporter)  # v1's test sink: receives every finished span


def make_app():
    from fastapi import FastAPI
    app = FastAPI()

    @app.get('/hello')
    def hello():
        return 'hello'

    return app


def span_names():
    return [s.name for s in exporter.get_finished_spans()]


def server_spans():
    """the server spans the contrib instrumentation made (fastapi 0.142+ emits its own, under the scope 'fastapi')"""
    return [s for s in exporter.get_finished_spans()
            if s.kind.name == 'SERVER' and s.instrumentation_scope.name == 'opentelemetry.instrumentation.fastapi']


def all_server_spans():
    return [s for s in exporter.get_finished_spans() if s.kind.name == 'SERVER']


def wrapper_handlers():
    return [h for h in logging.getLogger().handlers if getattr(h, '_opentelemetry_wrapper', False)]


def select_query(engine):
    from sqlalchemy import text
    with engine.connect() as c:
        c.execute(text('SELECT 1')).fetchall()


class Warned:
    """collects the OtelWrapperWarnings raised inside a `with` block"""
    def __enter__(self):
        self._cm = warnings.catch_warnings(record=True)
        self.caught = self._cm.__enter__()
        warnings.simplefilter('always')
        return self

    def __exit__(self, *exc):
        self._cm.__exit__(*exc)

    @property
    def messages(self):
        return [str(w.message) for w in self.caught if issubclass(w.category, OtelWrapperWarning)]
'''

# ----------------------------------------------------------------------------------------------------------------------
# AC-6: instrumenting twice behaves as once
# ----------------------------------------------------------------------------------------------------------------------

APP_TWICE = scenario(__name__, 'v1_instrument_app_twice', PRELUDE + r'''
app = make_app()
with Warned() as w:
    first = otel.instrument(app)
    second = otel.instrument(app)
emit('same_object', first is app and second is app)
emit('warnings', w.messages)
emit('status', asgi_request(app, '/hello').status)
emit('server_spans', len(server_spans()))
emit('all_server_spans', len(all_server_spans()))
''')

APP_ONCE = scenario(__name__, 'v1_instrument_app_once', PRELUDE + r'''
app = make_app()
otel.instrument(app)
emit('status', asgi_request(app, '/hello').status)
emit('server_spans', len(server_spans()))
''')

ENGINE_ONCE = scenario(__name__, 'v1_instrument_engine_once', PRELUDE + r'''
from sqlalchemy import create_engine
engine = create_engine('sqlite:///:memory:')
returned = otel.instrument(engine)
emit('returned_engine', returned is engine)
select_query(engine)
emit('select_spans', [n for n in span_names() if n.startswith('SELECT')])
emit('listeners', len(engine.dispatch.before_cursor_execute))
''')

ENGINE_TWICE = scenario(__name__, 'v1_instrument_engine_twice', PRELUDE + r'''
from sqlalchemy import create_engine
engine = create_engine('sqlite:///:memory:')
otel.instrument(engine)
otel.instrument(engine)
select_query(engine)
emit('select_spans', [n for n in span_names() if n.startswith('SELECT')])
emit('listeners', len(engine.dispatch.before_cursor_execute))
''')

LOGGING_TWICE = scenario(__name__, 'v1_instrument_logging_twice', PRELUDE + r'''
before = len(logging.getLogger().handlers)
otel.instrument(logging)
otel.instrument(logging)
emit('added', len(logging.getLogger().handlers) - before)
emit('wrapper_handlers', len(wrapper_handlers()))
''')


@pytest.mark.criterion('AC-6')
def test_an_app_instrumented_twice_is_the_same_app_without_warnings():  # AC-6
    r = APP_TWICE.result()
    assert r['same_object'] is True
    assert r['warnings'] == []


@pytest.mark.criterion('AC-6')
def test_an_app_instrumented_twice_gives_one_server_span_per_request():  # AC-6
    r = APP_TWICE.result()
    assert r['status'] == 200
    assert r['server_spans'] == 1
    assert r['all_server_spans'] == 1
    # the second call must not even reach upstream, which logs a warning when told to instrument an app twice
    assert 'already instrumented' not in APP_TWICE.result().stderr


def test_an_app_instrumented_once_gives_one_server_span():  # AC-6 (positive control)
    r = APP_ONCE.result()
    assert r['status'] == 200
    assert r['server_spans'] == 1


def test_an_engine_instrumented_once_gives_a_select_span():  # AC-6 (positive control)
    r = ENGINE_ONCE.result()
    assert r['returned_engine'] is True
    assert len(r['select_spans']) == 1, r['select_spans']


@pytest.mark.criterion('AC-6')
def test_an_engine_instrumented_twice_gives_one_select_span_per_query():  # AC-6
    assert len(ENGINE_TWICE.result()['select_spans']) == 1, ENGINE_TWICE.result()['select_spans']


@pytest.mark.criterion('AC-6')
def test_an_engine_instrumented_twice_listens_once():  # AC-6
    # a second listener would start a second span per query and leak it (upstream overwrites the span on the context,
    # so the first is never ended, and the exported spans alone can't show it)
    assert ENGINE_TWICE.result()['listeners'] == ENGINE_ONCE.result()['listeners']


@pytest.mark.criterion('AC-6')
def test_logging_instrumented_twice_adds_one_handler_in_total():  # AC-6
    r = LOGGING_TWICE.result()
    assert r['added'] == 1
    assert r['wrapper_handlers'] == 1


# ----------------------------------------------------------------------------------------------------------------------
# AC-7: unsupported targets and failing integrations warn once and never raise
# ----------------------------------------------------------------------------------------------------------------------

UNSUPPORTED = scenario(__name__, 'v1_instrument_unsupported', PRELUDE + r'''
with Warned() as w_module:
    returned_module = otel.instrument(json)
with Warned() as w_int:
    returned_int = otel.instrument(42)
emit('module_unchanged', returned_module is json)
emit('module_warnings', w_module.messages)
emit('int_unchanged', returned_int == 42 and type(returned_int) is int)
emit('int_warnings', w_int.messages)
''')

FAILING = scenario(__name__, 'v1_instrument_failing_integration', PRELUDE + r'''
import requests
from opentelemetry.instrumentation import dependencies
from opentelemetry.instrumentation.requests import RequestsInstrumentor


class FakeConflict:
    def __str__(self):
        return 'fake conflict'


dependencies.get_dependency_conflicts = lambda *args, **kwargs: FakeConflict()
raised = None
with Warned() as w:
    try:
        returned = otel.instrument(requests)
    except BaseException as e:
        raised = repr(e)
        returned = None
emit('raised', raised)
emit('returned_requests', returned is requests)
emit('warnings', w.messages)
emit('instrumented', RequestsInstrumentor().is_instrumented_by_opentelemetry)
''')


@pytest.mark.criterion('AC-7')
def test_an_unsupported_module_is_returned_unchanged_with_one_warning():  # AC-7
    r = UNSUPPORTED.result()
    assert r['module_unchanged'] is True
    assert len(r['module_warnings']) == 1, r['module_warnings']


@pytest.mark.criterion('AC-7')
@pytest.mark.criterion('AC-22')
def test_an_unsupported_object_is_returned_unchanged_with_one_warning():  # AC-7
    r = UNSUPPORTED.result()
    assert r['int_unchanged'] is True
    assert len(r['int_warnings']) == 1, r['int_warnings']


@pytest.mark.criterion('AC-7')
def test_a_failing_integration_does_not_raise():  # AC-7
    r = FAILING.result()
    assert r['raised'] is None
    assert r['returned_requests'] is True


@pytest.mark.criterion('AC-7')
@pytest.mark.criterion('AC-22')
def test_a_dependency_conflict_warns_once_and_instruments_nothing():  # AC-7
    r = FAILING.result()
    assert len(r['warnings']) == 1, r['warnings']
    assert 'fake conflict' in r['warnings'][0]
    assert r['instrumented'] is False


# ----------------------------------------------------------------------------------------------------------------------
# the trap (OTW-3): instrumenting an app that already started
# ----------------------------------------------------------------------------------------------------------------------

STARTED_APP = scenario(__name__, 'v1_instrument_started_app', PRELUDE + r'''
app = make_app()
emit('first_status', asgi_request(app, '/hello').status)  # builds app.middleware_stack
emit('started', app.middleware_stack is not None)
exporter.clear()
with Warned() as w:
    returned = otel.instrument(app)
emit('same_app', returned is app)
emit('warnings', w.messages)
emit('status', asgi_request(app, '/hello').status)
emit('server_spans', len(server_spans()))
''')


def test_instrumenting_a_started_app_warns_once_and_returns_the_same_app():  # OTW-3 trap
    r = STARTED_APP.result()
    assert r['started'] is True
    assert r['same_app'] is True
    assert len(r['warnings']) == 1, r['warnings']
    assert 'started' in r['warnings'][0]


def test_a_started_app_still_works_but_has_no_server_span():  # OTW-3 trap
    r = STARTED_APP.result()
    assert r['first_status'] == 200
    assert r['status'] == 200
    assert r['server_spans'] == 0


# ----------------------------------------------------------------------------------------------------------------------
# AC-3: instrumenting configures eagerly; no argument means logging and requests, never sqlalchemy (DEC-11)
# ----------------------------------------------------------------------------------------------------------------------

EAGER = scenario(__name__, 'v1_instrument_eager_configuration', PRELUDE + r'''
emit('before', _config.is_configured())
otel.instrument(logging)
emit('after', _config.is_configured())
''')

NO_ARGUMENT = scenario(__name__, 'v1_instrument_no_argument', PRELUDE + r'''
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
before = len(logging.getLogger().handlers)
with Warned() as w:
    returned = otel.instrument()
emit('returned', returned)
emit('handlers_added', len(logging.getLogger().handlers) - before)
emit('wrapper_handlers', len(wrapper_handlers()))
emit('requests', RequestsInstrumentor().is_instrumented_by_opentelemetry)
emit('sqlalchemy', SQLAlchemyInstrumentor().is_instrumented_by_opentelemetry)
emit('configured', _config.is_configured())
emit('warnings', w.messages)
''')


@pytest.mark.criterion('AC-3')
def test_instrumenting_configures_eagerly():  # AC-3
    r = EAGER.result()
    assert r['before'] is False
    assert r['after'] is True


@pytest.mark.criterion('AC-3')
def test_instrument_with_no_argument_returns_none_and_does_not_warn():  # AC-3
    r = NO_ARGUMENT.result()
    assert r['returned'] is None
    assert r['configured'] is True
    assert r['warnings'] == []


def test_instrument_with_no_argument_does_logging_and_requests_but_not_sqlalchemy():  # AC-3, DEC-11
    r = NO_ARGUMENT.result()
    assert r['handlers_added'] == 1
    assert r['wrapper_handlers'] == 1
    assert r['requests'] is True
    assert r['sqlalchemy'] is False


# ----------------------------------------------------------------------------------------------------------------------
# AC-4: disabled means nothing happens
# ----------------------------------------------------------------------------------------------------------------------

DISABLED_BODY = PRELUDE + r'''
app = make_app()
before = len(logging.getLogger().handlers)
with Warned() as w:
    returned = otel.instrument(app)
    otel.instrument(logging)
    returned_none = otel.instrument()
emit('same_app', returned is app)
emit('no_argument_returns_none', returned_none is None)
emit('status', asgi_request(app, '/hello').status)
emit('spans', span_names())
emit('handlers_added', len(logging.getLogger().handlers) - before)
emit('configured', _config.is_configured())
emit('warnings', w.messages)
'''
DISABLED = scenario(__name__, 'v1_instrument_disabled_wrapper', DISABLED_BODY, env={'OTEL_WRAPPER_DISABLED': 'true'})
SDK_DISABLED = scenario(__name__, 'v1_instrument_disabled_sdk', DISABLED_BODY, env={'OTEL_SDK_DISABLED': 'true'})


@pytest.mark.parametrize('which', ['wrapper', 'sdk'])
@pytest.mark.criterion('AC-4')
def test_disabled_instruments_nothing_and_configures_nothing(which):  # AC-4
    r = {'wrapper': DISABLED, 'sdk': SDK_DISABLED}[which].result()
    assert r['same_app'] is True
    assert r['no_argument_returns_none'] is True
    assert r['status'] == 200
    assert r['spans'] == []
    assert r['handlers_added'] == 0
    assert r['configured'] is False
    assert r['warnings'] == []


# ----------------------------------------------------------------------------------------------------------------------
# review fixes (OTW-3, session 2026-10-18l)
# ----------------------------------------------------------------------------------------------------------------------

FAILING_INTEGRATION = scenario(__name__, 'v1_instrument_no_argument_guards', PRELUDE + r'''
from opentelemetry_wrapper.v1 import _instrument
calls = []


def fine(name):
    def run(notes):
        calls.append(name)
    return run


def broken(notes):
    calls.append('requests')
    raise RuntimeError('requests is broken')


_instrument._installed = lambda *modules: True
_instrument.instrument_logging = fine('logging')
_instrument.instrument_requests = broken
_instrument.instrument_system_metrics = fine('system_metrics')
with Warned() as w:
    otel.instrument()
emit('calls', calls)
emit('warnings', w.messages)
''')


@pytest.mark.criterion('AC-7')
def test_one_failing_integration_does_not_skip_the_rest_of_instrument_with_no_argument():  # AC-7
    r = FAILING_INTEGRATION.result()
    assert r['calls'] == ['logging', 'requests', 'system_metrics']
    assert len(r['warnings']) == 1 and 'requests is broken' in r['warnings'][0]


FUNCTION_FIRST = scenario(__name__, 'v1_instrument_function_before_call', PRELUDE + r'''
def f():
    return 1


wrapped = otel.instrument(f)
emit('configured_by_decorating', _config.is_configured())
otel.instrument(logging)
emit('configured_by_a_library', _config.is_configured())
''')


def test_instrumenting_a_function_decorates_without_configuring():  # AC-3 (DEC-27 rule 1)
    r = FUNCTION_FIRST.result()
    assert r['configured_by_decorating'] is False
    assert r['configured_by_a_library'] is True
