"""
v1 request context from headers (OTW-7): the caller's x-userinfo claims on the server span (AC-12), with the
denylisted ones dropped and the raw value never recorded (AC-33), and upstream latency headers on `requests` client
spans (AC-30); DEC-2, DEC-59, DEC-76

the decoder and the denylist are pure, so they are tested in-process; apps and `requests` run in scenarios (their
own interpreters), against v1's test sink, which sees spans as they would be exported: scrubbed
"""
import base64
import json

import pytest

from opentelemetry_wrapper.v1 import _env
from opentelemetry_wrapper.v1 import _headers
from tests.v0._harness import ASGI_HELPER_SOURCE
from tests.v0._harness import scenario

USERINFO = {  # Keycloak-style userinfo, as Kong injects it (base64, no padding), with a site-specific claim
    'exp': 1700003600, 'iat': 1700000000, 'auth_time': 1700000000, 'jti': '6a1f-77c2',
    'iss': 'https://auth.example.com/realms/shop', 'aud': 'account', 'sub': 'f1b2c3', 'typ': 'Bearer',
    'azp': 'shop-web', 'nonce': 'n-0815', 'session_state': '9d0e-3c4b', 'sid': '9d0e-3c4b', 'at_hash': 'q1w2e3',
    'c_hash': 'r4t5y6', 'acr': '1', 'realm_access': {'roles': ['admin', 'user']}, 'scope': 'openid email profile',
    'email_verified': True, 'name': 'Ann Lee', 'preferred_username': 'ann', 'email': 'a@example.com',
    'employee_id': 'E-1234', 'access_token': 'at-QWERTY', 'refresh_token': 'rt-ASDFGH', 'locale': None,
}
DENIED_BY_DEFAULT = {'nonce', 'session_state', 'sid', 'at_hash', 'c_hash', 'access_token', 'refresh_token'}
PREFIX = 'http.request.header.x-userinfo.'


def with_json_length_mod_3(obj, remainder):
    """pad a claim until the JSON's length % 3 == remainder, which picks the base64 padding: 0, 2 or 1 '='"""
    obj = dict(obj, pad='')
    while len(json.dumps(obj).encode()) % 3 != remainder:
        obj['pad'] += 'x'
    return obj


def b64(obj, *, padded=False, urlsafe=False) -> str:
    out = (base64.urlsafe_b64encode if urlsafe else base64.b64encode)(json.dumps(obj).encode()).decode('ascii')
    return out if padded else out.rstrip('=')


def expected_claims(obj, denied=DENIED_BY_DEFAULT):
    flat = dict(_headers.flatten(obj))
    return {f'{PREFIX}{k}': v for k, v in flat.items() if k.split('.')[0] not in denied}


# ----------------------------------------------------------------------------------------------------------------------
# AC-12: every base64 length decodes; claims are recorded unchanged
# ----------------------------------------------------------------------------------------------------------------------

@pytest.mark.criterion('AC-12')
@pytest.mark.parametrize('urlsafe', [False, True], ids=['standard', 'urlsafe'])
@pytest.mark.parametrize('padded', [False, True], ids=['unpadded', 'padded'])
@pytest.mark.parametrize('remainder', [0, 1, 2])
def test_base64_userinfo_of_every_length_decodes(remainder, padded, urlsafe):
    obj = with_json_length_mod_3(USERINFO, remainder)
    value = b64(obj, padded=padded, urlsafe=urlsafe)
    assert value.count('=') == (padded and (3 - remainder) % 3)  # the case under test is the one intended
    assert dict(_headers.decode(value)) == dict(_headers.flatten(obj))


@pytest.mark.criterion('AC-12')
def test_claims_are_flattened_and_recorded_unchanged():
    attributes = _headers.header_attributes('x-userinfo', b64(USERINFO), _headers.Denylist(()))
    assert attributes[PREFIX + 'employee_id'] == 'E-1234'  # site-specific: named nowhere
    assert attributes[PREFIX + 'auth_time'] == 1700000000  # an int, not a string or a marker
    assert attributes[PREFIX + 'iss'] == 'https://auth.example.com/realms/shop'
    assert attributes[PREFIX + 'realm_access.roles.[0]'] == 'admin'
    assert attributes[PREFIX + 'email_verified'] is True
    assert PREFIX + 'locale' not in attributes  # nulls are dropped


def test_plain_json_header_is_flattened():
    assert dict(_headers.decode(' {"a": {"b": 1}, "c": [true, 2.5]} ')) == {'a.b': 1, 'c.[0]': True, 'c.[1]': 2.5}


