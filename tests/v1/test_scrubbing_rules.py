"""
characterization tests for the scrubbing rules (OTW-8, AC-13): what the default rules redact and what they keep,
checked on both engines (re, and hyperscan when installed). all secrets here are obviously fake
"""
import itertools
import random
import re

import pytest

from opentelemetry_wrapper.v1.scrubbing import (DEFAULT_RULES, KEY_RULES, NON_REGULAR, REDACTED, TOLERATED,
                                                VALUE_RULES, HyperscanEngine, RegexEngine, Rule, Scrubber)

JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc123"
K8S_JWT = "eyJhbGciOiJSUzI1NiIsImtpZCI6IkZBS0UifQ.eyJpc3MiOiJrdWJlcm5ldGVzL3NlcnZpY2VhY2NvdW50In0.FAKEsig_0000"
PEM = "-----BEGIN RSA PRIVATE KEY-----\nMIIEfakefakefake\nAAAA\n-----END RSA PRIVATE KEY-----"


@pytest.fixture(params=["re", "hyperscan"])
def scrubber(request):
    if request.param == "hyperscan":
        pytest.importorskip("hyperscan")
        return Scrubber(engine="hyperscan")
    return Scrubber()


# ----------------------------------------------------------------------------- keys
REDACT_KEYS = ["password", "passwd", "db_password", "user.password", "PGPASSWORD", "MYSQL_PWD", "secret",
               "client_secret", "secret_key", "api_key", "apikey", "x-api-key", "http.request.header.authorization",
               "proxy-authorization", "cookie", "set-cookie", "http.response.header.set-cookie", "access_token",
               "refresh_token", "id_token", "private_key", "credentials", "aws_secret_access_key", "session_id",
               "csrf_token", "x-csrf-token", "http.request.header.x-auth-token", "vault.token", "passphrase",
               "OPENAI_API_KEY", "credential", "http.request.header.cookie"]
KEEP_KEYS = ["author", "authority", "http.authority", "gen_ai.usage.input_tokens", "input_tokens", "max_tokens",
             "token_count", "tokenizer", "keyboard", "monkey", "password_policy", "passwordless", "secret_name",
             "routing_key", "messaging.rabbitmq.destination.routing_key", "cache.key", "partition_key",
             "http.method", "http.url", "db.statement", "exception.message", "user.id", "session", "tokens",
             "auth_time", "iss"]


@pytest.mark.parametrize("key", REDACT_KEYS)
@pytest.mark.criterion('AC-13')
def test_secret_key_redacts_whole_value(scrubber, key):
    out, notes = scrubber.scrub_attributes({key: "innocent-looking-value", "other": 1})
    assert out[key] == REDACTED and out["other"] == 1
    assert len(notes) == 1 and notes[0].startswith(f"{key}:key.")


@pytest.mark.parametrize("key", KEEP_KEYS)
@pytest.mark.criterion('AC-13')
def test_innocent_key_kept(scrubber, key):
    attrs = {key: "plain value 42"}
    out, notes = scrubber.scrub_attributes(attrs)
    assert out is attrs and notes == []


@pytest.mark.parametrize("key", ["http.request.header.x-userinfo.auth_time", "http.request.header.x-userinfo.iss",
                                 "http.request.header.x-userinfo.employee_id",
                                 "http.request.header.x-userinfo.password"])
@pytest.mark.criterion('AC-13')
def test_allowlist_glob_is_never_touched(scrubber, key):
    attrs = {key: f"password=hunter2 Bearer {JWT}"}  # even a value that looks secret
    out, notes = scrubber.scrub_attributes(attrs)
    assert out is attrs and notes == []


def test_allowlist_exact_key_and_custom_glob():
    s = Scrubber(allow_keys=["password"], allow_globs=["my.app.*"])
    attrs = {"password": "x", "my.app.secret": "y", "secret": "z"}
    out, _ = s.scrub_attributes(attrs)
    assert out == {"password": "x", "my.app.secret": "y", "secret": REDACTED}


