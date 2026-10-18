"""
per-call overhead of a decorated function, for the implementation `OTW_IMPL` selects (v0 or v1, DEC-38)

    python benchmarks/overhead.py                  # a table, from the repo root
    OTW_IMPL=v1 python benchmarks/overhead.py      # the same against v1
    python benchmarks/overhead.py --json           # one json object, for comparing runs

each exporter setup runs in a fresh interpreter, because the tracer provider is global. "none" is a `TracerProvider`
with no processor, so a span is created and dropped; "batch" adds a `BatchSpanProcessor` with an exporter that
discards everything (the setup behind DEC-15's per-span figures), so the caller thread pays for queueing a span but
not for exporting it. the provider is set before the package under test is imported, so v0 keeps it and adds no
console exporter. rows: the bare function, a span from the OTel tracer directly (the floor), and the function
decorated through `tests.impl.decorate`. on Windows, as in DEC-15, the ratios matter, not the absolute numbers
"""
import argparse
import json
import os
import subprocess
import sys
import timeit
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPORTERS = ('none', 'batch')


def _setup_provider(exporter: str):
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.export import SpanExporter
    from opentelemetry.sdk.trace.export import SpanExportResult

    class Discard(SpanExporter):
        def export(self, spans):
            return SpanExportResult.SUCCESS

    provider = TracerProvider()
    if exporter == 'batch':
        provider.add_span_processor(BatchSpanProcessor(Discard()))
    trace.set_tracer_provider(provider)
    return provider


def _per_call_ns(function, calls: int, repeat: int) -> float:
    return min(timeit.repeat(function, number=calls, repeat=repeat)) / calls * 1e9


def child(exporter: str, calls: int, repeat: int) -> dict:
    provider = _setup_provider(exporter)
    tracer = provider.get_tracer('benchmark')

    def bare(x=1):
        return x + 1

    def otel_direct():
        with tracer.start_as_current_span('otel_direct'):
            return bare()

    rows = {'bare': _per_call_ns(bare, calls, repeat), 'otel_direct': _per_call_ns(otel_direct, calls, repeat)}
    try:
        from tests.impl import decorate
        decorated = decorate(bare)
        decorated()  # the first call may do one-off work
    except NotImplementedError as e:
        rows['decorated'] = f'unbound: {e}'
    else:
        rows['decorated'] = _per_call_ns(decorated, calls, repeat)
    provider.shutdown()
    return rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0].strip())
    parser.add_argument('--calls', type=int, default=20_000, help='calls per timing (default %(default)s)')
    parser.add_argument('--repeat', type=int, default=5, help='timings per row, the fastest is kept')
    parser.add_argument('--json', action='store_true', help='print one json object instead of a table')
    parser.add_argument('--child', choices=EXPORTERS, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.child:
        print(json.dumps(child(args.child, args.calls, args.repeat)))
        return 0

    env = {k: v for k, v in os.environ.items() if not k.upper().startswith('OTEL_')}
    env['PYTHONPATH'] = str(REPO_ROOT)
    impl = env.get('OTW_IMPL') or 'v0'
    results = {}
    for exporter in EXPORTERS:
        out = subprocess.run([sys.executable, __file__, '--child', exporter, '--calls', str(args.calls),
                              '--repeat', str(args.repeat)],
                             env=env, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
        if out.returncode != 0:
            print(out.stderr, file=sys.stderr)
            return out.returncode
        results[exporter] = json.loads(out.stdout.strip().splitlines()[-1])

    if args.json:
        print(json.dumps({'impl': impl, 'calls': args.calls, 'repeat': args.repeat, 'ns_per_call': results}))
        return 0
    print(f'OTW_IMPL={impl}, ns per call (fastest of {args.repeat} x {args.calls} calls)')
    print(f'{"":<12}' + ''.join(f'{e:>14}' for e in EXPORTERS))
    for row in ('bare', 'otel_direct', 'decorated'):
        cells = [results[e][row] for e in EXPORTERS]
        print(f'{row:<12}' + ''.join(f'{c:>14.0f}' if isinstance(c, float) else f'{"unbound":>14}' for c in cells))
    return 0


if __name__ == '__main__':
    sys.exit(main())