def test_a_claim_too_big_for_an_attribute_is_recorded_as_text():
    assert dict(_headers.decode(b64({'n': 2 ** 70, 'm': -2 ** 63}))) == {'n': str(2 ** 70), 'm': -2 ** 63}


@pytest.mark.parametrize('value', [
    'eyJzdWIiOiAiMSIs',  # truncated
    'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJl',  # a JWT
    base64.b64encode(b'{"a": nope}').decode(),  # base64, not JSON
    base64.b64encode(b'{"\xff\xfe": 1}').decode(),  # not UTF-8
    'eyJ' + 'A' * 4002,  # not base64 (length 1 mod 4)
])
@pytest.mark.criterion('AC-33')
def test_a_value_that_looks_encoded_but_does_not_decode_is_never_recorded(value):
    assert value.startswith('ey')
    assert _headers.header_attributes('x-userinfo', value, _headers.Denylist(())) == {}


def test_plain_text_is_recorded_as_it_is():
    assert _headers.header_attributes('x-userinfo', 'just text', _headers.Denylist(())) == {
        'http.request.header.x-userinfo': 'just text'}


# ----------------------------------------------------------------------------------------------------------------------
# AC-33: the denylist
# ----------------------------------------------------------------------------------------------------------------------

@pytest.mark.criterion('AC-33')
def test_default_denylist_drops_credentials_and_session_handles_and_keeps_personal_data():
    settings, _ = _env.resolve({}, {})
    assert settings.header_attributes_exclude == ('*token*', 'at_hash', 'c_hash', 'nonce', 'session_state', 'sid')
    attributes = _headers.header_attributes('x-userinfo', b64(USERINFO),
                                            _headers.Denylist(settings.header_attributes_exclude))
    assert attributes == expected_claims(USERINFO)
    assert {k[len(PREFIX):] for k in attributes} & DENIED_BY_DEFAULT == set()
    assert attributes[PREFIX + 'email'] == 'a@example.com' and attributes[PREFIX + 'name'] == 'Ann Lee'


@pytest.mark.criterion('AC-33')
@pytest.mark.parametrize('pattern, path, denied', [
    ('realm_access.roles', 'realm_access.roles.[1]', True),  # a pattern covers everything under its path
    ('realm_access', 'realm_access.roles.[0]', True),
    ('realm_access.roles', 'realm_access', False),
    ('*token*', 'idToken', True),  # case-insensitive
    ('*token*', 'tokens.[0].value', True),
    ('email', 'email_verified', False),  # a glob matches the whole path
    ('email*', 'email_verified', True),
    ('sid', 'sub', False),
])
def test_denylist_patterns(pattern, path, denied):
    assert _headers.Denylist([pattern]).denies(path) is denied


def test_denylist_from_env_and_explicit():
    environ = {'OTEL_WRAPPER_HEADER_ATTRIBUTES_EXCLUDE': ' email , realm_access.* '}
    assert _env.resolve({}, environ)[0].header_attributes_exclude == ('email', 'realm_access.*')
    # a blank variable is unset: the denylist is not cleared by accident; an explicit empty list does clear it
    assert _env.resolve({}, {'OTEL_WRAPPER_HEADER_ATTRIBUTES_EXCLUDE': ' '})[0].header_attributes_exclude == \
        _env.DEFAULT_HEADER_ATTRIBUTES_EXCLUDE
    assert _env.resolve({'header_attributes_exclude': []}, environ)[0].header_attributes_exclude == ()
    assert _env.resolve({'header_attributes_exclude': 'sub,email'}, environ)[0].header_attributes_exclude == \
        ('sub', 'email')


def test_response_header_attributes_from_env_and_explicit():
    assert _env.resolve({}, {})[0].response_header_attributes == _env.DEFAULT_RESPONSE_HEADER_ATTRIBUTES
    assert 'x-envoy-upstream-service-time' in _env.DEFAULT_RESPONSE_HEADER_ATTRIBUTES
    environ = {'OTEL_WRAPPER_RESPONSE_HEADER_ATTRIBUTES': 'X-A, x-b'}
    assert _env.resolve({}, environ)[0].response_header_attributes == ('x-a', 'x-b')
    assert _env.resolve({'response_header_attributes': ['X-C']}, environ)[0].response_header_attributes == ('x-c',)


def test_wrong_typed_options_are_ignored_with_a_warning():
    settings, notes = _env.resolve({'header_attributes_exclude': 3, 'response_header_attributes': 4}, {})
    assert settings.header_attributes_exclude == _env.DEFAULT_HEADER_ATTRIBUTES_EXCLUDE
    assert settings.response_header_attributes == _env.DEFAULT_RESPONSE_HEADER_ATTRIBUTES
    assert len(notes) == 2


