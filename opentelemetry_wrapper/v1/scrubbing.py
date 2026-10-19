"""
secret scrubbing for telemetry about to leave the process (OTW-8, DEC-58, DEC-16, DEC-74)

two kinds of rule, kept apart on purpose:

* key rules match the (lowercased) attribute key; a hit redacts the *whole* value
* value rules match text by format, whatever its key; only the secret part (named group ``s*``, else the whole
  match) is replaced, so messages stay readable (``Bearer [REDACTED]``, ``postgresql://user:[REDACTED]@db``)

rules are plain data in a registry, written in a regex subset an automaton library can handle (no backreferences, no
lookarounds; a leading or trailing word boundary is a flag, never ``\\b`` in the pattern; the only anchors are
``\\A``/``\\Z``; the only flag is scoped ``(?i:...)``), enforced when a rule is compiled. an ``Engine`` compiles the
rules into a ``Matcher``: ``RegexEngine`` (stdlib ``re``, the default: one alternation per boundary class, no
capturing groups, the rule that fired found by re-testing the rules on the matched text only, a literal prefilter on
texts of 32+ characters) or ``HyperscanEngine`` (optional, only when asked for; ``hyperscan`` is imported lazily).

the exporter wrappers scrub on the exporter thread, so the cost stays off the caller's path. nothing here raises: a
value that fails to scrub is replaced by ``[REDACTED: scrubbing failed]`` (fail closed, DEC-74), noted, and reported
once per site as one json line on stderr (DEC-75). redactions are listed in the ``opentelemetry_wrapper.scrubbed``
attribute as ``<path>:<kind>.<rule>`` (paths and rule names, never the values). anything not behind these wrappers (a
user's own processors and exporters) is not scrubbed
"""
from __future__ import annotations

import base64
import copy
import dataclasses
import fnmatch
import re
import threading
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence

from opentelemetry.attributes import BoundedAttributes
from opentelemetry.sdk.trace import Event, ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.sdk.util import BoundedList
from opentelemetry.trace import Link

from opentelemetry_wrapper.v1._warnings import report

__all__ = [
    'REDACTED', 'FAILED', 'NOTES_ATTRIBUTE', 'Rule', 'KEY_RULES', 'VALUE_RULES', 'DEFAULT_RULES',
    'DEFAULT_ALLOW_GLOBS', 'Engine', 'Matcher', 'RegexEngine', 'HyperscanEngine', 'Scrubber', 'default_scrubber',
    'set_default_scrubber', 'scrub_argv', 'scrub_mapping', 'scrub_text', 'ScrubbingSpanExporter',
    'ScrubbingLogExporter',
]

REDACTED = '[REDACTED]'
FAILED = '[REDACTED: scrubbing failed]'  # DEC-74: distinct from REDACTED
NOTES_ATTRIBUTE = 'opentelemetry_wrapper.scrubbed'
Note = str  # "<path>:<kind>.<rule>", e.g. "http.url:value.url_query", "argv[3]:key.password", "a:error.ValueError"
_SEP = r'[._-]'


# ----------------------------------------------------------------------------------------------- failure reporting
_UNKNOWN = object()  # no value to describe


def _shape(value: Any, path: str | None) -> dict[str, Any]:
    """
    what may be said about a value that failed to scrub (DEC-94): its type, its length where it has one, and its path
    (named as in the notes); never its ``__str__`` or ``__repr__``; a failing ``__len__`` just leaves the length out
    """
    shape: dict[str, Any] = {}
    if value is not _UNKNOWN:
        try:
            t = type(value)
            shape['value.type'] = f'{t.__module__}.{t.__qualname__}'
        except Exception:  # noqa: BLE001 - e.g. a class whose __module__ or __qualname__ is odd
            pass
        try:
            shape['value.length'] = len(value)
        except Exception:  # noqa: BLE001 - unsized, or a __len__ that raises
            pass
    if path is not None:
        shape['value.path'] = path
    return shape


def _report(exc: BaseException, site: str, value: Any = _UNKNOWN, path: str | None = None) -> None:
    """a scrubbing failure goes through the wrapper's one reporter (DEC-75): one stderr JSON line per (site, exception
    type), every occurrence with ``OTEL_WRAPPER_DEBUG=true``; the message is withheld, debug or not, since it may hold
    the value (DEC-74, DEC-94), and the record carries the value's shape instead: ``value.type``, ``value.length``,
    ``value.path``, each absent when unknown"""
    try:
        fields = _shape(value, path)
    except Exception:  # noqa: BLE001 - the report goes out regardless
        fields = {}
    report(f'scrubbing.{site}', exc, withhold_message=True, fields=fields)


