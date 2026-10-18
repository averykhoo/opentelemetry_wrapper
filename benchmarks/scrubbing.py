"""
cost of scrubbing (OTW-8), in µs per call, per engine (stdlib re always; hyperscan when it is installed)

    python benchmarks/scrubbing.py            # a table, from the repo root
    python benchmarks/scrubbing.py --json     # one json object, for comparing runs

scrubbing runs on the exporter thread, so the caller-side overhead table (benchmarks/overhead.py) cannot see it;
"span export" here is the extra exporter-thread cost of `ScrubbingSpanExporter` over handing the same span straight
to a discarding exporter (10 attributes, clean or with one secret). the other rows call the scrubber directly with
the shapes of the DEC-16 benchmark: 10 attributes, a 2 KB body with no trigger word, one containing "password", one
with a secret, and an argv. on Windows the ratios matter, not the absolute numbers
"""
import argparse
import json
import sys
import timeit
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from opentelemetry.sdk.trace import ReadableSpan  # noqa: E402
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult  # noqa: E402

from opentelemetry_wrapper.v1.scrubbing import Scrubber, ScrubbingSpanExporter  # noqa: E402

ATTRS = {'http.method': 'GET', 'http.route': '/users/{id}', 'http.status_code': 200, 'user.id': 'u-123',
         'http.url': 'https://api.example.com/users/123?page=2', 'net.peer.name': 'api.example.com',
         'code.function': 'get_user', 'code.namespace': 'app.views', 'db.system': 'postgresql',
         'db.statement': 'SELECT * FROM users WHERE id = %s'}
SECRET_ATTRS = {**ATTRS, 'db.statement': "CREATE USER bob WITH PASSWORD 'hunter2'"}
FILLER = 'the quick brown fox jumps over the lazy dog while the service handles a request; '
BORING = (FILLER * 30)[:2048]
PASSWORD = (FILLER * 15 + 'Password reset email sent. ' + FILLER * 15)[:2048]
SECRET = (FILLER * 15 + 'connecting to postgresql://app:hunter2@db:5432/app ' + FILLER * 15)[:2048]
ARGV = ['python', '-m', 'app', '--host', '0.0.0.0', '--port', '8080', '--db-url', 'postgresql://u:pw@db/x',
        '--token', 'abc', '--verbose']


class _Discard(SpanExporter):
    def export(self, spans):
        return SpanExportResult.SUCCESS


def _us(fn, number):
    return min(timeit.repeat(fn, number=number, repeat=3)) / number * 1e6


def bench(engine: str, number: int) -> dict:
    s = Scrubber(engine=engine)
    discard, wrapped = _Discard(), ScrubbingSpanExporter(_Discard(), s)
    clean, secret = [ReadableSpan('s', attributes=ATTRS)], [ReadableSpan('s', attributes=SECRET_ATTRS)]
    base = _us(lambda: discard.export(clean), number)
    return {
        'span export, clean': _us(lambda: wrapped.export(clean), number) - base,
        'span export, 1 secret': _us(lambda: wrapped.export(secret), number) - base,
        'attrs clean': _us(lambda: s.scrub_attributes(ATTRS), number),
        '2KB boring': _us(lambda: s.scrub_text(BORING), number),
        '2KB "password"': _us(lambda: s.scrub_text(PASSWORD), number),
        '2KB 1 secret': _us(lambda: s.scrub_text(SECRET), number),
        'argv': _us(lambda: s.scrub_argv(ARGV), number),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--number', type=int, default=2000)
    args = parser.parse_args()
    engines = ['re']
    try:
        import hyperscan  # noqa: F401
        engines.append('hyperscan')
    except ImportError:
        pass
    results = {e: bench(e, args.number) for e in engines}
    if args.json:
        print(json.dumps(results))
        return
    rows = list(next(iter(results.values())))
    print('| µs per call | ' + ' | '.join(engines) + ' |')
    print('|---|' + '--:|' * len(engines))
    for row in rows:
        print(f'| {row} | ' + ' | '.join(f'{results[e][row]:.1f}' for e in engines) + ' |')


if __name__ == '__main__':
    main()
