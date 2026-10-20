"""
v0's root names at 1.0.0 (DEC-96): thin aliases onto v1, deleted at 2.0 (`opentelemetry_wrapper/_v0_aliases.py`)

each alias does what its replacement in README.md § Upgrading from v0 does, returns what that returns, writes exactly
one stderr JSON line naming the replacement the first time it is used (DEC-81's channel, never `warnings.warn`), and
never raises of its own accord. `instrument_dataclasses()` is a warned no-op (DEC-42); v0's per-call logging options
are accepted and ignored with a warning naming the environment variables (DEC-43). and the package imports and runs
with none of v0's dependencies importable (the lean install, AC-20)
"""
import json

import pytest

from tests.v0._harness import ASGI_HELPER_SOURCE
from tests.v0._harness import scenario

ALIASES = ('instrument_all', 'instrument_dataclasses', 'instrument_decorate', 'instrument_fastapi_app',
           'instrument_logging', 'instrument_requests', 'instrument_sqlalchemy', 'instrument_sqlalchemy_engine',
           'instrument_system_metrics')

# no `tests.impl`: the aliases are reached the way a v0 user reaches them, from the root
SINK = r'''
import warnings
import opentelemetry_wrapper as root
from opentelemetry_wrapper import otel
from opentelemetry_wrapper.v1 import _config
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
exporter = InMemorySpanExporter()
_config.add_span_sink(exporter)


def span_names():
    return [s.name for s in exporter.get_finished_spans()]
'''

# every alias called twice, from two call sites; each call's result emitted
CALLS = scenario(__name__, 'v0_aliases_called', SINK + ASGI_HELPER_SOURCE + r'''
import functools
import logging

import fastapi
import requests
import sqlalchemy
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')

    @root.instrument_decorate
    def plain(x):
        return x + 1

    def again(x):
        return x * 2

    again = root.instrument_decorate(again)

    @functools.partial(root.instrument_decorate, func_name='named by partial')
    def by_partial():
        return 'partial'

    @root.instrument_decorate(func_name='named by call')
    def by_call():
        return 'call'

    @root.instrument_decorate
    class Thing:
        def method(self):
            return 'method'

        @property
        def prop(self):
            return 'prop'

    exporter.clear()
    emit('results', [plain(1), again(2), by_partial(), by_call(), Thing().method(), Thing().prop])
    emit('decorate_spans', span_names())
    emit('decorate_marks', [getattr(f, '__wrapped__', None) is not None for f in (plain, again)])

    emit('logging_returns', root.instrument_logging() is logging)
    root.instrument_logging(level=logging.DEBUG, path='x.log', stream=None, print_json=False,
                            clobber_other_log_handlers=True)
    root.instrument_logging(stream=None)  # the options line again: written once
    logging.getLogger('alias').warning('hello from the logging alias')

    emit('requests_returns', root.instrument_requests() is requests)
    root.instrument_requests()
    emit('requests_instrumented', RequestsInstrumentor().is_instrumented_by_opentelemetry)

    emit('sqlalchemy_returns', root.instrument_sqlalchemy() is sqlalchemy)
    root.instrument_sqlalchemy()
    emit('sqlalchemy_instrumented', SQLAlchemyInstrumentor().is_instrumented_by_opentelemetry)

    engine = sqlalchemy.create_engine('sqlite://')
    emit('engine_returns', root.instrument_sqlalchemy_engine(engine) is engine)
    emit('engine_options_return', root.instrument_sqlalchemy_engine(engine, enable_commenter=True,
                                                                    commenter_options={'db_driver': True}) is engine)
    root.instrument_sqlalchemy_engine(engine, enable_commenter=False)  # the same lines again: written once each
    emit('engine_not_an_engine', root.instrument_sqlalchemy_engine('not an engine'))
    root.instrument_sqlalchemy_engine(42)

    app = fastapi.FastAPI()

    @app.get('/hello')
    def hello():
        return 'hi'

    emit('app_returns', root.instrument_fastapi_app(app) is app)
    emit('app_again', root.instrument_fastapi_app(app) is app)
    emit('app_not_an_app', root.instrument_fastapi_app('not an app'))
    root.instrument_fastapi_app(None)
    exporter.clear()
    emit('app_status', asgi_request(app, '/hello').status)
    emit('app_spans', [(s.name, s.kind.name, s.instrumentation_scope.name) for s in exporter.get_finished_spans()])

    emit('system_metrics_returns', root.instrument_system_metrics())
    root.instrument_system_metrics()
    emit('system_metrics_instrumented', SystemMetricsInstrumentor().is_instrumented_by_opentelemetry)

    import dataclasses
    before = dataclasses.dataclass
    emit('dataclasses_returns', [root.instrument_dataclasses(), root.instrument_dataclasses()])
    emit('dataclass_untouched', dataclasses.dataclass is before)

    @dataclasses.dataclass
    class Point:
        x: int

        def norm(self):
            return abs(self.x)

    exporter.clear()
    Point(-3).norm()
    emit('dataclass_spans', span_names())

    emit('all_returns', [root.instrument_all(), root.instrument_all(log_json=False, clobber_other_log_handlers=True),
                         root.instrument_all(log_json=True)])

emit('warnings', [f'{w.category.__name__}: {w.message}' for w in caught])
''')

