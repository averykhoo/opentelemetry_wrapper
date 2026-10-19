"""
v1's configuration (DEC-27, DEC-28, DEC-9): explicit and implicit, final once built, someone else configured first,
the read-only view, the scrubbing hook, and v0's old variable names (DEC-52, DEC-59)
"""
import os
import shutil
from pathlib import Path

import pytest

from tests.v0._harness import scenario
from tests.v1._prelude import PRELUDE

FINAL = scenario(__name__, 'v1_config_final', PRELUDE + r'''
import logging
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    otel.configure(service_name='explicit', otlp_headers={'Authorization': 'Basic c2VjcmV0'})
    emit('first', otel_warnings(caught)); caught.clear()
    otel.configure(service_name='explicit', otlp_headers={'Authorization': 'Basic c2VjcmV0'})
    emit('same_again', otel_warnings(caught)); caught.clear()
    otel.configure(service_name='different')
    otel.configure(service_name='different again')
    emit('different', otel_warnings(caught)); caught.clear()
    otel.instrument(logging)
    otel.configure(service_name='explicit', otlp_headers={'Authorization': 'Basic c2VjcmV0'}, log_level='debug')
    emit('log_level_only', otel_warnings(caught))
emit('root_level', logging.getLevelName(logging.getLogger().level))

@otel
def f():
    pass

f()
(span,) = exporter.get_finished_spans()
emit('service_name', span.resource.attributes['service.name'])
view = otel.config
emit('view', [view['service_name'], view['otlp_headers'], 'c2VjcmV0' in repr(dict(view))])
try:
    view['service_name'] = 'x'
except TypeError:
    emit('read_only', True)
''', env={'OTEL_SERVICE_NAME': 'from-env'})


@pytest.mark.criterion('AC-3')
def test_explicit_beats_env_and_configuration_is_final_once_built():  # AC-3 (DEC-27 rule 2)
    result = FINAL.result()
    assert result['first'] == [] and result['same_again'] == []
    assert len(result['different']) == 1 and 'ignored' in result['different'][0]
    assert result['service_name'] == 'explicit'


@pytest.mark.criterion('AC-3')
def test_only_the_log_level_may_change_after_configuration():  # AC-3 (DEC-9)
    result = FINAL.result()
    assert result['log_level_only'] == []
    assert result['root_level'] == 'DEBUG'


def test_the_config_view_is_read_only_and_redacts_secrets():  # DEC-27 rule 4
    result = FINAL.result()
    assert result['view'] == ['explicit', [['Authorization', '[REDACTED]']], False]
    assert result['read_only'] is True


IMPLICIT = scenario(__name__, 'v1_config_implicit', PRELUDE + r'''
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

@otel
def f():
    pass

emit('before', [_config.is_configured(), type(trace.get_tracer_provider()).__name__])
f()
emit('after', [_config.is_configured(), isinstance(trace.get_tracer_provider(), TracerProvider)])
(span,) = exporter.get_finished_spans()
emit('service_name', span.resource.attributes['service.name'])
emit('exporters', len(_config._state.sinks))
''', env={'OTEL_SERVICE_NAME': 'from-env'})


@pytest.mark.criterion('AC-3')
def test_the_first_span_configures_from_env_vars_and_exports_nothing_without_an_endpoint():  # AC-3 (DEC-27, DEC-28)
    result = IMPLICIT.result()
    assert result['before'] == [False, 'ProxyTracerProvider']
    assert result['after'] == [True, True]
    assert result['service_name'] == 'from-env'
    assert result['exporters'] == 0


ENDPOINT = scenario(__name__, 'v1_config_endpoint', PRELUDE + r'''
otel.configure()
emit('count', len(_config._state.sinks))
_config.set_exporters_enabled(False)  # nothing to send, and nothing listens on the endpoint
''', env={'OTEL_EXPORTER_OTLP_ENDPOINT': 'http://127.0.0.1:9', 'OTEL_METRICS_EXPORTER': 'none'})


@pytest.mark.criterion('AC-3')
def test_an_endpoint_turns_on_the_otlp_exporters():  # AC-3 (DEC-28)
    result = ENDPOINT.result()
    assert result['count'] == 2  # traces and logs; metrics switched off by OTEL_METRICS_EXPORTER=none