def test_hooks_never_raise(capsys):
    class Broken:
        def is_recording(self):
            return True

        def set_attributes(self, attributes):
            raise RuntimeError('broken span')

        set_attribute = set_attributes

    scope = {'headers': [(b'x-userinfo', b64(USERINFO).encode())]}
    _headers.server_request_hook(['x-userinfo'], ())(Broken(), scope)
    _headers.server_request_hook(['x-userinfo'], ())(Broken(), {'headers': 'not a list of pairs'})

    class Response:
        headers = {'x-envoy-upstream-service-time': '42'}

    _headers.requests_response_hook(['x-envoy-upstream-service-time'])(Broken(), None, Response())
    lines = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert {line['site'] for line in lines} == {'server_request_hook (request header attributes)',
                                                'requests response_hook (response header attributes)'}
    assert all(b64(USERINFO) not in json.dumps(line) for line in lines)


# ----------------------------------------------------------------------------------------------------------------------
# end to end: FastAPI and requests, with no configuration (AC-30) and with header capture on (AC-33)
# ----------------------------------------------------------------------------------------------------------------------

PRELUDE = ASGI_HELPER_SOURCE + r'''
import base64
import json
from tests.impl import import_v1
otel = import_v1().otel
from opentelemetry_wrapper.v1 import _config
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
exporter = InMemorySpanExporter()
_config.add_span_sink(exporter)  # v1's test sink: every finished span, scrubbed as it would be exported


def make_app():
    from fastapi import FastAPI
    app = FastAPI()

    @app.get('/hello')
    def hello():
        return 'hello'

    return app


def fake_session(response_headers):
    import requests
    from requests.adapters import BaseAdapter

    class FakeAdapter(BaseAdapter):
        def send(self, request, **kwargs):
            response = requests.Response()
            response.status_code = 200
            response._content = b'ok'
            response.url = request.url
            response.request = request
            response.headers.update(response_headers)
            return response

        def close(self):
            pass

    session = requests.Session()
    session.mount('http://', FakeAdapter())
    return session


def taken():
    """every finished span as {name, kind, attributes}, then clear"""
    out = [{'name': s.name, 'kind': s.kind.name, 'scope': s.instrumentation_scope.name,
            'attributes': dict(s.attributes)} for s in exporter.get_finished_spans()]
    exporter.clear()
    return out
'''


def _server(spans):
    (server,) = [s for s in spans if s['kind'] == 'SERVER' and s['scope'] == 'opentelemetry.instrumentation.fastapi']
    return server


def _client(spans):
    (client,) = [s for s in spans if s['kind'] == 'CLIENT']
    return client


def _userinfo_attributes(span):
    return {k: v for k, v in span['attributes'].items() if k.startswith('http.request.header.x-userinfo')}


_LENGTHS = [with_json_length_mod_3(USERINFO, r) for r in (0, 1, 2)]
_HEADERS = [b64(obj) for obj in _LENGTHS] + [b64(_LENGTHS[0], padded=True, urlsafe=True)]

NO_CONFIG = scenario(__name__, 'v1_headers_no_config', PRELUDE + f'''
app = otel.instrument(make_app())
for header in {_HEADERS!r}:
    assert asgi_request(app, '/hello', headers=[('x-userinfo', header)]).status == 200
    emit(header, taken())
for header in ('eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJl', 'just text'):
    asgi_request(app, '/hello', headers=[('x-userinfo', header)])
    emit(header, taken())
otel.instrument()  # logging, requests, system metrics: what an app calls at startup
session = fake_session({{'X-Envoy-Upstream-Service-Time': '42', 'X-Kong-Upstream-Latency': '7',
                         'X-Unlisted-Header': 'nope'}})
assert session.get('http://example.invalid/upstream').text == 'ok'
emit('requests', taken())
''')


@pytest.mark.criterion('AC-12')
@pytest.mark.criterion('AC-30')
@pytest.mark.criterion('AC-33')
def test_userinfo_claims_on_the_server_span_with_no_configuration():
    result = NO_CONFIG.result()
    for obj, header in zip(_LENGTHS + [_LENGTHS[0]], _HEADERS):
        spans = result[header]
        server = _server(spans)
        attributes = _userinfo_attributes(server)
        assert attributes == expected_claims(obj)  # every length; scrubbed, yet auth_time and iss are unchanged
        assert attributes[PREFIX + 'employee_id'] == 'E-1234'
        assert attributes[PREFIX + 'auth_time'] == 1700000000
        assert attributes[PREFIX + 'iss'] == 'https://auth.example.com/realms/shop'
        assert server['attributes']['http.route'] == '/hello'
        dump = json.dumps(spans)
        assert header not in dump and header.rstrip('=') not in dump  # the raw value, nowhere
        assert 'at-QWERTY' not in dump and '9d0e-3c4b' not in dump  # nor the denied claims' values