# ----------------------------------------------------------------------------------------------- rules
@dataclass(frozen=True)
class Rule:
    name: str  # an identifier; appears in notes
    kind: str  # "key" | "value"
    pattern: str  # the regex subset: no backrefs/lookarounds/\b; named groups only s, s1, s2...; scoped (?i:) ok
    doc: str = ''
    check: Callable[[str], bool] | None = None  # optional veto, run on the secret text after a match
    triggers: tuple[str, ...] = ()  # lowercase literals; any match MUST contain one of them (the prefilter)
    boundary: bool = False  # value rules: the match must start at a word boundary (the engine supplies the \b)
    end_boundary: bool = False  # value rules: ... and end at one (fixed-length keys: never cut a longer run)


def _k(name: str, pattern: str, doc: str = '') -> Rule:
    return Rule(name, 'key', pattern, doc)


def _v(name: str, pattern: str, *triggers: str, doc: str = '', check: Callable[[str], bool] | None = None,
       boundary: bool = True, end_boundary: bool = False) -> Rule:
    return Rule(name, 'value', pattern, doc, check, triggers, boundary, end_boundary)


def _looks_random(s: str) -> bool:
    """veto plain words ("Bearer authentication"): need a digit, a symbol, or an inner upper-case letter"""
    return any(c.isdigit() or c in '._-+/=' for c in s) or any(c.isupper() for c in s[1:])


def _is_b64_userpass(s: str) -> bool:
    try:
        return b':' in base64.b64decode(s + '=' * (-len(s) % 4), validate=True)
    except Exception:  # noqa: BLE001
        return False


KEY_RULES: tuple[Rule, ...] = (
    _k('password', r'(?:pass(?:word|wd|phrase)|pwd)$',
       'password, db_password, user.password, PGPASSWORD, MYSQL_PWD; not password_policy/passwordless'),
    _k('secret', rf'secret(?:{_SEP}?(?:access{_SEP}?)?key)?$',
       'secret, client_secret, secret_key, aws_secret_access_key; not secret_name'),
    _k('key', rf'(?:api|private|access|secret|signing|encryption|master){_SEP}?key$',
       "api_key, apikey, x-api-key, private_key; never bare 'key' (keyboard, monkey, routing_key)"),
    _k('token', rf'(?:^|{_SEP})token$',
       "'token' as the last key segment: access_token, x-csrf-token; not input_tokens/tokenizer/token_count"),
    _k('authorization', r'authorization$', 'authorization, proxy-authorization; not author/authority'),
    _k('cookie', r'cookies?$', 'cookie, set-cookie'),
    _k('credentials', r'credentials?$'),
    _k('session_id', rf'session{_SEP}?id$'),
)

# secret names for inline key=value text, grouped by first letter so the regex engine rejects most words after one
# character. 'credentials' is deliberately absent: inline it hits X-Amz-Credential=<key id>, which is not a secret
_KV_NAMES = (r'(?:[pP](?i:ass(?:word|wd|phrase)|wd|rivate[_-]?key)|[sS](?i:ecret(?:[_-]?key)?|ession[_-]token)'
             r'|[cC](?i:lient[_-]?secret|srf[_-]token)|[aA](?i:pi[_-]?key|ccess[_-]token|uth[_-]token|uthorization)'
             r'|[iI](?i:d[_-]token)|[rR](?i:efresh[_-]token)|[bB](?i:earer[_-]token)|[tT](?i:oken))')
_QUOTED = r'"(?P<s{a}>[^"]*)"|\'(?P<s{b}>[^\']*)\''
_QUERY_NAMES = (r'(?:[\w-]+[_-])?(?:token|secret|signature|password|passwd|pwd)'  # X-Amz-Signature, ...-Token
                r'|api[_-]?key|apikey|access[_-]?key|private[_-]?key|key|sig|auth')  # not X-Amz-Credential (key id)