SOMEONE_ELSE_SDK = scenario(__name__, 'v1_config_someone_else_sdk', r'''
import warnings
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
theirs = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(theirs))
trace.set_tracer_provider(provider)
''' + PRELUDE + r'''
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    otel.configure()  # explicit: implicit configuration reports to stderr instead (DEC-81)
    @otel
    def f():
        return 1
    emit('result', f())
    emit('warnings', otel_warnings(caught))
emit('provider_kept', trace.get_tracer_provider() is provider)
emit('spans', [len(theirs.get_finished_spans()), len(exporter.get_finished_spans())])
''')

SOMEONE_ELSE_FOREIGN = scenario(__name__, 'v1_config_someone_else_foreign', r'''
import warnings
from opentelemetry import trace
provider = trace.NoOpTracerProvider()
trace.set_tracer_provider(provider)
''' + PRELUDE + r'''
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    otel.configure()  # explicit: implicit configuration reports to stderr instead (DEC-81)
    @otel
    def f():
        return 1
    emit('result', f())
    with otel('x') as span:
        emit('span_is_recording', span.is_recording())
    emit('warnings', otel_warnings(caught))
emit('provider_kept', trace.get_tracer_provider() is provider)
''')


@pytest.mark.criterion('AC-3')
def test_an_sdk_provider_configured_first_gets_our_processors_attached():  # AC-3 (DEC-27 rule 5)
    result = SOMEONE_ELSE_SDK.result()
    assert result['result'] == 1 and result['provider_kept'] is True
    assert result['spans'] == [1, 1]  # their pipeline and ours both see the span
    assert len([w for w in result['warnings'] if 'tracer provider (TracerProvider)' in w]) == 1


@pytest.mark.criterion('AC-3')
def test_a_foreign_provider_configured_first_is_left_alone_without_a_crash():  # AC-3 (DEC-27 rule 5)
    result = SOMEONE_ELSE_FOREIGN.result()
    assert result['result'] == 1 and result['provider_kept'] is True
    assert result['span_is_recording'] is False
    assert len([w for w in result['warnings'] if 'leaves it alone' in w]) == 1


SCRUBBING_HOOK = scenario(__name__, 'v1_config_scrubbing_hook', PRELUDE + r'''
import sys, types
from importlib.machinery import ModuleSpec
sentinel = object()
_config.SCRUBBING_MODULE = 'opentelemetry_wrapper.v1._no_such_scrubbing_module'
emit('absent_is_pass_through', _config._wrap_exporter(sentinel, 'traces') is sentinel)

fake = types.ModuleType('fake_scrubbing')
fake.__spec__ = ModuleSpec('fake_scrubbing', None)
fake.ScrubbingSpanExporter = lambda inner: ('span', inner)
fake.ScrubbingLogExporter = lambda inner: ('log', inner)
sys.modules['fake_scrubbing'] = fake
_config.SCRUBBING_MODULE = 'fake_scrubbing'
emit('present', [_config._wrap_exporter(sentinel, 'traces') == ('span', sentinel),
                 _config._wrap_exporter(sentinel, 'logs') == ('log', sentinel),
                 _config._wrap_exporter(sentinel, 'metrics') is sentinel])

def broken(inner):
    raise RuntimeError('scrubber failed')

fake.ScrubbingSpanExporter = broken
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    otel.configure(traces_exporter=['console'])
    emit('warnings', otel_warnings(caught))
emit('exporters', len(_config._state.sinks))  # fail closed: the console exporter is dropped, never unscrubbed
''')


@pytest.mark.criterion('AC-5')
@pytest.mark.criterion('AC-13')
def test_every_exporter_goes_through_the_scrubbing_hook_which_fails_closed():  # AC-5 (scrubbed), OTW-8 hook
    result = SCRUBBING_HOOK.result()
    assert result['absent_is_pass_through'] is True
    assert result['present'] == [True, True, True]
    assert result['exporters'] == 0
    failed = [w for w in result['warnings'] if 'scrubber failed' in w]  # the console exporter and the test sink
    assert len(failed) == 2 and 'ConsoleSpanExporter' in failed[0] and 'InMemorySpanExporter' in failed[1]


MIGRATION = scenario(__name__, 'v1_config_migration', PRELUDE + r'''
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    otel.configure()  # explicit: implicit configuration reports to stderr instead (DEC-81)
    @otel
    def f():
        pass
    f()
    emit('warnings', otel_warnings(caught))
(span,) = exporter.get_finished_spans()
emit('namespace', span.resource.attributes.get('service.namespace'))
emit('log_level', otel.config['log_level'])
''', env={'OTEL_SERVICE_NAMESPACE': 'shop', 'OTEL_LOG_LEVEL': 'debug', 'OTEL_EXPORTER_OTLP_INSECURE': 'true',
          'OTEL_EXPORTER_OTLP_PROTOCOL': 'grpc', 'OTEL_EXPORTER_OTLP_TRACES_ENDPOINT': 'http://127.0.0.1:4317',
          'OTEL_TRACES_EXPORTER': 'none'})