# an engine through the alias, with no global `instrument_sqlalchemy()`: it is traced, and one not passed in is not
ENGINE = scenario(__name__, 'v0_alias_instrument_sqlalchemy_engine', SINK + r'''
import sqlalchemy

engine = sqlalchemy.create_engine('sqlite://')
control = sqlalchemy.create_engine('sqlite://')
emit('returns', root.instrument_sqlalchemy_engine(engine) is engine)
spans = {}
for name, e in (('engine', engine), ('control', control)):
    exporter.clear()
    with e.connect() as connection:
        connection.execute(sqlalchemy.text('SELECT 1'))
    spans[name] = span_names()
emit('spans', spans)
''')

# `instrument_all()` alone: what `otel.instrument()` does, and v0's switches still choose the parts
ALL_DEFAULT = scenario(__name__, 'v0_alias_instrument_all', SINK + r'''
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor

emit('returns', root.instrument_all())
emit('instrumented', [_config._state.logging_instrumented, RequestsInstrumentor().is_instrumented_by_opentelemetry,
                      SystemMetricsInstrumentor().is_instrumented_by_opentelemetry,
                      SQLAlchemyInstrumentor().is_instrumented_by_opentelemetry])
''')

ALL_SWITCHES = scenario(__name__, 'v0_alias_instrument_all_switches', SINK + r'''
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor

emit('returns', root.instrument_all(dataclasses=False, logging=False, requests=False, sqlalchemy=True,
                                    system_metrics=True))
emit('instrumented', [_config._state.logging_instrumented, RequestsInstrumentor().is_instrumented_by_opentelemetry,
                      SystemMetricsInstrumentor().is_instrumented_by_opentelemetry,
                      SQLAlchemyInstrumentor().is_instrumented_by_opentelemetry])
''')

# a failure inside an alias (here: v1 itself raising, which it never should) is reported, never raised; and an error
# filter on warnings changes nothing, since the alias's line never goes through `warnings`
NEVER_RAISES = scenario(__name__, 'v0_aliases_never_raise', SINK + r'''
import opentelemetry_wrapper._v0_aliases as aliases


class Broken:
    def __call__(self, *args, **kwargs):
        raise RuntimeError('v1 broke')

    def instrument(self, *args, **kwargs):
        raise RuntimeError('v1 broke')


def boom(*args, **kwargs):
    raise RuntimeError('v1 broke')


import fastapi
import sqlalchemy
app = fastapi.FastAPI()
engine = sqlalchemy.create_engine('sqlite://')
warnings.simplefilter('error')
aliases.otel = Broken()
aliases._system_metrics = boom
results = {}
for name, call in {
    'instrument_decorate': lambda: root.instrument_decorate(len) is len,
    'instrument_logging': lambda: root.instrument_logging(print_json=False, unknown_option=1),
    'instrument_requests': lambda: root.instrument_requests(),
    'instrument_sqlalchemy': lambda: root.instrument_sqlalchemy(),
    'instrument_all': lambda: root.instrument_all(),
    'instrument_dataclasses': lambda: root.instrument_dataclasses(),
    'instrument_fastapi_app': lambda: root.instrument_fastapi_app(app) is app,
    'instrument_sqlalchemy_engine': lambda: root.instrument_sqlalchemy_engine(engine) is engine,
    'instrument_system_metrics': lambda: root.instrument_system_metrics(),
}.items():
    try:
        results[name] = call()
    except BaseException as e:
        results[name] = f'raised {type(e).__name__}: {e}'
emit('results', results)
''')