VALUE_RULES: tuple[Rule, ...] = (
    _v('pem', r'-----BEGIN [A-Z ]*PRIVATE KEY-----(?P<s>[\s\S]*?)(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)',
       '-----begin', doc='PEM private key body; the markers are kept', boundary=False),
    _v('bearer', r'(?i:bearer)\s+(?P<s>[A-Za-z0-9._~+/=-]{12,})', 'bearer', check=_looks_random),
    _v('basic', r'(?i:basic)\s+(?P<s>[A-Za-z0-9+/]{8,}={0,2})', 'basic', doc='Basic <base64 user:pass>',
       check=_is_b64_userpass),
    _v('jwt', r'eyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}', 'eyj', doc='bare JWT, k8s SA token'),
    _v('vault_token', r'hv[sbr]\.[A-Za-z0-9_-]{20,}', 'hvs.', 'hvb.', 'hvr.'),
    _v('github_token', r'gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}',
       'ghp_', 'gho_', 'ghu_', 'ghs_', 'ghr_', 'github_pat_'),
    _v('gitlab_token', r'glpat-[A-Za-z0-9_.-]{20,}', 'glpat-'),
    _v('slack_token', r'xox[abpors]-[A-Za-z0-9-]{10,}', 'xox'),
    _v('stripe_key', r'[sr]k_(?:live|test)_[A-Za-z0-9]{10,}', 'k_live_', 'k_test_'),
    _v('aws_access_key_id', r'(?:AKIA|ASIA)[A-Z0-9]{16}', 'akia', 'asia', end_boundary=True),
    _v('google_api_key', r'AIza[A-Za-z0-9_-]{35}', 'aiza', end_boundary=True),
    _v('sk_api_key', r'sk-(?:ant-)?[A-Za-z0-9_-]{20,}', 'sk-', doc='OpenAI / Anthropic style'),
    _v('url_userinfo', r'[A-Za-z][A-Za-z0-9+.-]*://[^\s/@:]*:(?P<s>[^\s/@]+)@', '://', doc='scheme://user:PW@host'),
    _v('inline_kv',
       _KV_NAMES + r'(?:["\']?\s*(?:[:=]|=>)\s*(?:' + _QUOTED.format(a=1, b=2)
       + r'|(?:(?i:bearer|basic)\s+)?(?P<s3>[^\s"\',;&]+))|\s+(?:' + _QUOTED.format(a=4, b=5) + '))',
       'pass', 'pwd', 'secret', 'api', 'token', 'authorization', 'private',
       doc='key=value / key: value / "key": "value" / SQL PASSWORD \'literal\' in free text, JSON, SQL'),
    _v('url_query', rf'(?:\A|[?&;])(?i:{_QUERY_NAMES})=(?P<s>[^&\s#]+)',
       'token=', 'secret=', 'signature=', 'password=', 'passwd=', 'pwd=', 'key=', 'sig=', 'auth=',
       doc='?token=..&sig=..&X-Amz-Signature=..', boundary=False),
)
DEFAULT_RULES: tuple[Rule, ...] = KEY_RULES + VALUE_RULES
# DEC-2: the x-userinfo claims left after its denylist are recorded as-is (a generic scrubber mangles auth_time, iss)
DEFAULT_ALLOW_GLOBS: tuple[str, ...] = ('http.request.header.x-userinfo.*',)

# constructs an automaton engine cannot take, never allowed in a rule: lookarounds, \b, backrefs, atomic groups,
# possessive quantifiers
NON_REGULAR = re.compile(r'\(\?<?[=!]|\\[bB]|\(\?P=|\\\d|\(\?>|[*+?}][+]')
TOLERATED = re.compile(r'\\[AZ]|\(\?i:')  # anchors and scoped case-folding: an automaton engine expands these


# ----------------------------------------------------------------------------------------------- engine interface
class Matcher(Protocol):
    def key(self, key: str) -> str | None: ...  # the name of the key rule that fired, or None

    def sub(self, text: str) -> tuple[str, list[str]]: ...  # (new text, names of the value rules that fired)


class Engine(Protocol):
    def compile(self, rules: Sequence[Rule]) -> Matcher: ...


_GROUP = re.compile(r'\(\?P<(s\d*)>')


def prepare(rule: Rule, named: bool = True) -> tuple[str, list[str]]:
    """
    rename secret groups s* -> rule__s* (so rules can be merged), or drop every group when ``named`` is False;
    reject constructs outside the subset. returns (pattern, secret group names)
    """
    if not rule.name.isidentifier():
        raise ValueError(f'rule {rule.name!r}: the name must be an identifier')
    names: list[str] = []
    pat = _GROUP.sub(lambda m: names.append(f'{rule.name}__{m.group(1)}') or f'(?P<{names[-1]}>', rule.pattern)
    if re.search(rf'\(\?P<(?!{rule.name}__)', pat) or NON_REGULAR.search(pat):
        raise ValueError(f'rule {rule.name!r}: only s* named groups; no backrefs, lookarounds, \\b, atomic or '
                         f'possessive constructs')
    if not named:
        pat, names = re.sub(r'\(\?P<\w+>', '(?:', pat), []
    return pat, names


