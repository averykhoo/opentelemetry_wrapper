"""
the README is the v1 user guide (OTW-16): AC-28, every Python example in `README.md` runs as written, with
`from opentelemetry_wrapper import otel` as its only setup, and exporting over OTLP needs nothing but the endpoint;
AC-29, the defaults: no configuration means JSON logs on stderr and no export, and every variable and `configure`
option the wrapper reads has its default in the README's tables

each example runs in its own interpreter, from an empty directory, with no `OTEL_*` variable set (`clean_env`), under a
runner that records warnings: an example passes when it exits 0 with no `OtelWrapperWarning` and no runtime warning or
internal error from the wrapper on stderr. an example that defines `test_*` functions runs under pytest instead, with
the package's plugin
"""
import atexit
import http.server
import importlib.metadata
import inspect
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import pytest

from tests.v0._harness import REPO_ROOT
from tests.v0._harness import clean_env
from tests.v0._harness import scenario

README = REPO_ROOT / 'README.md'
TEXT = README.read_text(encoding='utf-8')
SIGNALS = ('TRACES', 'METRICS', 'LOGS')
WARNING_MARKER = '@@WARNING@@ '

RUNNER = f'''\
import runpy
import sys
import warnings

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    runpy.run_path(sys.argv[1], run_name='__main__')
for w in caught:
    print({WARNING_MARKER!r} + f'{{w.category.__module__}}.{{w.category.__qualname__}}: {{w.message}}')
'''


def python_examples(text=TEXT):
    """(line number, source) of every ```python block"""
    return [(text[:m.start()].count('\n') + 2, m.group(1))
            for m in re.finditer(r'^```python\n(.*?)^```', text, re.M | re.S)]


EXAMPLES = python_examples()
_WORK = Path(tempfile.mkdtemp(prefix='otel_wrapper_readme_'))
atexit.register(shutil.rmtree, _WORK, ignore_errors=True)
(_WORK / 'runner.py').write_text(RUNNER, encoding='utf-8')


def _pytest_plugin_args():
    """the plugin loads through its `pytest11` entry point when the package is installed; from a checkout, by name"""
    installed = any(ep.name == 'opentelemetry_wrapper' for ep in importlib.metadata.entry_points(group='pytest11'))
    return [] if installed else ['-p', 'opentelemetry_wrapper.v1.pytest_plugin']


def _example_scenario(line, code):
    path = _WORK / f'readme_example_{line}.py'
    path.write_text(code, encoding='utf-8')
    if 'def test_' in code:
        return _PytestExample(path)
    return scenario(__name__, f'readme_example_{line}', script=_WORK / 'runner.py', args=[str(path)], cwd=_WORK)


class _PytestExample:
    """an example that is a test module: run by pytest when its result is asked for"""

    def __init__(self, path):
        self.path = path

    def result(self):
        proc = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', *_pytest_plugin_args(),
                               str(self.path)], cwd=str(_WORK), env=clean_env(), capture_output=True, timeout=120,
                              encoding='utf-8', errors='replace')
        return proc


SCENARIOS = {line: _example_scenario(line, code) for line, code in EXAMPLES}


def _wrapper_stderr_records(stderr):
    """the wrapper's runtime warnings and swallowed internal errors: JSON lines with an `opentelemetry_wrapper` key"""
    records = []
    for line in stderr.splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict) and 'opentelemetry_wrapper' in record:
            records.append(record)
    return records


def test_the_readme_has_python_examples():
    assert len(EXAMPLES) >= 10, EXAMPLES


@pytest.mark.criterion('AC-28')
@pytest.mark.parametrize('line', [line for line, _ in EXAMPLES], ids=[f'line{line}' for line, _ in EXAMPLES])
def test_every_python_example_in_the_readme_runs_as_written(line):  # AC-28
    result = SCENARIOS[line].result()
    output = (f'exit code {result.returncode}\n--- stdout ---\n{result.stdout[-3000:]}\n'
              f'--- stderr ---\n{result.stderr[-3000:]}')
    assert result.returncode == 0, output
    ours = [w for w in result.stdout.splitlines()
            if w.startswith(WARNING_MARKER) and 'opentelemetry_wrapper' in w.split(':', 1)[0]]
    assert ours == [], output
    assert _wrapper_stderr_records(result.stderr) == [], output
    if isinstance(SCENARIOS[line], _PytestExample):
        assert ' passed' in result.stdout and 'failed' not in result.stdout, output