# ----------------------------------------------------------------------------- values: must redact
REDACT_VALUES = [
    # (input, expected output, rule name(s), "|"-separated when more than one rule may fire)
    (f"Bearer {JWT}", f"Bearer {REDACTED}", "bearer"),
    (f"bearer {JWT}", f"bearer {REDACTED}", "bearer"),
    (JWT, REDACTED, "jwt"),
    (K8S_JWT, REDACTED, "jwt"),
    (f"got token {JWT} from idp", f"got token {REDACTED} from idp", "jwt"),
    ("Basic dXNlcjpwYXNz", f"Basic {REDACTED}", "basic"),
    ("Bearer opaque-Token_12345678", f"Bearer {REDACTED}", "bearer"),
    ("hvs.CAESIfakefakefakefakefakefakefake0123", REDACTED, "vault_token"),
    ("hvb.AAAAAQfakefakefakefakefakefake", REDACTED, "vault_token"),
    ("hvr.fakefakefakefakefakefakefake", REDACTED, "vault_token"),
    ("ghp_FAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKE1234", REDACTED, "github_token"),
    ("gho_FAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKE1234", REDACTED, "github_token"),
    ("ghu_FAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKE1234", REDACTED, "github_token"),
    ("ghs_FAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKE1234", REDACTED, "github_token"),
    ("ghr_FAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKE1234", REDACTED, "github_token"),
    ("github_pat_FAKEFAKEFAKEFAKE_fakefakefakefakefake", REDACTED, "github_token"),
    ("glpat-fakefakefakefakefake1", REDACTED, "gitlab_token"),
    ("xoxb-0000000000-0000000000-fakefakefake", REDACTED, "slack_token"),
    ("xoxp-0000000000-fakefakefake", REDACTED, "slack_token"),
    ("sk_live_FAKEfakeFAKEfakeFAKE", REDACTED, "stripe_key"),
    ("rk_live_FAKEfakeFAKEfakeFAKE", REDACTED, "stripe_key"),
    ("AKIAFAKEFAKEFAKEFAKE", REDACTED, "aws_access_key_id"),
    ("ASIAFAKEFAKEFAKEFAKE", REDACTED, "aws_access_key_id"),
    ("AIzaFAKEfakeFAKEfakeFAKEfakeFAKEfakeFAK", REDACTED, "google_api_key"),
    ("sk-FAKEfakeFAKEfakeFAKEfakeFAKE", REDACTED, "sk_api_key"),
    ("sk-ant-api03-FAKEfakeFAKEfakeFAKEfake", REDACTED, "sk_api_key"),
    (PEM, f"-----BEGIN RSA PRIVATE KEY-----{REDACTED}-----END RSA PRIVATE KEY-----", "pem"),
    ("-----BEGIN PRIVATE KEY-----\nMIIfake\n-----END PRIVATE KEY-----",
     f"-----BEGIN PRIVATE KEY-----{REDACTED}-----END PRIVATE KEY-----", "pem"),
    ("-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1fake", f"-----BEGIN OPENSSH PRIVATE KEY-----{REDACTED}", "pem"),
    ("postgresql://user:hunter2@db/x", f"postgresql://user:{REDACTED}@db/x", "url_userinfo"),
    ("redis://:hunter2@cache:6379/0", f"redis://:{REDACTED}@cache:6379/0", "url_userinfo"),
    ("amqp://guest:guest@rabbit:5672/", f"amqp://guest:{REDACTED}@rabbit:5672/", "url_userinfo"),
    ("https://user:pw@host/path", f"https://user:{REDACTED}@host/path", "url_userinfo"),
    ("could not connect to postgresql://app:s3cret@db:5432/app: timeout",
     f"could not connect to postgresql://app:{REDACTED}@db:5432/app: timeout", "url_userinfo"),
    ("https://h/x?token=abc&sig=xyz&X-Amz-Signature=qq&api_key=k&max_tokens=5&sort_key=n",
     f"https://h/x?token={REDACTED}&sig={REDACTED}&X-Amz-Signature={REDACTED}&api_key={REDACTED}"
     "&max_tokens=5&sort_key=n", "url_query"),
    ("https://s3.example/obj?X-Amz-Credential=c&X-Amz-Security-Token=tok&X-Amz-Signature=s",
     f"https://s3.example/obj?X-Amz-Credential=c&X-Amz-Security-Token={REDACTED}&X-Amz-Signature={REDACTED}",
     "url_query"),
    ("access_token=abc&other=1", f"access_token={REDACTED}&other=1", "inline_kv|url_query"),  # url.query form
    ("retry with api_key=abc123", f"retry with api_key={REDACTED}", "inline_kv"),
    ("connecting with password=hunter2", f"connecting with password={REDACTED}", "inline_kv"),
    ('{"password": "hunter2"}', f'{{"password": "{REDACTED}"}}', "inline_kv"),
    ('{"password": "hunter two", "user": "bob"}', f'{{"password": "{REDACTED}", "user": "bob"}}', "inline_kv"),
    ("client_secret: s3cret", f"client_secret: {REDACTED}", "inline_kv"),
    ("Authorization: Bearer opaque-Token_12345678", f"Authorization: Bearer {REDACTED}", "inline_kv"),
    ("x-api-key: abc", f"x-api-key: {REDACTED}", "inline_kv"),
    ("SELECT * FROM users WHERE password = 'x'", f"SELECT * FROM users WHERE password = '{REDACTED}'", "inline_kv"),
]