def bounded(rule: Rule, pat: str) -> str:
    return (r'\b' if rule.boundary else '') + f'(?:{pat})' + (r'\b' if rule.end_boundary else '')


def _apply(m: re.Match, rule: Rule, idxs: list[int]) -> str | None:
    """the replacement for one match, or None when the rule's check vetoes it"""
    whole, base = m.group(0), m.start()
    for g in idxs:
        if m.start(g) != -1:
            s0, s1 = m.start(g) - base, m.end(g) - base
            break
    else:
        s0, s1 = 0, len(whole)
    if rule.check is not None and not rule.check(whole[s0:s1]):
        return None
    return whole[:s0] + REDACTED + whole[s1:]


class _ReMatcher:
    def __init__(self, rules: Sequence[Rule], prefilter: bool, prefilter_min_len: int):
        keys = [f'(?P<{r.name}>{prepare(r)[0]})' for r in rules if r.kind == 'key']
        self._key_re = re.compile('|'.join(keys)) if keys else None
        vals = [r for r in rules if r.kind == 'value']
        vals.sort(key=lambda r: (not r.boundary, not r.end_boundary))  # the factored alternation's order
        self._vals: list[tuple[Rule, re.Pattern, list[int]]] = []  # (rule, own regex, secret group indices)
        for r in vals:
            pat, names = prepare(r)
            rx = re.compile(bounded(r, pat))
            self._vals.append((r, rx, [rx.groupindex[n] for n in names]))
        self._val_re = None
        if vals:  # one alternation per boundary class, the shared \b factored out, no groups
            parts, seen = [], []
            for r in vals:
                cls = (r.boundary, r.end_boundary)
                if cls not in seen:
                    seen.append(cls)
                    same = [f'(?:{prepare(x, named=False)[0]})' for x in vals if (x.boundary, x.end_boundary) == cls]
                    parts.append((r'\b' if cls[0] else '') + '(?:' + '|'.join(same) + ')' + (r'\b' if cls[1] else ''))
            self._val_re = re.compile('|'.join(parts))
        ok = prefilter and vals and all(r.triggers for r in vals)
        self._triggers = tuple({t for r in vals for t in r.triggers}) if ok else None
        self._min_len = prefilter_min_len

    def key(self, key: str) -> str | None:
        m = self._key_re.search(key.lower()) if self._key_re else None
        return m.lastgroup if m else None

    def _skip(self, text: str) -> bool:
        if self._triggers is not None and len(text) >= self._min_len:
            low = text.lower()
            return not any(t in low for t in self._triggers)
        return False

    def sub(self, text: str) -> tuple[str, list[str]]:
        fired: list[str] = []
        if self._val_re is None or self._skip(text):
            return text, fired

        def repl(m: re.Match) -> str:
            for rule, rx, idxs in self._vals:  # the first rule (alternation order) matching here with the same end
                mm = rx.match(text, m.start())
                if mm and mm.end() == m.end():
                    out = _apply(mm, rule, idxs)
                    if out is None:
                        return m.group(0)
                    fired.append(rule.name)
                    return out
            fired.append('unidentified')  # cannot happen with re; fail closed if it ever does
            return REDACTED

        new = self._val_re.sub(repl, text)
        return (new, fired) if fired else (text, fired)


class RegexEngine:
    """the default engine: stdlib ``re``, one alternation per boundary class, no groups, literal prefilter"""

    def __init__(self, prefilter: bool = True, prefilter_min_len: int = 32):
        self.prefilter, self.prefilter_min_len = prefilter, prefilter_min_len

    def compile(self, rules: Sequence[Rule]) -> Matcher:
        return _ReMatcher(rules, self.prefilter, self.prefilter_min_len)


_HS_CACHE: dict = {}  # expressions tuple -> compiled hyperscan.Database (compiling costs ~0.8 s)
_HS_LOCK = threading.Lock()
_NON_ASCII = r'\x{80}-\x{10FFFF}'