# a v0 app upgraded as it was: v0's environment variables still set, the extras not installed (v0 had them as core
# dependencies), warnings as errors. v1 warns about each of those; through an alias the warnings are stderr lines
UPGRADED_UNDER_W_ERROR = scenario(__name__, 'v0_aliases_upgraded_under_w_error', r'''
import importlib.abc
import sys
import warnings


class Block(importlib.abc.MetaPathFinder):  # the [fastapi] and [sqlalchemy] extras' instrumentations, missing
    def find_spec(self, name, path=None, target=None):
        if name.startswith(('opentelemetry.instrumentation.fastapi', 'opentelemetry.instrumentation.sqlalchemy')):
            raise ModuleNotFoundError(f'No module named {name!r} (blocked)', name=name)
        return None


sys.meta_path.insert(0, Block())
warnings.simplefilter('error')
import fastapi
import sqlalchemy
import opentelemetry_wrapper as root

app = fastapi.FastAPI()
engine = sqlalchemy.create_engine('sqlite://')
results = {}
for name, call in {
    'instrument_all': lambda: root.instrument_all(),
    'instrument_logging': lambda: root.instrument_logging() is not None,
    'instrument_fastapi_app': lambda: root.instrument_fastapi_app(app) is app,
    'instrument_sqlalchemy_engine': lambda: root.instrument_sqlalchemy_engine(engine) is engine,
    'instrument_sqlalchemy': lambda: root.instrument_sqlalchemy(),
}.items():
    try:
        results[name] = call()
    except BaseException as e:
        results[name] = f'raised {type(e).__name__}: {e}'
emit('results', results)
''', env={'OTEL_LOG_LEVEL': 'debug', 'OTEL_EXPORTER_OTLP_INSECURE': 'true'})

# the extras missing, through v1 itself: each warning names the extra to install (v0 had them all as core)
V1_MISSING_EXTRAS = scenario(__name__, 'v1_instrument_missing_extras', r'''
import importlib.abc
import sys
import warnings


class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.startswith(('opentelemetry.instrumentation.fastapi', 'opentelemetry.instrumentation.requests')):
            raise ModuleNotFoundError(f'No module named {name!r} (blocked)', name=name)
        return None


sys.meta_path.insert(0, Block())
import fastapi
import requests
from opentelemetry_wrapper import otel

app = fastapi.FastAPI()
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    emit('returns', [otel.instrument(app) is app, otel.instrument(requests) is requests])
emit('warnings', [str(w.message) for w in caught])
''')

DISABLED = scenario(__name__, 'v0_aliases_disabled', SINK + r'''
def f():
    return 1

import logging
emit('results', [root.instrument_decorate(f) is f, root.instrument_logging(level=10) is logging, root.instrument_all(),
                 root.instrument_dataclasses(), root.instrument_fastapi_app('x')])
''', env={'OTEL_WRAPPER_DISABLED': 'true'})

# the lean install (DEC-96, AC-20): none of v0's dependencies importable. stricter than a real no-extras install,
# where `requests` is present (the OTLP HTTP exporter needs it): the real one is ci/smoke_core.py, in CI's core job
BLOCKED = ('fastapi', 'starlette', 'sqlalchemy', 'requests', 'grpc', 'pydantic', 'psutil')
LEAN = scenario(__name__, 'v0_aliases_lean_install', r'''
import importlib.abc
import sys

BLOCKED = %r


class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split('.')[0] in BLOCKED:
            raise ModuleNotFoundError(f'No module named {name!r} (blocked)', name=name)
        return None


emit('preloaded', sorted(m for m in sys.modules if m.split('.')[0] in BLOCKED))
sys.meta_path.insert(0, Block())

import opentelemetry_wrapper as root
from opentelemetry_wrapper import otel
from opentelemetry_wrapper.v1 import _config
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
exporter = InMemorySpanExporter()
_config.add_span_sink(exporter)


@otel
def decorated():
    return 'otel'


@root.instrument_decorate
def aliased():
    return 'alias'


otel.instrument()
import logging
results = [decorated(), aliased(), root.instrument_logging() is logging, root.instrument_requests(),
           root.instrument_sqlalchemy(), root.instrument_sqlalchemy_engine('e'), root.instrument_fastapi_app('a'),
           root.instrument_system_metrics(), root.instrument_all(sqlalchemy=True), root.instrument_dataclasses()]
emit('results', results)
emit('spans', sorted(s.name for s in exporter.get_finished_spans()))
emit('loaded', sorted(m for m in sys.modules if m.split('.')[0] in BLOCKED))
''' % (BLOCKED,))


def records(result):
    """the stderr JSON lines that are the wrapper's warnings (DEC-81)"""
    out = []
    for line in result.stderr_lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and record.get('opentelemetry_wrapper') == 'warning':
            out.append(record['message'])
    return out


def deprecations(result, name):
    return [m for m in records(result) if m.startswith(f'opentelemetry_wrapper.{name} is deprecated since 1.0.0')]