@pytest.mark.parametrize("text,expected,rule", REDACT_VALUES, ids=[c[2] + ":" + c[0][:24] for c in REDACT_VALUES])
@pytest.mark.criterion('AC-13')
def test_value_redacted_under_innocent_key(scrubber, text, expected, rule):
    out, notes = scrubber.scrub_attributes({"log.message": text})
    assert out["log.message"] == expected
    assert notes and all(n.startswith("log.message:value.") for n in notes)
    assert any(n.endswith("." + r) for n in notes for r in rule.split("|"))


def test_sql_create_user_password_literal_is_redacted(scrubber):
    out, notes = scrubber.scrub_text("CREATE USER bob WITH PASSWORD 'hunter2'")  # keyword form: no '=' or ':'
    assert out == f"CREATE USER bob WITH PASSWORD '{REDACTED}'"
    assert notes == ["body:value.inline_kv"]


# ----------------------------------------------------------------------------- values: must keep
KEEP_VALUES = [
    "Password reset email sent", "used 5 tokens", "see docs/secrets.md", "tests pass: 5",
    "Basic configuration is required", "bearer authentication failed", "Bearer token missing",
    "4bf92f3577b34da6a3ce929d0e0e4736", "00f067aa0ba902b7",  # w3c trace id / span id
    "123e4567-e89b-12d3-a456-426614174000",  # uuid
    "6bbd615f0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f",  # git sha
    "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",  # digest
    "SGVsbG8gd29ybGQsIHRoaXMgaXMgYW4gb3JkaW5hcnkgcGF5bG9hZA==",  # ordinary base64, no prefix
    "https://auth.example.com/realms/session-demo", "postgresql://user@host/db", "http://host:8080/path?x=a@b",
    "https://h/x?max_tokens=5&sort_key=name&page_token_count=3",
    "task-fakefakefakefakefakefakefake", "desk-fakefakefakefakefakefake",  # not sk-
    "Traceback (most recent call last):\n  File \"app.py\", line 1\nValueError: bad input",
    "the tokenizer produced 12 tokens for input_tokens=12",
]