_IMPORT = re.compile(r'^\s*(?:from\s+([\w.]+)\s+import\s+([\w., ()]+)|import\s+([\w., ]+))', re.M)


@pytest.mark.criterion('AC-28')
def test_readme_examples_set_up_only_with_the_otel_import_and_use_no_sdk_or_private_module():  # AC-28
    problems = []
    for line, code in EXAMPLES:
        for m in _IMPORT.finditer(code):
            module, names, plain = m.groups()
            modules = [module] if module else [part.strip().split(' ')[0] for part in plain.split(',')]
            imported = [n.strip(' ()').split(' ')[0] for n in names.split(',')] if names else []
            for mod in modules:
                if mod == 'opentelemetry.sdk' or mod.startswith('opentelemetry.sdk.'):
                    problems.append(f'line {line}: imports the SDK ({m.group(0).strip()})')
                if any(part.startswith('_') for part in mod.split('.')):
                    problems.append(f'line {line}: imports a private module ({m.group(0).strip()})')
                if mod.split('.')[0] == 'opentelemetry_wrapper' and (mod != 'opentelemetry_wrapper'
                                                                     or imported != ['otel']):
                    problems.append(f'line {line}: wrapper setup beyond `from opentelemetry_wrapper import otel`')
            if any(name.startswith('_') for name in imported):
                problems.append(f'line {line}: imports a private name ({m.group(0).strip()})')
        if 'from opentelemetry_wrapper import otel' not in code:
            problems.append(f'line {line}: no `from opentelemetry_wrapper import otel`')
    assert problems == []


class _Collector(http.server.BaseHTTPRequestHandler):
    """an OTLP/HTTP endpoint that records the paths it was sent to"""
    paths: list = []

    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length') or 0))
        type(self).paths.append(self.path)
        self.send_response(200)
        self.send_header('Content-Type', 'application/x-protobuf')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def log_message(self, *args):
        pass


