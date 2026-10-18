"""
v1's environment variables (in-process: `_env.resolve` is pure): explicit > env > default (DEC-27), exporters only
with an endpoint (DEC-28), v0's old names for one release (DEC-52, DEC-59), the disabled switch (DEC-24, DEC-5)
"""
import pytest

from tests import impl

if impl.IMPL == 'v1':
    impl.import_v1()  # under v1 the package root must not import v0 (see tests/impl.py)
from opentelemetry_wrapper.v1 import _env  # noqa: E402


def resolve(explicit=None, **environ):
    return _env.resolve(explicit or {}, environ)


def test_defaults_build_no_exporters():  # AC-3 (DEC-28)
    settings, notes = resolve()
    assert notes == []
    assert (settings.traces_exporter, settings.metrics_exporter, settings.logs_exporter) == ((), (), ())
    assert (settings.log_level, settings.log_format, settings.prometheus_path) == ('info', 'json', '/metrics')


def test_an_endpoint_turns_on_otlp_per_signal_and_the_exporter_variables_choose():  # AC-3 (DEC-28)
    settings, _ = resolve(OTEL_EXPORTER_OTLP_ENDPOINT='http://collector:4318', OTEL_METRICS_EXPORTER='none',
                          OTEL_LOGS_EXPORTER='console,otlp')
    assert settings.traces_exporter == ('otlp',)
    assert settings.metrics_exporter == ()
    assert settings.logs_exporter == ('console', 'otlp')
    settings, _ = resolve(OTEL_EXPORTER_OTLP_LOGS_ENDPOINT='http://collector:4318/v1/logs')
    assert (settings.traces_exporter, settings.logs_exporter) == ((), ('otlp',))


def test_explicit_beats_env():  # AC-3 (DEC-27 rule 2)
    settings, _ = resolve({'log_level': 'WARNING', 'traces_exporter': ['console']},
                          OTEL_WRAPPER_LOG_LEVEL='debug', OTEL_TRACES_EXPORTER='otlp')
    assert (settings.log_level, settings.traces_exporter) == ('warning', ('console',))


def test_same_meaning_compares_equal_and_the_log_level_is_set_apart():  # AC-3 (DEC-27, DEC-9)
    a, _ = resolve({'otlp_headers': {'b': '2', 'a': '1'}, 'log_level': 'debug'})
    b, _ = resolve({'otlp_headers': {'a': '1', 'b': '2'}})
    assert a != b and a.without_log_level() == b.without_log_level()


@pytest.mark.parametrize('old, new, value, field, expected', [
    ('OTEL_SERVICE_NAMESPACE', 'OTEL_RESOURCE_ATTRIBUTES', 'shop', 'resource_attributes',
     (('service.namespace', 'shop'),)),
    ('OTEL_EXPORTER_OTLP_HEADER', 'OTEL_EXPORTER_OTLP_HEADERS', 'Authorization=Basic abc==\tx-team=a',
     'otlp_headers', (('Authorization', 'Basic abc=='), ('x-team', 'a'))),
    ('OTEL_EXPORTER_PROMETHEUS_ENDPOINT', 'OTEL_WRAPPER_PROMETHEUS_PATH', '/prom', 'prometheus_path', '/prom'),
    ('OTEL_HEADER_ATTRIBUTES', 'OTEL_WRAPPER_HEADER_ATTRIBUTES', 'X-A,x-b', 'header_attributes', ('x-a', 'x-b')),
])
def test_v0_names_are_read_for_one_release_with_a_warning(old, new, value, field, expected):  # AC-27 (DEC-52)
    settings, notes = resolve(**{old: value})
    assert getattr(settings, field) == expected
    assert len(notes) == 1 and notes[0].startswith(old) and new in notes[0]


def test_a_new_name_beats_the_old_one():  # AC-27 (DEC-59)
    settings, notes = resolve(OTEL_EXPORTER_PROMETHEUS_ENDPOINT='/old', OTEL_WRAPPER_PROMETHEUS_PATH='/new')
    assert settings.prometheus_path == '/new' and len(notes) == 1


def test_v0s_log_level_name_only_warns():  # AC-27 (DEC-52)
    settings, notes = resolve(OTEL_LOG_LEVEL='debug')
    assert settings.log_level == 'info'
    assert len(notes) == 1 and 'OTEL_WRAPPER_LOG_LEVEL' in notes[0]
    assert resolve(OTEL_LOG_LEVEL='debug', OTEL_WRAPPER_LOG_LEVEL='error')[1] == []


@pytest.mark.parametrize('environ', [
    {'OTEL_EXPORTER_OTLP_ENDPOINT': 'http://collector:4317'},
    {'OTEL_EXPORTER_OTLP_METRICS_ENDPOINT': 'grpc://collector:1234'},
    {'OTEL_EXPORTER_OTLP_PROTOCOL': 'grpc'},
    {'OTEL_EXPORTER_OTLP_TRACES_PROTOCOL': 'GRPC'},
    {'OTEL_EXPORTER_OTLP_INSECURE': 'true'},
], ids=lambda e: ','.join(e))
def test_grpc_settings_warn(environ):  # AC-27 (DEC-52)
    assert len(resolve(**environ)[1]) == 1


def test_an_explicit_grpc_endpoint_warns_and_http_does_not():  # AC-27
    assert len(resolve({'otlp_endpoint': 'localhost:4317'})[1]) == 1
    assert resolve({'otlp_endpoint': 'https://collector:4318'})[1] == []


@pytest.mark.parametrize('environ, expected', [
    ({}, False),
    ({'OTEL_WRAPPER_DISABLED': 'true'}, True),
    ({'OTEL_WRAPPER_DISABLED': ' TRUE '}, True),
    ({'OTEL_WRAPPER_DISABLED': 'false'}, False),
    ({'OTEL_SDK_DISABLED': 'true'}, True),
    ({'OTEL_SDK_DISABLED': 'false'}, False),
])
def test_disabled_switch(environ, expected):  # AC-4 (DEC-24, DEC-5)
    assert _env.disabled(environ) is expected


def test_an_unknown_configure_option_is_a_type_error():  # AC-3 (typed signature)
    with pytest.raises(TypeError, match='servce_name'):
        resolve({'servce_name': 'x'})