@pytest.mark.parametrize("text", KEEP_VALUES, ids=lambda t: t[:30])
@pytest.mark.criterion('AC-13')
def test_innocent_value_kept(scrubber, text):
    attrs = {"log.message": text}
    out, notes = scrubber.scrub_attributes(attrs)
    assert out is attrs and notes == []


@pytest.mark.criterion('AC-13')
def test_spec_must_keep_keys_and_values(scrubber):
    """OTW-8 spec: telemetry's own ids, digests and token *counts* are never scrubbed"""
    keys = ["input_tokens", "tokenizer", "token_count", "password_policy", "passwordless"]
    values = ["4bf92f3577b34da6a3ce929d0e0e4736",  # w3c trace id
              "00f067aa0ba902b7",  # span id
              "123e4567-e89b-12d3-a456-426614174000",  # uuid
              "sha256:" + "0123456789abcdef" * 4]  # sha256 digest
    for k in keys:
        attrs = {k: "12"}
        assert scrubber.scrub_attributes(attrs) == (attrs, [])
    for v in values:
        for attrs in ({"trace_id": v}, {"log.message": f"id {v} done"}):
            assert scrubber.scrub_attributes(attrs) == (attrs, [])
        assert scrubber.scrub_text(v) == (v, [])


# ----------------------------------------------------------------------------- known false positives
# known false positives, accepted for now (OTW-8 spec): if one of these starts passing through, the rules changed;
# update the spec's list
@pytest.mark.parametrize("key", ["next_token", "page_token", "continuation_token", "cancellation_token", "is_secret",
                                 "has_password", "access_key"])
def test_known_false_positive_key_redacted(scrubber, key):
    out, notes = scrubber.scrub_attributes({key: "plain value 42"})
    assert out == {key: REDACTED}
    assert len(notes) == 1 and notes[0].startswith(f"{key}:key.")


@pytest.mark.parametrize("text,expected", [
    ("token: 7", f"token: {REDACTED}"),
    ("Token: Expired", f"Token: {REDACTED}"),
    ("password: The password must be 8 chars", f"password: {REDACTED} password must be 8 chars"),
    ("pwd: /home/bob", f"pwd: {REDACTED}"),
    ("private_key: /path/to/key.pem", f"private_key: {REDACTED}"),
    ("https://h/x?key=user:42", f"https://h/x?key={REDACTED}"),
    ("https://h/x?auth=basic", f"https://h/x?auth={REDACTED}"),
    ("https://h/x?page_token=abc", f"https://h/x?page_token={REDACTED}"),
    ("sku sk-blue-widget-2024-edition-pro", f"sku {REDACTED}"),
    ("ASIAPACIFICREGION123", REDACTED),
])
def test_known_false_positive_text_redacted(scrubber, text, expected):
    out, notes = scrubber.scrub_text(text)
    assert out == expected
    assert notes


# ----------------------------------------------------------------------------- shapes
def test_attribute_sequences_and_scalars(scrubber):
    attrs = {"tags": ("a", f"Bearer {JWT}", "c"), "n": 3, "ok": True, "f": 1.5, "ints": [1, 2]}
    out, notes = scrubber.scrub_attributes(attrs)
    assert out is not attrs and out["tags"] == ("a", f"Bearer {REDACTED}", "c") and out["n"] == 3
    assert out["ints"] is attrs["ints"]
    assert notes == ["tags[1]:value.bearer"]


def test_scrub_body_nested(scrubber):
    body = {"msg": "login ok", "user": {"name": "bob", "password": "hunter2"},
            "hdrs": [{"authorization": "Basic dXNlcjpwYXNz"}, "plain"], "url": "postgresql://u:p@h/d"}
    out, notes = scrubber.scrub_body(body)
    assert out["user"]["password"] == REDACTED and out["hdrs"][0]["authorization"] == REDACTED
    assert out["url"] == f"postgresql://u:{REDACTED}@h/d" and out["msg"] == "login ok"
    assert body["user"]["password"] == "hunter2"  # input untouched
    assert sorted(notes) == ["body.hdrs[0].authorization:key.authorization", "body.url:value.url_userinfo",
                             "body.user.password:key.password"]