def _hs_expr(pat: str) -> str:
    """
    rule pattern -> Hyperscan (PCRE) expression: no captures; \\Z -> \\z; Hyperscan's \\w and \\s are ASCII-only
    (UCP forbids \\b), so widen them with every non-ASCII code point in *positive* contexts (bare, or inside a
    non-negated class) so Hyperscan over-reports rather than misses; the rule's own re regex decides the exact span
    """
    pat = re.sub(r'\(\?P<\w+>', '(?:', pat).replace(r'\Z', r'\z')
    out, i = [], 0
    for m in re.finditer(r'\[(\^?)(?:\\.|[^\]\\])+\]|\\[ws]', pat):
        tok = m.group(0)
        if tok.startswith('['):
            if not m.group(1) and re.search(r'\\[ws]', tok):
                tok = '[' + _NON_ASCII + tok[1:]  # first in the class, so it cannot be misread as a range end
        else:
            tok = f'[{tok}{_NON_ASCII}]'
        out.append(pat[i:m.start()] + tok)
        i = m.end()
    return ''.join(out) + pat[i:]


class _HsMatcher(_ReMatcher):
    """
    one Hyperscan database for every value rule. Hyperscan reports every end offset of an open-ended match, and with
    SOM_LEFTMOST only the leftmost start per end, so take the leftmost start of a scan, let the rule's own ``re``
    regex (matched there) decide the rule, exact end, secret group and check, then rescan from that end. byte
    offsets are mapped back to str indices; one scratch space per thread
    """

    def __init__(self, rules: Sequence[Rule], prefilter: bool, prefilter_min_len: int):
        import hyperscan  # optional: only imported when this engine is asked for
        super().__init__(rules, prefilter, prefilter_min_len)
        self._hs, self._local = hyperscan, threading.local()
        exprs = tuple(_hs_expr(bounded(r, r.pattern)).encode() for r, _, _ in self._vals)
        with _HS_LOCK:
            self._db = _HS_CACHE.get(exprs)
            if self._db is None and exprs:
                self._db = _HS_CACHE[exprs] = hyperscan.Database()
                flags = hyperscan.HS_FLAG_SOM_LEFTMOST | hyperscan.HS_FLAG_UTF8
                self._db.compile(expressions=list(exprs), ids=list(range(len(exprs))), flags=[flags] * len(exprs))

    def _scratch(self):
        sc = getattr(self._local, 'scratch', None)
        if sc is None:
            sc = self._local.scratch = self._hs.Scratch(self._db)
        return sc

    def sub(self, text: str) -> tuple[str, list[str]]:
        fired: list[str] = []
        if self._db is None or self._skip(text):
            return text, fired
        data, ascii_ = text.encode('utf-8'), text.isascii()

        def chars(nbytes: int) -> int:
            return nbytes if ascii_ else len(data[:nbytes].decode('utf-8', 'ignore'))

        out, pos, win_b, win_c, scratch = [], 0, 0, 0, self._scratch()  # pos: consumed chars; win: scan window
        while win_b < len(data):
            starts: dict[int, set] = {}  # byte start (relative to the window) -> rule indices reported there

            def on_match(idx, start, end, flags, ctx):
                starts.setdefault(start, set()).add(idx)

            self._db.scan(data[win_b:], match_event_handler=on_match, scratch=scratch)
            if not starts:
                break
            hit = None
            for sb in sorted(starts):  # leftmost start first; the rule's own re regex is the arbiter
                start = win_c + chars(win_b + sb) - chars(win_b)
                for idx in sorted(starts[sb]):
                    rule, rx, idxs = self._vals[idx]
                    mm = rx.match(text, start)  # None: Hyperscan over-reported; such a span is not a secret
                    if mm is None:
                        continue
                    rep = _apply(mm, rule, idxs)
                    if rep is None:
                        continue  # vetoed by the check
                    hit = (start, mm.end(), rep, rule.name)
                    break
                if hit:
                    break
            if hit:
                start, end, rep, name = hit
                fired.append(name)
                out.append(text[pos:start] + rep)
                pos = win_c = end
                win_b = end if ascii_ else len(text[:end].encode('utf-8'))
            else:  # every start rejected: step past the leftmost (to the next UTF-8 character boundary) and rescan
                win_b += min(starts) + 1
                while win_b < len(data) and (data[win_b] & 0xC0) == 0x80:
                    win_b += 1
                win_c = chars(win_b)
        if not fired:
            return text, fired
        out.append(text[pos:])
        return ''.join(out), fired


class HyperscanEngine:
    """the optional fast engine (DEC-16); needs ``hyperscan``, which is not a declared dependency yet"""

    def __init__(self, prefilter: bool = False, prefilter_min_len: int = 32):
        self.prefilter, self.prefilter_min_len = prefilter, prefilter_min_len

    def compile(self, rules: Sequence[Rule]) -> Matcher:
        return _HsMatcher(rules, self.prefilter, self.prefilter_min_len)


