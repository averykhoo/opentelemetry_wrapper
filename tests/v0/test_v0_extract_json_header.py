"""
`extract_json_header`: flattens a JSON (or base64-encoded JSON, e.g. Kong's `x-userinfo`) header into a flat dict
v1 keeps this as-is (OTW-7, workstream 5), so these are expected to hold for v1 too
"""
import base64
import json

import pytest

from opentelemetry_wrapper.v0.utils.extract_json_header import extract_json_header


def b64(obj, *, padded=False, urlsafe=False) -> str:
    raw = json.dumps(obj).encode('utf-8')
    out = (base64.urlsafe_b64encode if urlsafe else base64.b64encode)(raw).decode('ascii')
    return out if padded else out.rstrip('=')


# ----------------------------------------------------------------------------------------------------------------------
# plain json
# ----------------------------------------------------------------------------------------------------------------------

def test_json_object_is_flattened_with_dotted_keys_and_nulls_dropped():
    header = json.dumps({'a': {'aa': {'aaa': 'AAA'}, 'x': None}, 'b': [1, 2, 3]})
    assert extract_json_header(header) == {'a.aa.aaa': 'AAA', 'b.[0]': 1, 'b.[1]': 2, 'b.[2]': 3}


def test_json_array_is_flattened_with_index_keys():
    assert extract_json_header('["x", null, {"1": 11}, "y"]') == {'[0]': 'x', '[2].1': 11, '[3]': 'y'}


def test_scalar_types_are_preserved():
    assert extract_json_header('{"t": true, "f": false, "i": 1, "fl": 2.5, "s": "s"}') == \
           {'t': True, 'f': False, 'i': 1, 'fl': 2.5, 's': 's'}


def test_key_order_is_preserved():
    assert list(extract_json_header('{"z": 1, "a": {"y": 2, "b": 3}, "m": 4}')) == ['z', 'a.y', 'a.b', 'm']


def test_empty_containers_give_an_empty_dict():
    assert extract_json_header('{}') == {}
    assert extract_json_header('[]') == {}


def test_dotted_keys_collide_with_nesting():
    # documented "unhandled edge case" in _flatten_json's doctests
    assert extract_json_header('{"a.b": 1}') == extract_json_header('{"a": {"b": 1}}') == {'a.b': 1}


@pytest.mark.parametrize('value', [
    None,
    b'{"a": 1}',  # only str is decoded
    123,
    '',
    'plain text',
    '{not json}',
    '"a json string"',
    '123',
    ' {"a": 1}',  # leading whitespace: not recognised as json
    '{"a": 1',
])
def test_non_json_values_give_none(value):
    assert extract_json_header(value) is None


# ----------------------------------------------------------------------------------------------------------------------
# base64-encoded json (userinfo)
# ----------------------------------------------------------------------------------------------------------------------

USERINFO = {  # Keycloak-style userinfo as injected by Kong (same shape as the design evidence's header check)
    'sub': 'f1b2c3', 'email': 'a@example.com', 'email_verified': True, 'name': 'Ann Lee',
    'realm_access': {'roles': ['admin', 'user']}, 'auth_time': 1700000000, 'session_state': None,
}
USERINFO_FLAT = {'sub': 'f1b2c3', 'email': 'a@example.com', 'email_verified': True, 'name': 'Ann Lee',
                 'realm_access.roles.[0]': 'admin', 'realm_access.roles.[1]': 'user', 'auth_time': 1700000000}


def _with_json_length_mod_3(obj, remainder):
    """pad a string field until len(json.dumps(obj)) % 3 == remainder, i.e. pick which base64 padding is needed"""
    obj = dict(obj)
    obj['pad'] = ''
    while len(json.dumps(obj).encode()) % 3 != remainder:
        obj['pad'] += 'x'
    return obj


def test_base64_userinfo_needing_two_padding_chars_is_decoded():
    # this is the one length class that works on python 3.12: the decoder always appends exactly '=='
    obj = _with_json_length_mod_3(USERINFO, 1)
    assert extract_json_header(b64(obj)) == {**USERINFO_FLAT, 'pad': obj['pad']}
    assert extract_json_header(b64(obj, padded=True)) == {**USERINFO_FLAT, 'pad': obj['pad']}


@pytest.mark.xfail(strict=True, reason='found while writing this suite (not in the v0 bug list): '
                                       '_extract_userinfo always '
                                       'appends "==" before b64decode(validate=True), which python >= 3.11 rejects '
                                       '("Excess data after padding" / "Excess padding not allowed"), so 2 out of 3 '
                                       'userinfo headers are not decoded (python 3.10 accepted them)')
@pytest.mark.parametrize('remainder', [0, 2])
def test_base64_userinfo_of_any_length_is_decoded(remainder):
    obj = _with_json_length_mod_3(USERINFO, remainder)
    assert extract_json_header(b64(obj)) == {**USERINFO_FLAT, 'pad': obj['pad']}


def test_jwt_is_not_decoded():
    # three dot-separated base64 segments: treated as a JWT and left alone (so the hook records it raw)
    jwt = f'{b64({"alg": "HS256"})}.{b64({"sub": "1"})}.signature'
    assert jwt.startswith('ey')
    assert extract_json_header(jwt) is None


def test_base64_json_array_is_not_decoded():
    # only base64 that starts with 'ey' (i.e. decodes to '{"') is considered
    assert extract_json_header(base64.b64encode(b'[1, 2]').decode()) is None


def test_urlsafe_base64_with_dash_or_underscore_is_not_decoded():
    obj = _with_json_length_mod_3({'k': '\xff\xfe>>>???'}, 1)  # chars whose base64 contains '+' / '/'
    standard, urlsafe = b64(obj), b64(obj, urlsafe=True)
    assert standard != urlsafe
    assert extract_json_header(standard) == {'k': obj['k'], 'pad': obj['pad']}
    assert extract_json_header(urlsafe) is None


def test_base64_of_invalid_json_gives_none():
    assert extract_json_header(base64.b64encode(b'{"a": nope}').decode().rstrip('=')) is None
