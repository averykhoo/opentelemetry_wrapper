"""
v1's environment variables (in-process: `_env.resolve` is pure): explicit > env > default (DEC-27), exporters only
with an endpoint (DEC-28), v0's old names for one release (DEC-52, DEC-59), the disabled switch (DEC-24, DEC-5)
"""
import pytest

from opentelemetry_wrapper.v1 import _env


def resolve(explicit=None, **environ):
    return _env.resolve(explicit or {}, environ)


@pytest.mark.criterion('AC-3')
def test_defaults_build_no_exporters():  # AC-3 (DEC-28)
    settings, notes = resolve()
    assert notes == []
    assert (settings.traces_exporter, settings.metrics_exporter, settings.logs_exporter) == ((), (), ())
    assert (settings.log_level, settings.log_format, settings.prometheus_path) == ('info', 'json', '/metrics')


@pytest.mark.criterion('AC-3')
def test_an_endpoint_turns_on_otlp_per_signal_and_the_exporter_variables_choose():  # AC-3 (DEC-28)
    settings, _ = resolve(OTEL_EXPORTER_OTLP_ENDPOINT='http://collector:4318', OTEL_METRICS_EXPORTER='none',
                          OTEL_LOGS_EXPORTER='console,otlp')
    assert settings.traces_exporter == ('otlp',)
    assert settings.metrics_exporter == ()
    assert settings.logs_exporter == ('console', 'otlp')
    settings, _ = resolve(OTEL_EXPORTER_OTLP_LOGS_ENDPOINT='http://collector:4318/v1/logs')
    assert (settings.traces_exporter, settings.logs_exporter) == ((), ('otlp',))


@pytest.mark.criterion('AC-3')
def test_explicit_beats_env():  # AC-3 (DEC-27 rule 2)
    settings, _ = resolve({'log_level': 'WARNING', 'traces_exporter': ['console']},
                          OTEL_WRAPPER_LOG_LEVEL='debug', OTEL_TRACES_EXPORTER='otlp')
    assert (settings.log_level, settings.traces_exporter) == ('warning', ('console',))


@pytest.mark.criterion('AC-3')
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
@pytest.mark.criterion('AC-27')
def test_v0_names_are_read_for_one_release_with_a_warning(old, new, value, field, expected):  # AC-27 (DEC-52)
    settings, notes = resolve(**{old: value})
    assert getattr(settings, field) == expected
    assert len(notes) == 1 and notes[0].startswith(old) and new in notes[0]


@pytest.mark.criterion('AC-27')
def test_a_new_name_beats_the_old_one():  # AC-27 (DEC-59)
    settings, notes = resolve(OTEL_EXPORTER_PROMETHEUS_ENDPOINT='/old', OTEL_WRAPPER_PROMETHEUS_PATH='/new')
    assert settings.prometheus_path == '/new' and len(notes) == 1


@pytest.mark.criterion('AC-27')
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
@pytest.mark.criterion('AC-27')
def test_grpc_settings_warn(environ):  # AC-27 (DEC-52)
    assert len(resolve(**environ)[1]) == 1


@pytest.mark.criterion('AC-27')
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
@pytest.mark.criterion('AC-4')
def test_disabled_switch(environ, expected):  # AC-4 (DEC-24, DEC-5)
    assert _env.disabled(environ) is expected


def test_an_unknown_configure_option_is_a_type_error():  # AC-3 (typed signature)
    with pytest.raises(TypeError, match='servce_name'):
        resolve({'servce_name': 'x'})


# review fixes (OTW-3, session 2026-10-18l)

def test_wrong_types_and_an_invalid_log_level_warn_and_fall_back_without_raising():  # AC-7 (DEC-49)
    bad = {'log_level': 'loud', 'service_name': 5, 'otlp_headers': 7, 'traces_exporter': 3, 'prometheus_path': 9,
           'header_attributes': 4, 'resource_attributes': 'x', 'otlp_endpoint': ['a'], 'log_format': 1}
    settings, notes = resolve(bad)
    assert settings == resolve()[0]  # every one of them fell back to what it would have been without it
    assert len(notes) == len(bad)
    for option in bad:
        assert len([n for n in notes if option in n]) == 1, (option, notes)


def test_an_invalid_log_level_from_the_environment_warns_and_falls_back():  # AC-7 (DEC-49)
    settings, notes = resolve(OTEL_WRAPPER_LOG_LEVEL='loud')
    assert settings.log_level == 'info'
    assert len(notes) == 1 and 'loud' in notes[0]
    settings, notes = resolve({'log_level': 'loud'}, OTEL_WRAPPER_LOG_LEVEL='debug')
    assert settings.log_level == 'debug' and len(notes) == 1  # the explicit value is ignored, not the environment
    assert resolve({'log_level': 'Warn'}) == (resolve()[0].__class__(log_level='warn'), [])