def _engine(engine: Engine | str | None) -> Engine:
    if engine is None or engine == 're':
        return RegexEngine()
    if engine == 'hyperscan':
        return HyperscanEngine()
    if engine == 'auto':  # DEC-16: picked once, from what is installed, falling back to re
        try:
            import hyperscan  # noqa: F401
        except ImportError:
            return RegexEngine()
        return HyperscanEngine()
    if isinstance(engine, str):
        raise ValueError(f'unknown scrubbing engine {engine!r}: use "re", "hyperscan" or "auto"')
    return engine


# ----------------------------------------------------------------------------------------------- scrubber
_ARGV_KV = re.compile(r'^(-{0,2}[A-Za-z_][\w.-]*)=(.*)$', re.S)  # --db-password=x, PGPASSWORD=x, -Dpassword=x
_ARGV_FLAG = re.compile(r'^--?([A-Za-z_][\w.-]+)$')  # --token, --api-key (2+ char names: '-p' is ambiguous)


def _note_failed(exc: BaseException, path: str, notes: list[Note]) -> str:
    notes.append(f'{path}:error.{type(exc).__name__}')
    return FAILED


def _failed(exc: BaseException, path: str, notes: list[Note], site: str, value: Any = _UNKNOWN) -> str:
    _report(exc, site, value, path)
    return _note_failed(exc, path, notes)


class Scrubber:
    """
    every public method returns ``(scrubbed, notes)``, the *same* object when nothing changed, and never raises:
    a value that fails to scrub becomes ``FAILED`` with a ``<path>:error.<exception type>`` note
    """

    def __init__(self, rules: Iterable[Rule] = DEFAULT_RULES, extra_rules: Iterable[Rule] = (),
                 allow_keys: Iterable[str] = (), allow_globs: Iterable[str] = DEFAULT_ALLOW_GLOBS,
                 engine: Engine | str | None = None):
        self.rules = tuple(rules) + tuple(extra_rules)
        names = [r.name for r in self.rules]
        if len(names) != len(set(names)):
            raise ValueError('rule names must be unique')
        self._m = _engine(engine).compile(self.rules)
        self._allow_exact = frozenset(allow_keys)
        globs = [fnmatch.translate(g) for g in allow_globs]
        self._allow_re = re.compile('|'.join(globs)) if globs else None

    def allowed(self, key: str) -> bool:
        return key in self._allow_exact or bool(self._allow_re and self._allow_re.match(key))

    def scrub_attributes(self, attrs: Mapping[str, Any], path: str = '') -> tuple[Mapping[str, Any], list[Note]]:
        notes: list[Note] = []
        try:
            return self._scrub_mapping(attrs, path, notes, fail_soft=True), notes
        except Exception as exc:  # noqa: BLE001 - e.g. a mapping whose iteration raises
            _report(exc, 'scrub_attributes', attrs, path or '*')  # the mapping as a whole failed: one report
            try:
                return {k: _note_failed(exc, f'{path}.{k}' if path else str(k), notes) for k in attrs}, notes
            except Exception as exc2:  # noqa: BLE001
                _failed(exc2, path or '*', notes, 'scrub_attributes', attrs)
                return {}, notes

    def scrub_text(self, text: str, path: str = 'body') -> tuple[str, list[Note]]:
        return self.scrub_body(text, path)

    def scrub_body(self, value: Any, path: str = 'body') -> tuple[Any, list[Note]]:
        notes: list[Note] = []
        try:
            return self._scrub_any(value, path, notes, fail_soft=True), notes
        except Exception as exc:  # noqa: BLE001
            return _failed(exc, path, notes, 'scrub_body', value), notes

    def scrub_argv(self, argv: Sequence[str]) -> tuple[list[str], list[Note]]:
        out, notes, pending = list(argv), [], None
        for i, arg in enumerate(argv):
            try:
                if pending:
                    out[i] = REDACTED
                    notes.append(f'argv[{i}]:key.{pending}')
                    pending = None
                    continue
                if (m := _ARGV_KV.match(arg)) and (rule := self._m.key(m.group(1).lstrip('-'))):
                    out[i] = f'{m.group(1)}={REDACTED}'
                    notes.append(f'argv[{i}]:key.{rule}')
                elif (m := _ARGV_FLAG.match(arg)) and (rule := self._m.key(m.group(1))):
                    pending = rule
                else:
                    out[i] = self._scrub_any(arg, f'argv[{i}]', notes)
            except Exception as exc:  # noqa: BLE001
                out[i] = _failed(exc, f'argv[{i}]', notes, 'scrub_argv', arg)
        if notes or not isinstance(argv, list):
            return out, notes
        return argv, notes

    # -- internals
    def _scrub_mapping(self, m: Mapping, path: str, notes: list[Note], fail_soft: bool = False) -> Mapping:
        out = None
        for k, v in m.items():
            p = f'{path}.{k}' if path else str(k)
            try:
                nv = self._scrub_item(str(k), v, p, notes, fail_soft)
            except Exception as exc:  # noqa: BLE001
                if not fail_soft:
                    raise
                nv = _failed(exc, p, notes, 'scrub_mapping', v)
            if nv is not v:
                if out is None:
                    out = dict(m)
                out[k] = nv
        return m if out is None else out

    def _scrub_item(self, key: str, value: Any, path: str, notes: list[Note], fail_soft: bool) -> Any:
        if self.allowed(key):
            return value
        rule = self._m.key(key)
        if rule:
            notes.append(f'{path}:key.{rule}')
            return REDACTED
        return self._scrub_any(value, path, notes, fail_soft)

    def _scrub_any(self, value: Any, path: str, notes: list[Note], fail_soft: bool = False) -> Any:
        if isinstance(value, str):
            new, fired = self._m.sub(value)
            notes.extend(f'{path}:value.{r}' for r in fired)
            return new if fired else value
        if isinstance(value, Mapping):
            return self._scrub_mapping(value, path, notes, fail_soft)
        if isinstance(value, (list, tuple)):
            items = []
            for i, v in enumerate(value):
                try:
                    items.append(self._scrub_any(v, f'{path}[{i}]', notes, fail_soft))
                except Exception as exc:  # noqa: BLE001
                    if not fail_soft:
                        raise
                    items.append(_failed(exc, f'{path}[{i}]', notes, 'scrub_sequence', v))
            if all(a is b for a, b in zip(items, value)):
                return value
            return tuple(items) if isinstance(value, tuple) else items
        return value  # bool/int/float/None/bytes: nothing to scan