def _serve(port=0):
    handler = type('Collector', (_Collector,), {'paths': []})
    server = http.server.ThreadingHTTPServer(('127.0.0.1', port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, handler


def _run_example(code, env):
    path = _WORK / f'run_{abs(hash(code))}_{threading.get_ident()}.py'
    path.write_text(code, encoding='utf-8')
    return subprocess.run([sys.executable, str(_WORK / 'runner.py'), str(path)], cwd=str(_WORK),
                          env=clean_env({'NO_PROXY': '127.0.0.1,localhost', 'no_proxy': '127.0.0.1,localhost',
                                         **env}),
                          capture_output=True, timeout=120, encoding='utf-8', errors='replace')


def _quick_start():
    at = TEXT.index('## Quick start')
    return python_examples(TEXT[at:])[0][1]


@pytest.mark.criterion('AC-28')
def test_the_quick_start_exports_traces_logs_and_metrics_given_only_the_otlp_endpoint():  # AC-28
    server, collector = _serve()
    try:
        proc = _run_example(_quick_start(), {'OTEL_EXPORTER_OTLP_ENDPOINT': f'http://127.0.0.1:{server.server_port}'})
    finally:
        server.shutdown()
        server.server_close()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert {'/v1/traces', '/v1/logs', '/v1/metrics'} <= set(collector.paths), (collector.paths, proc.stderr)


NO_CONFIGURATION_APP = '''\
import json
import logging

from opentelemetry_wrapper import otel

otel.instrument(logging)


@otel
def checkout():
    logging.warning('checked out', extra={'items': 2})


checkout()
config = otel.config
print(json.dumps({k: config[k] for k in ('traces_exporter', 'logs_exporter', 'metrics_exporter', 'prometheus_port',
                                         'otlp_endpoint')}))
'''


@pytest.mark.criterion('AC-29')
def test_with_no_configuration_an_app_runs_writes_json_logs_to_stderr_and_exports_nothing():  # AC-29
    try:  # where an OTLP exporter would send by default; if the port is taken, the config view has to do
        server, collector = _serve(4318)
    except OSError:
        server, collector = None, None
    try:
        proc = _run_example(NO_CONFIGURATION_APP, {})
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    stdout = [line for line in proc.stdout.splitlines() if line.strip()]
    assert stdout == ['{"traces_exporter": [], "logs_exporter": [], "metrics_exporter": [], "prometheus_port": null, '
                      '"otlp_endpoint": null}'], proc.stdout  # nothing else: no console exporter either
    lines = [line for line in proc.stderr.splitlines() if line.strip()]
    records = [json.loads(line) for line in lines]  # every line is one JSON object
    assert [r['message'] for r in records] == ['checked out'], lines
    assert records[0]['items'] == 2
    if collector is not None:
        assert collector.paths == []


# ----------------------------------------------------------------------------------------------------------------------
# AC-29: the README's tables against what the wrapper reads
# ----------------------------------------------------------------------------------------------------------------------

def _expand(name):
    """`OTEL_EXPORTER_OTLP_{TRACES,LOGS,METRICS}_ENDPOINT` -> its three names; `{signal.upper()}` -> one per signal"""
    m = re.search(r'\{([^{}]*)\}', name)
    if m is None:
        return [name]
    options = m.group(1).split(',') if ',' in m.group(1) else list(SIGNALS)
    return [expanded for option in options for expanded in _expand(name[:m.start()] + option + name[m.end():])]


def _tables(text=TEXT):
    """every markdown table as (header cells, rows of cells)"""
    tables, current = [], None
    for line in text.splitlines():
        if line.startswith('|'):
            cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
            if current is None:
                current = (cells, [])
                tables.append(current)
            elif not set(''.join(cells)) <= set('-: '):
                current[1].append(cells)
        else:
            current = None
    return tables


def _names(cell):
    return [n for token in re.findall(r'`([^`]*)`', cell) for n in _expand(token.split('=')[0])
            if re.fullmatch(r'OTEL_[A-Z0-9_]+\*?', n)]


def _documented_variables():
    """variable -> its default cell (None for v0's renamed variables, which have no default of their own)"""
    documented = {}
    for header, rows in _tables():
        if header[0] == 'Variable' and header[-1] == 'Default':
            for row in rows:
                for name in _names(row[0]):
                    documented[name] = row[-1]
        elif header[:2] == ['v0', 'v1']:
            for row in rows:
                for name in _names(row[0]):
                    documented.setdefault(name, None)
    return documented


def _variables_read():
    """every `OTEL_*` variable named in v1's source, with f-string families expanded per signal"""
    names = set()
    for path in (REPO_ROOT / 'opentelemetry_wrapper' / 'v1').glob('*.py'):
        source = path.read_text(encoding='utf-8')
        names.update(re.findall(r'\bOTEL_[A-Z0-9_]*[A-Z0-9]\b(?!\{)', source))
        for family in re.findall(r'\bOTEL_[A-Z0-9_]*\{[^{}]*\}[A-Z0-9_]*[A-Z0-9]', source):
            names.update(_expand(family))
    return names


def _is_documented(name, documented):
    return name in documented or any(d.endswith('*') and name.startswith(d[:-1]) for d in documented)


@pytest.mark.criterion('AC-29')
def test_every_variable_the_wrapper_reads_is_in_the_readme_tables_with_its_default():  # AC-29
    documented = _documented_variables()
    read = _variables_read()
    assert len(read) > 20, read
    assert sorted(n for n in read if not _is_documented(n, documented)) == []
    assert sorted(n for n, default in documented.items() if default is not None and not default.strip()) == []


def _default_pieces(value):
    """what the README's default cell must show for a `Settings` default"""
    if isinstance(value, bool):
        return [str(value).lower()]
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, tuple):
        return [piece for item in value if isinstance(item, str) for piece in _default_pieces(item)]
    return []  # None: "none"


@pytest.mark.criterion('AC-29')
def test_every_configure_option_is_in_the_readme_table_with_its_default_and_variable():  # AC-29
    from opentelemetry_wrapper import otel
    from opentelemetry_wrapper.v1 import _env
    options = [p for p in inspect.signature(otel.configure).parameters]
    table = next(rows for header, rows in _tables() if header[0] == 'Option')
    variables = _documented_variables()
    defaults = _env.Settings()
    problems = []
    for option in options:
        row = next((r for r in table if f'`{option}`' in r[0]), None)
        if row is None:
            problems.append(f'{option}: no row')
            continue
        variable_names = _names(row[1])
        if not variable_names:
            problems.append(f'{option}: names no variable')
        for piece in _default_pieces(getattr(defaults, option)):
            if piece not in row[2]:
                problems.append(f'{option}: default {piece!r} missing from {row[2]!r}')
            for name in variable_names:  # the variable's own row says the same
                if variables.get(name) is not None and piece not in variables[name]:
                    problems.append(f'{name}: default {piece!r} missing from {variables[name]!r}')
    assert problems == []
    assert sorted(set(options)) == sorted(_env.CONFIGURE_OPTIONS)  # the signature and the settings agree
