"""
canary: resource precedence (DEC-33): our detectors (guesses) < `OTEL_SERVICE_NAME` / `OTEL_RESOURCE_ATTRIBUTES` <
explicit `otel.configure(...)` arguments, built as `Resource.create()`, then our detectors, then
`OTELResourceDetector().detect()`, then the explicit attributes. that order only works while `Resource.merge` lets the
updating resource win and `OTELResourceDetector` reads both env vars at `detect()` time
"""
import pytest
from opentelemetry.sdk.resources import OTELResourceDetector
from opentelemetry.sdk.resources import Resource


@pytest.fixture
def environ(monkeypatch):
    for name in ('OTEL_SERVICE_NAME', 'OTEL_RESOURCE_ATTRIBUTES', 'OTEL_EXPERIMENTAL_RESOURCE_DETECTORS'):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def _build(explicit=None):
    guess = Resource({'service.name': 'guessed-from-k8s', 'k8s.pod.name': 'guessed-pod'})
    resource = Resource.create().merge(guess).merge(OTELResourceDetector().detect())
    return resource.merge(Resource(explicit or {})).attributes


def test_without_env_vars_the_default_is_unknown_service_and_our_guess_beats_it(environ):
    assert Resource.create().attributes['service.name'].startswith('unknown_service')
    assert _build()['service.name'] == 'guessed-from-k8s'


def test_otel_service_name_beats_our_guess(environ):
    environ.setenv('OTEL_SERVICE_NAME', 'from-env')
    attributes = _build()
    assert attributes['service.name'] == 'from-env'
    assert attributes['k8s.pod.name'] == 'guessed-pod'  # guesses the env does not name survive


def test_otel_resource_attributes_beat_our_guess(environ):
    environ.setenv('OTEL_RESOURCE_ATTRIBUTES', 'k8s.pod.name=from-env,service.name=attr-name')
    attributes = _build()
    assert attributes['k8s.pod.name'] == 'from-env'
    assert attributes['service.name'] == 'attr-name'


def test_otel_service_name_beats_otel_resource_attributes(environ):
    environ.setenv('OTEL_RESOURCE_ATTRIBUTES', 'service.name=attr-name')
    environ.setenv('OTEL_SERVICE_NAME', 'from-env')
    assert _build()['service.name'] == 'from-env'


def test_explicit_attributes_beat_the_env(environ):
    environ.setenv('OTEL_SERVICE_NAME', 'from-env')
    assert _build({'service.name': 'explicit'})['service.name'] == 'explicit'
