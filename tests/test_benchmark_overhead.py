"""
the per-call overhead benchmark (`benchmarks/overhead.py`) still runs; its numbers are read by hand, not checked here
"""
import json

from tests.v0._harness import REPO_ROOT
from tests.v0._harness import scenario

SMOKE = scenario(__name__, 'benchmark_overhead_smoke', script=REPO_ROOT / 'benchmarks' / 'overhead.py',
                 args=['--calls', '20', '--repeat', '1', '--json'])


def test_the_benchmark_runs_and_reports_every_row():
    result = SMOKE.result()
    assert result.returncode == 0, result.describe()
    report = json.loads(result.stdout.strip().splitlines()[-1])
    assert set(report) == {'calls', 'repeat', 'ns_per_call'}
    for exporter in ('none', 'batch'):
        rows = report['ns_per_call'][exporter]
        assert rows['bare'] > 0 and rows['otel_direct'] > 0
        assert rows['decorated'] > 0