def test_body_unchanged_returns_same_object(scrubber):
    body = {"msg": "hello", "items": [1, "two"]}
    out, notes = scrubber.scrub_body(body)
    assert out is body and notes == []
    assert scrubber.scrub_text("hello")[0] == "hello"


@pytest.mark.criterion('AC-15')
def test_scrub_argv(scrubber):
    argv = ["python", "app.py", "--db-password=hunter2", "--token", "abc", "--api-key", "abc", "-p", "hunter2",
            "--db-url", "postgresql://user:pass@host/db", "PGPASSWORD=x", "some_cmd", "-Dpassword=x", "--verbose"]
    out, notes = scrubber.scrub_argv(argv)
    assert out == ["python", "app.py", f"--db-password={REDACTED}", "--token", REDACTED, "--api-key", REDACTED,
                   "-p", "hunter2",  # single-letter flag is ambiguous (mysql -p vs psql -p port): kept
                   "--db-url", f"postgresql://user:{REDACTED}@host/db", f"PGPASSWORD={REDACTED}", "some_cmd",
                   f"-Dpassword={REDACTED}", "--verbose"]
    assert notes == ["argv[2]:key.password", "argv[4]:key.token", "argv[6]:key.key", "argv[10]:value.url_userinfo",
                     "argv[11]:key.password", "argv[13]:key.password"]
    clean = ["python", "-m", "pytest", "-q"]
    assert scrubber.scrub_argv(clean)[0] is clean


@pytest.mark.criterion('AC-15')
def test_scrub_argv_short_p_flag_keeps_the_next_argument(scrubber):
    argv = ["mysql", "-p", "hunter2"]
    assert scrubber.scrub_argv(argv) == (argv, [])


# ----------------------------------------------------------------------------- rules
def test_extra_rules():
    s = Scrubber(extra_rules=[Rule("acme_key", "value", r"acme_[a-z0-9]{8,}", boundary=True),
                              Rule("badge", "key", r"badge$")])
    out, notes = s.scrub_attributes({"m": "key acme_abcdefgh ok", "user.badge": "123", "x": "xacme_abcdefgh"})
    assert out == {"m": f"key {REDACTED} ok", "user.badge": REDACTED, "x": "xacme_abcdefgh"}
    assert notes == ["m:value.acme_key", "user.badge:key.badge"]


@pytest.mark.parametrize("pattern", [r"(?P<x>a)", r"(a)\1", r"\bword", r"a(?=b)", r"(?<!x)a", r"(?P<s>a)(?P=s)",
                                     r"(?>a|b)", r"a++"])
def test_rules_outside_the_regex_subset_are_rejected(pattern):
    with pytest.raises(ValueError):
        Scrubber(extra_rules=[Rule("bad", "value", pattern)])


def test_default_rules_stay_fsm_friendly():
    for r in DEFAULT_RULES:
        assert not NON_REGULAR.search(r.pattern), r.name
    tolerated = {r.name for r in VALUE_RULES if TOLERATED.search(r.pattern)}
    assert tolerated == {"pem", "bearer", "basic", "inline_kv", "url_query"}  # update the spec if this changes
    assert all(r.triggers for r in VALUE_RULES)  # every value rule has a literal prefilter trigger


def test_rule_names_unique():
    names = [r.name for r in DEFAULT_RULES]
    assert len(names) == len(set(names))
    assert {r.name for r in KEY_RULES} | {r.name for r in VALUE_RULES} == set(names)


def test_boundary_flag_is_honoured(scrubber):
    out, _ = scrubber.scrub_text("desk-fakefakefakefakefakefakefake and sk-fakefakefakefakefakefakefake")
    assert out == f"desk-fakefakefakefakefakefakefake and {REDACTED}"