@pytest.mark.criterion('AC-27')
def test_v0_names_are_read_with_a_warning_and_grpc_settings_warn_at_configuration():  # AC-27 (DEC-52, DEC-59)
    result = MIGRATION.result()
    assert result['namespace'] == 'shop'
    assert result['log_level'] == 'info'  # OTEL_LOG_LEVEL only warns
    warnings = result['warnings']
    for expected in ('OTEL_SERVICE_NAMESPACE', 'OTEL_LOG_LEVEL', 'OTEL_EXPORTER_OTLP_INSECURE',
                     'OTEL_EXPORTER_OTLP_PROTOCOL=grpc', 'OTEL_EXPORTER_OTLP_TRACES_ENDPOINT'):
        assert len([w for w in warnings if w.startswith(expected)]) == 1, (expected, warnings)
    assert len(warnings) == 5


# ----------------------------------------------------------------------------------------------------------------------
# review fixes (OTW-3, session 2026-10-18l)
# ----------------------------------------------------------------------------------------------------------------------

PARTIAL_BUILD = scenario(__name__, 'v1_config_partial_build', PRELUDE + r'''
import opentelemetry.exporter.otlp.proto.http.trace_exporter as trace_exporter
import opentelemetry.sdk._logs as sdk_logs


class Broken:
    def __init__(self, *args, **kwargs):
        raise RuntimeError('exporter constructor failed')


def broken_logger_provider(*args, **kwargs):
    raise RuntimeError('logger provider failed')


trace_exporter.OTLPSpanExporter = Broken  # one exporter of the traces signal
sdk_logs.LoggerProvider = broken_logger_provider  # the whole logs signal
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    otel.configure()
    emit('warnings', otel_warnings(caught))
state = _config._state
emit('state', [state.failed, len(state.owned), state.tracer_provider is not None, state.meter_provider is not None,
               state.logger_provider is None])
emit('exit_flush', len(_config._fork_hooks))


@otel
def f():
    pass


f()
emit('spans', len(exporter.get_finished_spans()))
''', env={'OTEL_TRACES_EXPORTER': 'otlp', 'OTEL_LOGS_EXPORTER': 'console', 'OTEL_METRICS_EXPORTER': 'none'})


def test_one_failing_exporter_or_signal_keeps_the_rest_built_and_flushed_at_exit():  # AC-7 (DEC-49)
    result = PARTIAL_BUILD.result()
    warnings = result['warnings']
    assert len(warnings) == 2, warnings
    assert any('exporter constructor failed' in w for w in warnings)
    assert any('logger provider failed' in w for w in warnings)
    # not failed; the tracer and meter providers are ours and owned (so flushed); the logs signal is skipped
    assert result['state'] == [False, 2, True, True, True]
    assert result['exit_flush'] == 1
    assert result['spans'] == 1  # the span still reaches the test sink


METRICS_SWITCH = scenario(__name__, 'v1_config_metrics_switch', PRELUDE + r'''
import opentelemetry.sdk.metrics.export as mexport
from opentelemetry import metrics


class Recording(mexport.ConsoleMetricExporter):
    exports = 0

    def export(self, metrics_data, timeout_millis=10_000, **kwargs):
        Recording.exports += 1
        return mexport.MetricExportResult.SUCCESS


mexport.ConsoleMetricExporter = Recording
otel.configure()
counter = metrics.get_meter('test').create_counter('c')


def exports_after_a_flush():
    before = Recording.exports
    counter.add(1)
    _config._state.meter_provider.force_flush()
    return Recording.exports - before


_config.set_exporters_enabled(False)
emit('off', exports_after_a_flush())
_config.set_exporters_enabled(True)
emit('on', exports_after_a_flush())
''', env={'OTEL_METRICS_EXPORTER': 'console'})


def test_switching_exporters_off_stops_the_metric_exporters_too():  # AC-3 (DEC-27 rule 3, DEC-10)
    result = METRICS_SWITCH.result()
    assert result['off'] == 0
    assert result['on'] >= 1


