"""
v1's configuration (DEC-27, DEC-28, DEC-9): explicit and implicit, final once built, someone else configured first,
the read-only view, the scrubbing hook, and v0's old variable names (DEC-52, DEC-59)
"""
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


def test_explicit_beats_env_and_configuration_is_final_once_built():  # AC-3 (DEC-27 rule 2)
    result = FINAL.result()
    assert result['first'] == [] and result['same_again'] == []
    assert len(result['different']) == 1 and 'ignored' in result['different'][0]
    assert result['service_name'] == 'explicit'


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
    @otel
    def f():
        return 1
    emit('result', f())
    with otel('x') as span:
        emit('span_is_recording', span.is_recording())
    emit('warnings', otel_warnings(caught))
emit('provider_kept', trace.get_tracer_provider() is provider)
''')


def test_an_sdk_provider_configured_first_gets_our_processors_attached():  # AC-3 (DEC-27 rule 5)
    result = SOMEONE_ELSE_SDK.result()
    assert result['result'] == 1 and result['provider_kept'] is True
    assert result['spans'] == [1, 1]  # their pipeline and ours both see the span
    assert len([w for w in result['warnings'] if 'tracer provider was configured first' in w]) == 1


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


def test_v0_names_are_read_with_a_warning_and_grpc_settings_warn_at_configuration():  # AC-27 (DEC-52, DEC-59)
    result = MIGRATION.result()
    assert result['namespace'] == 'shop'
    assert result['log_level'] == 'info'  # OTEL_LOG_LEVEL only warns
    warnings = result['warnings']
    for expected in ('OTEL_SERVICE_NAMESPACE', 'OTEL_LOG_LEVEL', 'OTEL_EXPORTER_OTLP_INSECURE',
                     'OTEL_EXPORTER_OTLP_PROTOCOL=grpc', 'OTEL_EXPORTER_OTLP_TRACES_ENDPOINT'):
        assert len([w for w in warnings if w.startswith(expected)]) == 1, (expected, warnings)
    assert len(warnings) == 5
