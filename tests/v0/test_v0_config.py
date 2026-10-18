"""
v0's env-var parsing (v0/config). v1 renames most of these variables (DEC-59, "Environment variables"), so this
whole module is v0-specific; the parsing functions read os.environ at call time, so they are tested in-process
"""
import logging
import warnings

import pytest

from opentelemetry_wrapper.v0.config import otel_exporter_otlp
from opentelemetry_wrapper.v0.config import otel_header_attributes
from opentelemetry_wrapper.v0.config import otel_log_level
from opentelemetry_wrapper.v0.config import otel_wrapper_prometheus_exporter
from tests.v0._harness import REPO_ROOT
from tests.v0._harness import scenario

pytestmark = pytest.mark.v0_specific


@pytest.fixture
def no_warnings():
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        yield


# ----------------------------------------------------------------------------------------------------------------------
# OTEL_EXPORTER_PROMETHEUS_ENDPOINT (cases from get_prometheus_endpoint's docstring)
# ----------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize('value, expected', [
    (None, '/metrics'),  # default
    ('/metrics', '/metrics'),
    ('/metrics/', '/metrics/'),
    ('/metrics/prometheus', '/metrics/prometheus'),
])
def test_prometheus_endpoint_valid(monkeypatch, no_warnings, value, expected):
    if value is None:
        monkeypatch.delenv('OTEL_EXPORTER_PROMETHEUS_ENDPOINT', raising=False)
    else:
        monkeypatch.setenv('OTEL_EXPORTER_PROMETHEUS_ENDPOINT', value)
    assert otel_wrapper_prometheus_exporter.get_prometheus_endpoint() == expected


@pytest.mark.parametrize('value, expected', [
    ('/metrics////', '/metrics/'),
    ('////metrics////prometheus////', '/metrics/prometheus/'),
    ('metrics', '/metrics'),
])
def test_prometheus_endpoint_normalised_with_a_warning(monkeypatch, value, expected):
    monkeypatch.setenv('OTEL_EXPORTER_PROMETHEUS_ENDPOINT', value)
    with pytest.warns(UserWarning):
        assert otel_wrapper_prometheus_exporter.get_prometheus_endpoint() == expected


def test_prometheus_endpoint_empty_disables_silently(monkeypatch, no_warnings):
    monkeypatch.setenv('OTEL_EXPORTER_PROMETHEUS_ENDPOINT', '  ')
    assert otel_wrapper_prometheus_exporter.get_prometheus_endpoint() is None


@pytest.mark.parametrize('value', ['/', '////', '/a b', '/métrics', '/metrics.txt', '/metrics?x=1'])
def test_prometheus_endpoint_rejected_with_a_warning(monkeypatch, value):
    monkeypatch.setenv('OTEL_EXPORTER_PROMETHEUS_ENDPOINT', value)
    with pytest.warns(UserWarning):
        assert otel_wrapper_prometheus_exporter.get_prometheus_endpoint() is None


@pytest.mark.parametrize('value, expected, warns', [
    (None, None, False),
    ('', None, False),
    ('9464', 9464, False),
    (' 9464 ', 9464, False),
    ('80', 80, True),  # below 1024: warns but is used
    ('abc', None, True),
    ('-1', None, True),
])
def test_prometheus_port(monkeypatch, value, expected, warns):
    if value is None:
        monkeypatch.delenv('OTEL_EXPORTER_PROMETHEUS_PORT', raising=False)
    else:
        monkeypatch.setenv('OTEL_EXPORTER_PROMETHEUS_PORT', value)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        assert otel_wrapper_prometheus_exporter.get_prometheus_port() == expected
    assert bool(caught) is warns