@pytest.mark.parametrize("text", ["AKIAFAKEFAKEFAKEFAKEFAKE", "ASIAPACIFICREGION123X", "id=AKIAFAKEFAKEFAKEFAKE_more",
                                  "AIzaFAKEfakeFAKEfakeFAKEfakeFAKEfakeFAKtail"])
def test_fixed_length_keys_never_cut_a_longer_run(scrubber, text):
    out, notes = scrubber.scrub_text(text)
    assert out == text and notes == []


def test_fixed_length_keys_still_match_at_word_end(scrubber):
    assert scrubber.scrub_text("id=AKIAFAKEFAKEFAKEFAKE.")[0] == f"id={REDACTED}."
    assert scrubber.scrub_text("(AIzaFAKEfakeFAKEfakeFAKEfakeFAKEfakeFAK)")[0] == f"({REDACTED})"


# ----------------------------------------------------------------------------- engines agree
def _random_inputs(n=300, seed=0):
    rnd = random.Random(seed)
    atoms = ["password", "Password", "token", "tokens", "secret", "api_key", "Bearer", "Basic", "eyJ", "sk-", "AKIA",
             "ASIA", "AIza", "hvs.", "ghp_", "glpat-", "xoxb-", "sk_live_", "://", "@", "=", ":", "?", "&", " ", "\n",
             '"', "'", ".", "-", "_", "/", "+", "x", "Z", "7", "é", "-----BEGIN RSA PRIVATE KEY-----",
             "-----END RSA PRIVATE KEY-----", "user:pw", "abcdefghij", "ABCDEFGHIJKLMNOPQRST", "0123456789"]
    return ["".join(rnd.choice(atoms) for _ in range(rnd.randint(1, 40))) for _ in range(n)]


ADVERSARIAL = [("password" + " " * 300 + "x ") * 3,  # \s* run then no separator
               ("eyJ" + "A" * 300 + " ") * 3,  # jwt near-miss: {8,} run then no '.'
               "?" + "a" * 600 + "=1",  # url_query near-miss
               "Basic " + "A" * 600 + "!",  # base64 run, check fails
               "-----BEGIN RSA PRIVATE KEY-----" + "A" * 600,  # pem with no END
               "sk-" + "a" * 600, "hvs." + "b" * 600 + "." + "c" * 600, "AKIA" + "B" * 600]


def test_hyperscan_agrees_with_re_on_random_adversarial_and_example_inputs():
    pytest.importorskip("hyperscan")
    ref, hs = Scrubber(engine=RegexEngine()), Scrubber(engine=HyperscanEngine())
    corpus = _random_inputs() + ADVERSARIAL + [c[0] for c in REDACT_VALUES] + KEEP_VALUES
    for text in corpus:
        assert hs.scrub_text(text) == ref.scrub_text(text), text[:80]


# ----------------------------------------------------------------------------- overlap lint
def test_value_rules_do_not_overlap_except_the_known_pair():
    """
    interegular: two value rules whose languages intersect would fight over the same text. the known pair is
    ("url_userinfo", "inline_kv"). interegular cannot parse \\A / \\Z, so the rules using them (pem, url_query)
    are skipped
    """
    interegular = pytest.importorskip("interegular")
    fsms = {}
    for r in VALUE_RULES:
        try:
            fsms[r.name] = interegular.parse_pattern(re.sub(r"\(\?P<\w+>", "(?:", r.pattern)).to_fsm()
        except Exception:  # noqa: BLE001 - unsupported escape (\A, \Z)
            assert TOLERATED.search(r.pattern) and re.search(r"\\[AZ]", r.pattern), r.name
    assert {r.name for r in VALUE_RULES} - set(fsms) == {"pem", "url_query"}
    overlaps = {tuple(sorted(pair)) for pair in itertools.combinations(fsms, 2)
                if not (fsms[pair[0]] & fsms[pair[1]]).empty()}
    assert overlaps == {("inline_kv", "url_userinfo")}
