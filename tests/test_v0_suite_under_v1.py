"""
AC-8, DEC-38's "proven safe is one command": the plain `tests/v0` tests pass under `OTW_IMPL=v1`

the gate and CI run the suite under the default, `OTW_IMPL=v0`, so this runs `pytest tests/v0` once more, under v1,
in a child interpreter, started at collection with the other scenarios so it overlaps them. under `OTW_IMPL=v1` the
outer run already holds those tests, so it is skipped (and not started)
"""
import re

import pytest

from tests import impl
from tests.v0._harness import scenario

V0_SUITE_UNDER_V1 = None
if impl.IMPL == 'v0':
    V0_SUITE_UNDER_V1 = scenario(__name__, 'v0_suite_under_v1', r'''
import sys
import pytest
sys.exit(pytest.main(['-q', '-p', 'no:cacheprovider', '-rfEs', 'tests/v0']))
''', env={'OTW_IMPL': 'v1'})


def _counts(summary: str) -> dict:
    return {word: int(n) for n, word in re.findall(r'(\d+) (passed|failed|errors?|skipped|xfailed|xpassed)', summary)}


@pytest.mark.criterion('AC-8')
@pytest.mark.skipif(impl.IMPL != 'v0', reason='under OTW_IMPL=v1 this run holds tests/v0 itself')
def test_plain_v0_tests_pass_under_v1():
    result = V0_SUITE_UNDER_V1.result()
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    summary = lines[-1] if lines else ''
    assert result.returncode == 0, result.describe()  # a failure, an error or a strict xfail that passed
    counts = _counts(summary)
    assert counts.get('passed', 0) > 0, result.describe()
    assert not {'failed', 'error', 'errors', 'xpassed'} & set(counts), result.describe()
    # it really ran v1: the v0_specific tests were skipped as v0-only (tests/conftest.py)
    assert 'v0_specific: pins a v0 detail, and OTW_IMPL=v1' in result.stdout, result.describe()