REPLACEMENTS = {
    'instrument_decorate': 'use @otel',
    'instrument_fastapi_app': 'use otel.instrument(app)',
    'instrument_sqlalchemy': 'use otel.instrument(sqlalchemy)',
    'instrument_sqlalchemy_engine': 'use otel.instrument(engine)',
    'instrument_requests': 'use otel.instrument(requests)',
    'instrument_logging': 'use otel.instrument(logging)',
    'instrument_system_metrics': 'use otel.instrument() (with the [system-metrics] extra)',
    'instrument_all': 'use otel.instrument()',
    'instrument_dataclasses': 'it does nothing: put @otel on the dataclasses you want',
}


def test_the_root_exports_every_alias():
    import opentelemetry_wrapper as root
    assert set(ALIASES) <= set(root.__all__)
    for name in ALIASES:
        alias = getattr(root, name)
        assert callable(alias) and alias.__module__ == 'opentelemetry_wrapper', name


@pytest.mark.parametrize('name', ALIASES)
def test_each_alias_warns_exactly_once_on_stderr_naming_its_replacement(name):
    result = CALLS.result()
    lines = deprecations(result, name)
    assert len(lines) == 1, (lines, result.describe())
    assert 'removed in 2.0' in lines[0] and REPLACEMENTS[name] in lines[0], lines[0]
    assert 'scenario_v0_aliases_called.py:' in lines[0].rpartition('(first used at ')[2], lines[0]  # the caller


def test_the_alias_lines_never_go_through_warnings():  # DEC-81
    result = CALLS.result()
    assert not [w for w in result['warnings'] if 'deprecated' in w or 'ignored' in w], result['warnings']


def test_instrument_decorate_is_otel_in_each_of_v0_s_call_forms():
    result = CALLS.result()
    assert result['results'] == [2, 4, 'partial', 'call', 'method', 'prop']
    assert result['decorate_marks'] == [True, True]
    spans = result['decorate_spans']
    assert spans[:4] == ['__main__.plain', '__main__.again', 'named by partial', 'named by call'], spans
    # a class: its methods, and (as v0 did) its properties
    assert '__main__.Thing.method' in spans and '__main__.Thing.prop' in spans, spans


def test_instrument_logging_is_otel_instrument_logging_and_ignores_v0_s_options():  # DEC-43
    result = CALLS.result()
    assert result['logging_returns'] is True
    logged = [line for line in result.stderr_lines if 'hello from the logging alias' in line]
    assert len(logged) == 1 and json.loads(logged[0]), result.describe()  # v1's one-line JSON on stderr
    ignored = [m for m in records(result) if m.startswith('instrument_logging(): ')]
    assert len(ignored) == 1, records(result)
    assert 'level, path, stream, print_json, clobber_other_log_handlers ignored' in ignored[0]
    assert 'OTEL_WRAPPER_LOG_LEVEL' in ignored[0] and 'OTEL_WRAPPER_LOG_FORMAT=off' in ignored[0]


def test_instrument_requests_and_sqlalchemy_instrument_the_module_and_return_it():
    result = CALLS.result()
    assert result['requests_returns'] is True and result['requests_instrumented'] is True
    assert result['sqlalchemy_returns'] is True and result['sqlalchemy_instrumented'] is True


def test_instrument_sqlalchemy_engine_returns_the_traced_engine_and_ignores_the_commenter_options():  # DEC-91
    result = CALLS.result()
    assert result['engine_returns'] is True and result['engine_options_return'] is True
    assert result['engine_not_an_engine'] == 'not an engine'  # as v0: returned unchanged
    spans = ENGINE.result()['spans']
    assert ENGINE.result()['returns'] is True
    assert [n for n in spans['engine'] if n.startswith('SELECT')] and spans['control'] == [], spans
    ignored = [m for m in records(result) if m.startswith('instrument_sqlalchemy_engine(): ')]
    assert len(ignored) == 1 and 'enable_commenter, commenter_options ignored' in ignored[0], records(result)
    assert 'OTEL_WRAPPER_SQLALCHEMY_COMMENTER' in ignored[0]
    assert len([m for m in records(result) if 'not a SQLAlchemy Engine' in m]) == 1


def test_instrument_fastapi_app_returns_the_instrumented_app():
    result = CALLS.result()
    assert result['app_returns'] is True and result['app_again'] is True
    assert result['app_not_an_app'] == 'not an app'
    assert result['app_status'] == 200
    # the instrumentation's server span (FastAPI makes one of its own too, instrumented or not)
    assert [name for name, kind, scope in result['app_spans']
            if kind == 'SERVER' and scope == 'opentelemetry.instrumentation.fastapi'] == ['GET /hello'], \
        result['app_spans']
    assert len([m for m in records(result) if 'not a FastAPI or Starlette app' in m]) == 1, records(result)