_default: Scrubber | None = None
_default_lock = threading.Lock()


def default_scrubber() -> Scrubber:
    """the one scrubber the exporters, the stderr json logs and `scrub_argv` share (built on first use, engine re)"""
    global _default
    if _default is None:
        with _default_lock:
            if _default is None:
                _default = Scrubber()
    return _default


def set_default_scrubber(scrubber: Scrubber | None) -> None:
    """for configure: e.g. ``set_default_scrubber(Scrubber(engine='auto'))``; None resets to the default"""
    global _default
    _default = scrubber


def scrub_argv(argv: Sequence[str]) -> list[str]:
    """for ``process.command_args``: a secret-named flag's next argument, ``--flag=secret``, URL passwords"""
    return default_scrubber().scrub_argv(argv)[0]


def scrub_mapping(mapping: Mapping[str, Any]) -> Mapping[str, Any]:
    """for the stderr json logs: key rules on every key (nested too), value rules on every string"""
    return default_scrubber().scrub_attributes(mapping)[0]


def scrub_text(text: str) -> str:
    """value rules only (messages, exception text, stack traces)"""
    return default_scrubber().scrub_text(text)[0]


# ----------------------------------------------------------------------------------------------- exporters
def _keep_dropped(new: Mapping, dropped: int, extended: bool = False) -> Mapping:
    """keep the original's dropped-attribute count, which the SDK reads off a BoundedAttributes"""
    if not dropped:
        return dict(new)
    b = BoundedAttributes(None, new, immutable=True, extended_attributes=extended)
    b.dropped = dropped
    return b


def _keep_dropped_list(new: list, dropped: int) -> Sequence:
    if not dropped:
        return tuple(new)
    b = BoundedList.from_seq(None, new)
    b.dropped = dropped
    return b


def _with_notes(attrs: Mapping, notes: list[Note]) -> dict:
    out = dict(attrs)
    out[NOTES_ATTRIBUTE] = tuple(dict.fromkeys(notes))  # deduplicated, in order
    return out