FOREIGN_ALL = scenario(__name__, 'v1_config_foreign_all', r'''
from opentelemetry import _logs, metrics, trace
trace.set_tracer_provider(trace.NoOpTracerProvider())
_logs.set_logger_provider(_logs.NoOpLoggerProvider())
metrics.set_meter_provider(metrics.NoOpMeterProvider())
''' + PRELUDE + r'''
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    otel.configure()
    emit('warnings', otel_warnings(caught))
''')


@pytest.mark.criterion('AC-3')
def test_foreign_providers_for_several_signals_give_one_warning_naming_them():  # AC-3 (DEC-27 rule 5)
    (warning,) = FOREIGN_ALL.result()['warnings']
    assert 'tracer' in warning and 'logger' in warning and 'meter' in warning


DEDUPE = scenario(__name__, 'v1_config_warning_dedupe', PRELUDE + r'''
from opentelemetry_wrapper.v1 import _decorator
raised = 0
with warnings.catch_warnings():
    warnings.simplefilter('error', v1.OtelWrapperWarning)
    for _ in range(3):
        try:
            _decorator.decorate(42)  # not callable: a warning at decoration time, the same site every time
        except v1.OtelWrapperWarning:
            raised += 1
emit('raised', raised)
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    for _ in range(2):
        _decorator.decorate(42)
    emit('recorded', len(otel_warnings(caught)))
''')


def test_a_repeated_misuse_under_an_error_filter_keeps_raising_at_decoration_time():  # AC-7 (DEC-49)
    result = DEDUPE.result()
    assert result['raised'] == 3  # the key is only recorded once the warning was actually issued
    assert result['recorded'] == 1  # and a warning that was issued is deduplicated as before


BAD_CONFIGURE = scenario(__name__, 'v1_config_bad_arguments', PRELUDE + r'''
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    otel.configure(log_level='loud', service_name=5, otlp_headers=7, traces_exporter=3)
    emit('warnings', otel_warnings(caught))
    otel.configure(log_level=9)  # after the build: only the log level can change, and it must not raise either
emit('view', [otel.config['log_level'], otel.config['service_name']])
''')


def test_wrong_arguments_to_configure_warn_and_fall_back_without_raising():  # AC-7 (DEC-49)
    result = BAD_CONFIGURE.result()
    warnings = result['warnings']
    for option in ('log_level', 'service_name', 'otlp_headers', 'traces_exporter'):
        assert len([w for w in warnings if option in w]) == 1, (option, warnings)
    assert result['view'] == ['info', None]


NORMALISED = scenario(__name__, 'v1_config_normalised', PRELUDE + r'''
none = dict(traces_exporter='none', metrics_exporter='none', logs_exporter='none')
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    otel.configure(service_name=' svc ', otlp_endpoint=' http://127.0.0.1:4318/ ', **none)
    otel.configure(service_name='svc', otlp_endpoint='http://127.0.0.1:4318', **none)
    emit('warnings', otel_warnings(caught))
emit('view', [otel.config['service_name'], otel.config['otlp_endpoint']])
''')


def test_endpoint_and_service_name_are_normalised_before_the_same_arguments_comparison():  # AC-3 (DEC-27 rule 2)
    result = NORMALISED.result()
    assert result['warnings'] == []
    assert result['view'] == ['svc', 'http://127.0.0.1:4318']


# the bounded shutdown (workstream 9): a hanging exporter must not hold up the exit longer than the bound

SHUTDOWN = scenario(__name__, 'v1_config_bounded_shutdown', PRELUDE + r'''
import atexit
import time
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult


class Hanging(SpanExporter):
    def export(self, spans):
        return SpanExportResult.SUCCESS

    def shutdown(self):
        time.sleep(30)


started = []
emit('default_bound', _config.SHUTDOWN_TIMEOUT_SECONDS)
_config.SHUTDOWN_TIMEOUT_SECONDS = 1.0  # the real bound is 5 s: the same code path, a quicker test
_config.add_span_sink(Hanging())
atexit.register(lambda: emit('elapsed', time.monotonic() - started[0]))  # atexit is last in, first out: runs last
otel.configure()  # registers the bounded shutdown
atexit.register(lambda: started.append(time.monotonic()))  # so this one runs just before it
''')


def test_a_hanging_exporter_does_not_block_exit_longer_than_the_bound():  # AC-22 (workstream 9)
    result = SHUTDOWN.result()
    assert result['default_bound'] == 5.0
    assert 0.9 <= result['elapsed'] < 4.0, result['elapsed']  # waited for the bound, not for the 30 s