def test_instrument_system_metrics_is_otel_instrument_s_system_metrics_part():
    result = CALLS.result()
    assert result['system_metrics_returns'] is None and result['system_metrics_instrumented'] is True


def test_instrument_dataclasses_does_nothing_but_warn():  # DEC-42
    result = CALLS.result()
    assert result['dataclasses_returns'] == [None, None]
    assert result['dataclass_untouched'] is True
    assert result['dataclass_spans'] == []


def test_instrument_all_is_otel_instrument():
    result = CALLS.result()
    assert result['all_returns'] == [None, None, None]
    ignored = [m for m in records(result) if m.startswith('instrument_all(): ')]
    assert len(ignored) == 1 and 'log_json, clobber_other_log_handlers ignored' in ignored[0], records(result)
    # logging, requests, system metrics; never SQLAlchemy unless asked (DEC-11)
    assert ALL_DEFAULT.result()['returns'] is None
    assert ALL_DEFAULT.result()['instrumented'] == [True, True, True, False]


def test_instrument_all_s_switches_still_choose_the_parts():
    assert ALL_SWITCHES.result()['instrumented'] == [False, False, True, True]


def test_an_alias_never_raises_even_when_v1_fails_and_warnings_are_errors():
    result = NEVER_RAISES.result()
    assert result['results'] == {'instrument_decorate': True, 'instrument_logging': None,
                                 'instrument_requests': None, 'instrument_sqlalchemy': None,
                                 'instrument_all': None, 'instrument_dataclasses': None,
                                 'instrument_fastapi_app': True, 'instrument_sqlalchemy_engine': True,
                                 'instrument_system_metrics': None}, result.describe()
    swallowed = [line for line in result.stderr_lines if 'internal error, swallowed' in line]
    assert swallowed and all('v0 alias' in line for line in swallowed), result.describe()


def test_an_upgraded_v0_app_does_not_crash_under_w_error_and_hears_why_on_stderr():  # DEC-81, DEC-52
    result = UPGRADED_UNDER_W_ERROR.result()
    assert result['results'] == {'instrument_all': None, 'instrument_logging': True, 'instrument_fastapi_app': True,
                                 'instrument_sqlalchemy_engine': True, 'instrument_sqlalchemy': None}, result.describe()
    messages = records(result)
    assert any('OTEL_LOG_LEVEL' in m for m in messages), messages  # v1's own startup warning, as a stderr line
    assert any('OTEL_EXPORTER_OTLP_INSECURE' in m for m in messages), messages
    for extra, caller in (('fastapi', 'instrument_fastapi_app()'), ('sqlalchemy', 'instrument_sqlalchemy_engine()'),
                          ('sqlalchemy', 'instrument_sqlalchemy()')):
        assert [m for m in messages if m.startswith(f'{caller} did nothing') and f'opentelemetry_wrapper[{extra}]' in m
                ], (caller, messages)


def test_v1_names_the_missing_extra_for_an_app_and_for_requests():
    result = V1_MISSING_EXTRAS.result()
    assert result['returns'] == [True, True]
    caught = result['warnings']
    for what, extra in (('app', 'fastapi'), ('requests', 'requests')):
        assert [w for w in caught if w.startswith(f'otel.instrument({what}) did nothing')
                and w.endswith(f'Install opentelemetry_wrapper[{extra}]')], (what, caught)


def test_disabled_aliases_are_silent_and_return_what_they_were_given():
    result = DISABLED.result()
    assert result['results'] == [True, True, None, None, 'x']  # v1's own: the target back, untouched
    assert records(result) == [], result.describe()


@pytest.mark.criterion('AC-20')
def test_the_package_runs_with_none_of_v0_s_dependencies_importable():  # DEC-96: the lean install
    result = LEAN.result()
    assert result['preloaded'] == []
    assert result['results'] == ['otel', 'alias', True, None, None, 'e', 'a', None, None, None], result.describe()
    assert result['spans'] == ['__main__.aliased', '__main__.decorated']
    assert result['loaded'] == []
    for name in ('instrument_requests', 'instrument_sqlalchemy', 'instrument_system_metrics'):
        assert any(m.startswith(f'{name}() did nothing') for m in records(result)), (name, records(result))
    # v0's instrument_all() instrumented requests and system metrics: the alias says they are not
    assert 'instrument_all(): requests and system-metrics not instrumented: Install '            'opentelemetry_wrapper[requests,system-metrics]' in [m.partition(' (first used at ')[0] for m in records(result)]