class _Wrapper:
    def __init__(self, inner: Any, scrubber: Scrubber | None = None):
        self.inner = inner
        self._scrubber = scrubber

    @property
    def scrubber(self) -> Scrubber:
        return self._scrubber or default_scrubber()

    def shutdown(self, *args: Any, **kwargs: Any) -> Any:
        return self.inner.shutdown(*args, **kwargs)

    def force_flush(self, *args: Any, **kwargs: Any) -> Any:
        return self.inner.force_flush(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:  # e.g. InMemorySpanExporter.get_finished_spans
        if name == 'inner':
            raise AttributeError(name)
        return getattr(self.inner, name)


class ScrubbingSpanExporter(_Wrapper, SpanExporter):
    """scrubs span attributes, event attributes and link attributes, then hands the spans to ``inner``"""

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        out = []
        for span in spans:
            try:
                out.append(self._scrub(span))
            except Exception as exc:  # noqa: BLE001 - fail closed: never export the span unscrubbed
                _report(exc, 'ScrubbingSpanExporter.export', span, '*')
                try:  # what is left: the span without its attributes, events and links, and a note
                    out.append(ReadableSpan(
                        name=span.name, context=span.context, parent=span.parent, resource=span.resource,
                        attributes={NOTES_ATTRIBUTE: (f'*:error.{type(exc).__name__}',)}, kind=span.kind,
                        status=span.status, start_time=span.start_time, end_time=span.end_time,
                        instrumentation_scope=span.instrumentation_scope))
                except Exception as exc2:  # noqa: BLE001 - not even that: drop the span
                    _report(exc2, 'ScrubbingSpanExporter.export.fallback', span, '*')
        return self.inner.export(out)

    def _scrub(self, span: ReadableSpan) -> ReadableSpan:
        s, notes = self.scrubber, []
        old_attrs = span.attributes
        attrs, n = s.scrub_attributes(old_attrs) if old_attrs else (old_attrs, [])
        notes += n
        events, ev_changed = [], False
        for i, ev in enumerate(span.events):
            new, n = s.scrub_attributes(ev.attributes, f'events[{i}]') if ev.attributes else (ev.attributes, [])
            notes += n
            if new is not ev.attributes:
                ev_changed = True
                ev = Event(ev.name, _keep_dropped(new, getattr(ev, 'dropped_attributes', 0)), ev.timestamp)
            events.append(ev)
        links, ln_changed = [], False
        for i, ln in enumerate(span.links):
            new, n = s.scrub_attributes(ln.attributes, f'links[{i}]') if ln.attributes else (ln.attributes, [])
            notes += n
            if new is not ln.attributes:
                ln_changed = True
                ln = Link(ln.context, _keep_dropped(new, ln.dropped_attributes))
            links.append(ln)
        if not notes and attrs is old_attrs and not ev_changed and not ln_changed:
            return span
        return ReadableSpan(
            name=span.name, context=span.context, parent=span.parent, resource=span.resource,
            attributes=_keep_dropped(_with_notes(attrs or {}, notes), span.dropped_attributes),
            events=_keep_dropped_list(events, span.dropped_events),
            links=_keep_dropped_list(links, span.dropped_links),
            kind=span.kind, status=span.status, start_time=span.start_time, end_time=span.end_time,
            instrumentation_scope=span.instrumentation_scope,
        )


class ScrubbingLogExporter(_Wrapper):
    """scrubs log record attributes and body, then hands the records to ``inner`` (a LogRecordExporter)"""

    def export(self, batch: Sequence[Any]) -> Any:
        out = []
        for rec in batch:
            try:
                out.append(self._scrub(rec))
            except Exception as exc:  # noqa: BLE001 - fail closed: never export the record unscrubbed
                _report(exc, 'ScrubbingLogExporter.export', rec, '*')
                try:  # what is left: the record with its body and attributes dropped, and a note
                    new = copy.copy(rec.log_record)
                    new.body = FAILED
                    new.attributes = {NOTES_ATTRIBUTE: (f'*:error.{type(exc).__name__}',)}
                    out.append(dataclasses.replace(rec, log_record=new))
                except Exception as exc2:  # noqa: BLE001 - not even that: drop the record
                    _report(exc2, 'ScrubbingLogExporter.export.fallback', rec, '*')
        return self.inner.export(out)

    def _scrub(self, rec: Any) -> Any:
        s, lr = self.scrubber, rec.log_record
        old_attrs = lr.attributes
        attrs, notes = s.scrub_attributes(old_attrs) if old_attrs else (old_attrs, [])
        body, n = s.scrub_body(lr.body)
        notes += n
        if not notes and attrs is old_attrs and body is lr.body:
            return rec
        new = copy.copy(lr)
        dropped = old_attrs.dropped if isinstance(old_attrs, BoundedAttributes) else 0
        new.attributes = _keep_dropped(_with_notes(attrs or {}, notes), dropped, extended=True)
        new.body = body
        return dataclasses.replace(rec, log_record=new)