_FLUSH_MARKER = r'''
import multiprocessing
import multiprocessing.util
import os
import tempfile
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

marker = os.path.join(tempfile.mkdtemp(), 'shutdowns')


class Marker(SpanExporter):
    def export(self, spans):
        return SpanExportResult.SUCCESS

    def shutdown(self):
        with open(marker, 'a') as f:
            f.write(f'{os.getpid()}\n')


_config.add_span_sink(Marker())
otel.configure()
emit('marker', marker)
emit('parent', os.getpid())
'''

FORK_FLUSH = scenario(__name__, 'v1_config_fork_flush', PRELUDE + _FLUSH_MARKER + r'''
child = multiprocessing.get_context('fork').Process(target=lambda: None)  # no atexit in it: it ends with os._exit
child.start()
child.join()
emit('child', [child.pid, child.exitcode])
''') if hasattr(os, 'fork') else None

FINALIZERS = scenario(__name__, 'v1_config_finalizers', PRELUDE + _FLUSH_MARKER + r'''
multiprocessing.util._run_after_forkers()  # what `Process._bootstrap` does first in a forked child
multiprocessing.util._exit_function()  # and last: the finalizers, where the flush is registered
emit('flushed', open(marker).read().split() if os.path.exists(marker) else [])
''')


def test_the_finalizer_a_forked_child_runs_flushes_the_providers():  # AC-22 (workstream 9); simulated, any platform
    result = FINALIZERS.result()
    assert result['flushed'] == [str(result['parent'])]
    shutil.rmtree(Path(result['marker']).parent, ignore_errors=True)


@pytest.mark.skipif(not hasattr(os, 'fork'), reason='no fork on this platform (Linux CI runs it)')
def test_a_forked_child_flushes_its_providers_when_it_ends():  # AC-22 (workstream 9)
    result = FORK_FLUSH.result()
    child_pid, exitcode = result['child']
    assert exitcode == 0
    marker = Path(result['marker'])
    lines = marker.read_text().split() if marker.exists() else []
    assert str(child_pid) in lines  # the child's own flush, though a forked child skips atexit
    assert str(result['parent']) in lines  # and the parent's, at its exit
    shutil.rmtree(Path(result['marker']).parent, ignore_errors=True)


# ----------------------------------------------------------------------------------------------------------------------
# the scrubbing engine (OTW-8, DEC-83): configure picks 'auto', hyperscan when importable
# ----------------------------------------------------------------------------------------------------------------------

AUTO_ENGINE = scenario(__name__, 'v1_config_auto_engine', PRELUDE + r'''
from opentelemetry_wrapper.v1 import scrubbing
emit('before', type(scrubbing.default_scrubber()._m).__name__)  # the stock default, built on first use: `re`
otel.configure()
emit('after', type(scrubbing.default_scrubber()._m).__name__)
emit('scrubs', scrubbing.scrub_text('password=hunter2 ' * 3))
''')

NO_HYPERSCAN = scenario(__name__, 'v1_config_auto_engine_without_hyperscan', PRELUDE + r'''
import sys
sys.modules['hyperscan'] = None  # as if it were not installed
from opentelemetry_wrapper.v1 import scrubbing
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    otel.configure()
    emit('warnings', otel_warnings(caught))
emit('after', type(scrubbing.default_scrubber()._m).__name__)
''')

OWN_SCRUBBER = scenario(__name__, 'v1_config_own_scrubber_kept', PRELUDE + r'''
from opentelemetry_wrapper.v1 import scrubbing
mine = scrubbing.Scrubber(allow_keys=['password'])
scrubbing.set_default_scrubber(mine)
otel.configure()
emit('kept', scrubbing.default_scrubber() is mine)
''')


def test_configure_uses_the_auto_scrubbing_engine():  # OTW-8 (DEC-83)
    import importlib.util
    result = AUTO_ENGINE.result()
    assert result['before'] == '_ReMatcher'
    assert result['after'] == ('_HsMatcher' if importlib.util.find_spec('hyperscan') else '_ReMatcher')
    assert 'hunter2' not in result['scrubs']


def test_the_auto_engine_falls_back_to_re_without_hyperscan_and_without_a_warning():  # OTW-8 (DEC-83)
    result = NO_HYPERSCAN.result()
    assert result['after'] == '_ReMatcher' and result['warnings'] == []


def test_a_scrubber_the_app_set_is_not_replaced_by_configure():  # OTW-8 (DEC-83)
    assert OWN_SCRUBBER.result()['kept'] is True
