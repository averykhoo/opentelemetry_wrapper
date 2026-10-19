"""
AC-21 (OTW-14): `reveal_type` under mypy for every form of `otel`, so the decorated object keeps its exact type

`samples/forms.py` is never run, only type-checked: mypy runs once over it, and each `reveal_type(...)` line's
`# R: <type>` comment is compared with what mypy revealed on that line. A `# E: <code>` comment marks a line that must
be a mypy error with that code (the signature is kept, so a wrong call is caught), and any other error fails.
pyright is not covered: it needs node, which this repo never has (OTW-14 says "if available").
"""
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict
from typing import List
from typing import NamedTuple
from typing import Tuple

import pytest

pytest.importorskip('mypy')

_HERE = Path(__file__).resolve().parent
_SAMPLE = _HERE / 'samples' / 'forms.py'
_REPO = _HERE.parents[1]
_OUTPUT_LINE = re.compile(r'^(?P<file>.+?):(?P<line>\d+): (?P<severity>error|note): (?P<message>.*?)(?:  \[(?P<code>[\w-]+)])?$')
_REVEALED = re.compile(r'^Revealed type is "(?P<type>.*)"$')


class _Line(NamedTuple):
    number: int
    source: str
    expected: str


def _comments(marker: str) -> List[_Line]:
    found = []
    for number, source in enumerate(_SAMPLE.read_text(encoding='utf-8').splitlines(), start=1):
        match = re.search(rf'#\s*{marker}:\s*(?P<expected>\S.*?)\s*$', source)
        if match and not source.lstrip().startswith('#'):
            found.append(_Line(number, source.split('#')[0].strip(), match.group('expected')))
    return found


_REVEAL_LINES = [line for line in _comments('R') if line.source.startswith('reveal_type(')]
_ERROR_LINES = _comments('E')


@pytest.fixture(scope='module')
def mypy_output() -> Tuple[Dict[int, List[str]], Dict[int, List[str]], str]:
    """mypy over the samples once: (revealed types, error codes by line, the raw output); the package's own errors
    are not this test's business (`--follow-imports=silent`), only what is reported in the samples"""
    proc = subprocess.run(
        [sys.executable, '-m', 'mypy', '--config-file', str(_REPO / 'pyproject.toml'), '--follow-imports=silent',
         '--no-error-summary', '--show-error-codes', '--hide-error-context', str(_SAMPLE)],
        cwd=_REPO, capture_output=True, text=True, encoding='utf-8')
    revealed: Dict[int, List[str]] = {}
    errors: Dict[int, List[str]] = {}
    for raw in proc.stdout.splitlines():
        match = _OUTPUT_LINE.match(raw)
        if not match or Path(match.group('file')).name != _SAMPLE.name:
            continue
        line = int(match.group('line'))
        if match.group('severity') == 'note':
            revealed_match = _REVEALED.match(match.group('message'))
            if revealed_match:
                revealed.setdefault(line, []).append(revealed_match.group('type'))
        else:
            errors.setdefault(line, []).append(match.group('code') or match.group('message'))
    assert revealed, f'mypy revealed nothing (exit {proc.returncode}):\n{proc.stdout}\n{proc.stderr}'
    return revealed, errors, proc.stdout


@pytest.mark.parametrize('line', _REVEAL_LINES, ids=lambda line: f'{line.number}:{line.source}')
def test_revealed_type(line: _Line, mypy_output) -> None:
    revealed, _, raw = mypy_output
    assert revealed.get(line.number) == [line.expected], raw


@pytest.mark.parametrize('line', _ERROR_LINES, ids=lambda line: f'{line.number}:{line.source}')
def test_wrong_call_is_an_error(line: _Line, mypy_output) -> None:
    _, errors, raw = mypy_output
    assert errors.get(line.number) == [line.expected], raw


def test_no_other_errors(mypy_output) -> None:
    _, errors, raw = mypy_output
    expected = {line.number for line in _ERROR_LINES}
    unexpected = {number: codes for number, codes in errors.items() if number not in expected}
    assert not unexpected, raw


def test_the_samples_are_not_empty() -> None:
    # the forms AC-21 names; a sample lost in an edit must not pass silently
    text = _SAMPLE.read_text(encoding='utf-8')
    for form in ('async def', 'yield', '@classmethod', '@staticmethod', '@otel\nclass', "@otel('", 'otel.instrument(',
                 'with otel as', "with otel('x') as", 'async with otel'):
        assert form in text, form
    assert len(_REVEAL_LINES) >= 35