# ----------------------------------------------------------------------------------------------------------------------
# OTEL_LOG_LEVEL (note: collides with a standard OTel variable, see DEC-59)
# ----------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize('value, expected', [
    (None, logging.INFO),
    ('', logging.INFO),
    ('debug', logging.DEBUG),
    ('TRACE', logging.DEBUG),
    (' Warn ', logging.WARNING),
    ('warning', logging.WARNING),
    ('fatal', logging.CRITICAL),
    ('notset', logging.NOTSET),
    ('15', 15),
    ('nonsense', logging.INFO),
])
def test_log_level(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv('OTEL_LOG_LEVEL', raising=False)
    else:
        monkeypatch.setenv('OTEL_LOG_LEVEL', value)
    otel_log_level.get_log_level.cache_clear()
    try:
        assert otel_log_level.get_log_level() == expected
    finally:
        otel_log_level.get_log_level.cache_clear()


# ----------------------------------------------------------------------------------------------------------------------
# OTEL_HEADER_ATTRIBUTES
# ----------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize('value, expected', [
    (None, ['x-userinfo']),  # default
    ('', []),  # set but empty: capture nothing
    ('X-UserInfo', ['x-userinfo']),
    ('x-b, x-a;x-b  X_C', ['x-a', 'x-b', 'x_c']),  # any separator, lowercased, deduplicated, sorted
])
def test_header_attributes(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv('OTEL_HEADER_ATTRIBUTES', raising=False)
    else:
        monkeypatch.setenv('OTEL_HEADER_ATTRIBUTES', value)
    otel_header_attributes.get_header_attributes.cache_clear()
    try:
        assert otel_header_attributes.get_header_attributes() == expected
    finally:
        otel_header_attributes.get_header_attributes.cache_clear()


# ----------------------------------------------------------------------------------------------------------------------
# OTLP exporter settings
# ----------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize('separator, value, expected', [
    (None, 'some-header=some-value', (('some-header', 'some-value'),)),
    (None, 'a=b\tc=d', (('a', 'b'), ('c', 'd'))),
    (';', 'a=1;b=2;c=3', (('a', '1'), ('b', '2'), ('c', '3'))),
    (None, 'authorization=Bearer abc==', (('authorization', 'Bearer abc=='),)),  # split on the first '=' only
    (None, '', ()),
])
def test_otlp_header(monkeypatch, no_warnings, separator, value, expected):
    if separator is None:
        monkeypatch.delenv('OTEL_EXPORTER_OTLP_HEADER_SEPARATOR', raising=False)
    else:
        monkeypatch.setenv('OTEL_EXPORTER_OTLP_HEADER_SEPARATOR', separator)
    monkeypatch.setenv('OTEL_EXPORTER_OTLP_HEADER', value)
    result = otel_exporter_otlp.getenv_otel_exporter_otlp_header()
    assert result == expected
    assert isinstance(result, tuple)  # otel crashes on a list of tuples, see the comment in the source


@pytest.mark.parametrize('value, expected', [
    ('novalue', ()),  # missing '='
    ('bad name=x', ()),  # invalid header name
    ('a=1\ta=2', (('a', '1'), ('a', '2'))),  # duplicate: kept, but warns
])
def test_otlp_header_warnings(monkeypatch, value, expected):
    monkeypatch.delenv('OTEL_EXPORTER_OTLP_HEADER_SEPARATOR', raising=False)
    monkeypatch.setenv('OTEL_EXPORTER_OTLP_HEADER', value)
    with pytest.warns(UserWarning):
        assert otel_exporter_otlp.getenv_otel_exporter_otlp_header() == expected


@pytest.mark.parametrize('value, expected, warns', [
    (None, None, False),
    ('true', True, False),
    ('TRUE', True, False),
    ('false', False, False),
    ('yes', False, True),  # fail secure
])
def test_otlp_insecure(monkeypatch, value, expected, warns):
    if value is None:
        monkeypatch.delenv('OTEL_EXPORTER_OTLP_INSECURE', raising=False)
    else:
        monkeypatch.setenv('OTEL_EXPORTER_OTLP_INSECURE', value)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        assert otel_exporter_otlp.getenv_otel_exporter_otlp_insecure() is expected
    assert bool(caught) is warns


@pytest.mark.parametrize('value, expected, warns', [
    (None, '', False),
    ('https://otel-collector.domain:4317', 'https://otel-collector.domain:4317', False),
    ('otel-collector/some-endpoint', 'otel-collector/some-endpoint', True),  # missing scheme
    ('http://host:notaport', 'http://host:notaport', True),
])
def test_otlp_endpoint(monkeypatch, value, expected, warns):
    monkeypatch.delenv('OTEL_EXPORTER_OTLP_INSECURE', raising=False)
    if value is None:
        monkeypatch.delenv('OTEL_EXPORTER_OTLP_ENDPOINT', raising=False)
    else:
        monkeypatch.setenv('OTEL_EXPORTER_OTLP_ENDPOINT', value)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        assert otel_exporter_otlp.getenv_otel_exporter_otlp_endpoint() == expected
    assert bool(caught) is warns


# ----------------------------------------------------------------------------------------------------------------------
# CLAUDE.md § Gate, outside the gate: the doctests (they set os.environ, so they run in their own interpreter)
# ----------------------------------------------------------------------------------------------------------------------

DOCTESTS = scenario(__name__, 'doctests', r'''
import subprocess, sys
proc = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '--doctest-modules',
                       'opentelemetry_wrapper/v0/config', 'opentelemetry_wrapper/v0/utils/extract_json_header.py'],
                      capture_output=True, text=True)
emit('returncode', proc.returncode)
emit('summary', proc.stdout.strip().splitlines()[-1])
''')


def test_doctests_pass():
    result = DOCTESTS.result()
    assert result['returncode'] == 0, result.stdout
    assert result['summary'].startswith('4 passed')
    assert (REPO_ROOT / 'opentelemetry_wrapper' / 'v0' / 'config').is_dir()