def test_endpoint_and_service_name_are_normalised():  # AC-3 (DEC-27 rule 2)
    a, _ = resolve({'service_name': ' svc ', 'otlp_endpoint': ' http://h:4318/ '})
    b, _ = resolve({'service_name': 'svc', 'otlp_endpoint': 'http://h:4318'})
    assert a == b and (a.service_name, a.otlp_endpoint) == ('svc', 'http://h:4318')
    assert resolve({'service_name': '  ', 'otlp_endpoint': ' / '})[0] == resolve()[0]


# Prometheus (workstream 9, OTW-12)

@pytest.mark.criterion('AC-19')
def test_prometheus_host_and_port():  # AC-19 (DEC-59): the host is read, so k8s can bind 0.0.0.0
    settings, notes = resolve()
    assert (settings.prometheus_host, settings.prometheus_port, notes) == ('localhost', None, [])  # no server
    settings, notes = resolve(OTEL_EXPORTER_PROMETHEUS_PORT=' 9464 ', OTEL_EXPORTER_PROMETHEUS_HOST='0.0.0.0')
    assert (settings.prometheus_host, settings.prometheus_port, notes) == ('0.0.0.0', 9464, [])
    settings, _ = resolve({'prometheus_host': '::', 'prometheus_port': 9000}, OTEL_EXPORTER_PROMETHEUS_PORT='9464')
    assert (settings.prometheus_host, settings.prometheus_port) == ('::', 9000)


@pytest.mark.criterion('AC-19')
def test_the_standard_prometheus_exporter_switch_serves_on_the_default_port():  # review of OTW-12
    settings, notes = resolve(OTEL_METRICS_EXPORTER='prometheus')
    assert (settings.metrics_exporter, settings.prometheus_port, notes) == ((), 9464, [])  # the spec's default
    settings, notes = resolve(OTEL_METRICS_EXPORTER='prometheus', OTEL_EXPORTER_PROMETHEUS_PORT='9000')
    assert (settings.metrics_exporter, settings.prometheus_port, notes) == ((), 9000, [])  # no "ignored" warning
    settings, notes = resolve(OTEL_METRICS_EXPORTER='otlp, prometheus')
    assert (settings.metrics_exporter, settings.prometheus_port, notes) == (('otlp',), 9464, [])
    settings, notes = resolve({'metrics_exporter': ['prometheus'], 'prometheus_port': 9100})
    assert (settings.metrics_exporter, settings.prometheus_port, notes) == ((), 9100, [])
    settings, notes = resolve(OTEL_TRACES_EXPORTER='prometheus')  # a metrics exporter only
    assert settings.prometheus_port is None and len(notes) == 1 and 'traces_exporter' in notes[0]


@pytest.mark.parametrize('port', ['http', '0', '65536', '-1', '9464.0', '²', '123456'])
def test_a_port_that_is_not_a_port_warns_and_starts_no_server(port):  # AC-7 (DEC-49)
    settings, notes = resolve(OTEL_EXPORTER_PROMETHEUS_PORT=port)
    assert settings.prometheus_port is None
    assert len(notes) == 1 and 'OTEL_EXPORTER_PROMETHEUS_PORT' in notes[0]


def test_a_wrong_typed_explicit_port_warns_and_falls_back():  # AC-7 (DEC-49)
    for port in ('9464', True, 0, 70000):
        settings, notes = resolve({'prometheus_port': port}, OTEL_EXPORTER_PROMETHEUS_PORT='9000')
        assert settings.prometheus_port == 9000 and len(notes) == 1 and 'prometheus_port' in notes[0]


@pytest.mark.parametrize('path, expected, warns', [
    ('/metrics', '/metrics', False),
    ('/prom/scrape', '/prom/scrape', False),
    ('/metrics/', '/metrics/', False),
    ('prom//scrape', '/prom/scrape', True),  # normalised like v0
    ('', '', False),  # no route
    ('   ', '', False),
    ('/', '', True),  # v0 ignored the root too
    ('/met rics', '', True),
    ('/métrics', '', True),
])
def test_the_prometheus_path_is_normalised_or_refused(path, expected, warns):
    settings, notes = resolve(OTEL_WRAPPER_PROMETHEUS_PATH=path)
    assert settings.prometheus_path == expected
    assert len(notes) == (1 if warns else 0), notes


@pytest.mark.criterion('AC-27')
def test_v0s_blank_prometheus_endpoint_still_turns_the_route_off_with_a_warning():  # AC-27 (DEC-52)
    settings, notes = resolve(OTEL_EXPORTER_PROMETHEUS_ENDPOINT='')
    assert settings.prometheus_path == ''
    assert len(notes) == 1 and 'OTEL_WRAPPER_PROMETHEUS_PATH' in notes[0]
    settings, _ = resolve(OTEL_EXPORTER_PROMETHEUS_ENDPOINT='', OTEL_WRAPPER_PROMETHEUS_PATH='/new')
    assert settings.prometheus_path == '/new'