@pytest.mark.criterion('AC-33')
def test_a_jwt_in_x_userinfo_is_not_recorded_and_plain_text_is():
    result = NO_CONFIG.result()
    assert _userinfo_attributes(_server(result['eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJl'])) == {}
    assert _userinfo_attributes(_server(result['just text'])) == {'http.request.header.x-userinfo': 'just text'}


@pytest.mark.criterion('AC-30')
def test_upstream_latency_on_the_requests_client_span_with_no_configuration():
    client = _client(NO_CONFIG.result()['requests'])
    headers = {k: v for k, v in client['attributes'].items() if k.startswith('http.response.header.')}
    assert headers == {'http.response.header.x-envoy-upstream-service-time': '42',
                       'http.response.header.x-kong-upstream-latency': '7'}


_CAPTURE_HEADER = b64(_LENGTHS[2])

CAPTURE_ON = scenario(__name__, 'v1_headers_capture_on', PRELUDE + f'''
app = otel.instrument(make_app())
otel.instrument()
header = {_CAPTURE_HEADER!r}
asgi_request(app, '/hello', headers=[('x-userinfo', header), ('x-other', 'visible'), ('x-internal-id', 'hidden')])
emit('server', taken())
session = fake_session({{}})
session.get('http://example.invalid/upstream', headers={{'x-userinfo': header, 'x-other': 'visible'}})
emit('client', taken())
''', env={'OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_REQUEST': '.*',
          'OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_CLIENT_REQUEST': '.*',
          'OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SANITIZE_FIELDS': 'x-internal-id'})


@pytest.mark.criterion('AC-33')
def test_the_raw_header_never_appears_with_header_capture_on():
    result = CAPTURE_ON.result()
    server, client = _server(result['server']), _client(result['client'])
    # capture is on, so this isn't vacuous: the other headers are captured, the user's sanitize field still applies
    assert server['attributes']['http.request.header.x_other'] == ['visible']
    assert server['attributes']['http.request.header.x_internal_id'] == ['[REDACTED]']
    assert client['attributes']['http.request.header.x_other'] == ['visible']
    # the raw value is captured as [REDACTED], on the server span and on a client call that forwards it
    assert server['attributes']['http.request.header.x_userinfo'] == ['[REDACTED]']
    assert client['attributes']['http.request.header.x_userinfo'] == ['[REDACTED]']
    assert _userinfo_attributes(server) == expected_claims(_LENGTHS[2])  # and decoded, as without capture
    dump = json.dumps([result['server'], result['client']])
    assert _CAPTURE_HEADER not in dump and 'at-QWERTY' not in dump and '9d0e-3c4b' not in dump


CONFIGURED = scenario(__name__, 'v1_headers_configured', PRELUDE + f'''
otel.configure(response_header_attributes=['X-Unlisted-Header'])
app = otel.instrument(make_app())
otel.instrument()
asgi_request(app, '/hello', headers=[('x-userinfo', {b64(USERINFO)!r}), ('x-claims', '{{"team": {{"id": 7}}}}')])
emit('server', taken())
session = fake_session({{'X-Envoy-Upstream-Service-Time': '42', 'X-Unlisted-Header': 'yes'}})
session.get('http://example.invalid/upstream')
emit('client', taken())
''', env={'OTEL_WRAPPER_HEADER_ATTRIBUTES': 'x-userinfo,X-Claims',
          'OTEL_WRAPPER_HEADER_ATTRIBUTES_EXCLUDE': 'email,realm_access.roles,Employee_*'})


@pytest.mark.criterion('AC-33')
def test_configured_denylist_and_headers():
    result = CONFIGURED.result()
    server = _server(result['server'])
    attributes = _userinfo_attributes(server)
    # the variable replaces the default: its patterns are dropped, the default's are recorded
    assert attributes == expected_claims(USERINFO, denied={'email', 'realm_access', 'employee_id'})
    assert attributes[PREFIX + 'sid'] == '9d0e-3c4b'
    assert server['attributes']['http.request.header.x-claims.team.id'] == 7
    headers = {k: v for k, v in _client(result['client'])['attributes'].items()
               if k.startswith('http.response.header.')}
    assert headers == {'http.response.header.x-unlisted-header': 'yes'}
