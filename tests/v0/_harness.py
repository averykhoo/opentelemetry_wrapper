"""
test-side helpers

v0 sets global OpenTelemetry providers, patches `logging` / `dataclasses` / sqlalchemy globally, and reads its config
from env vars at import time, none of which can be reset cleanly. anything that depends on that global state runs as
a *scenario*: a small script executed in a fresh interpreter (the same conda python that runs pytest), which reports
back via `_child.emit(key, value)`

scenarios are registered at import (collection) time and all started in parallel when collection finishes (see
`tests/conftest.py`), so the suite pays for interpreter start-up roughly once instead of once per scenario
"""
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
from concurrent.futures import Future
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Dict
from typing import List
from typing import Optional
from typing import Sequence
from typing import Union

from tests.impl import IMPL
from tests.v0._child import RESULT_MARKER

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable  # the conda env's interpreter, since that's what runs pytest

SCENARIO_TIMEOUT_SECONDS = 120  # the default budget, for one small script; a scenario can set its own

_PRELUDE = 'from tests.v0._child import *  # noqa\n'


def clean_env(overrides: Optional[Dict[str, Optional[str]]] = None) -> Dict[str, str]:
    """
    environment for a child interpreter: no OTEL_* / LOGFIRE_* config leaking in from the developer's shell
    (so no OTLP exporter, no prometheus port), repo root importable, utf-8 stdio, the same `OTW_IMPL`
    an override of `None` removes the variable
    """
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(('OTEL_', 'LOGFIRE_'))}
    env['PYTHONPATH'] = str(REPO_ROOT)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    env['OTW_IMPL'] = IMPL  # the child tests the same implementation as pytest
    for k, v in (overrides or {}).items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = v
    return env


@dataclass
class Result:
    args: List[str]
    returncode: int
    stdout: str
    stderr: str
    values: Dict[str, object] = field(default_factory=dict)

    def __getitem__(self, key: str):
        assert self.returncode == 0, self.describe()
        assert key in self.values, f'scenario never emitted {key!r}\n{self.describe()}'
        return self.values[key]

    def describe(self) -> str:
        return (f'command: {self.args}\nexit code: {self.returncode}\n'
                f'--- stderr (last 4000 chars) ---\n{self.stderr[-4000:]}\n'
                f'--- stdout (last 2000 chars) ---\n{self.stdout[-2000:]}')

    @property
    def stderr_lines(self) -> List[str]:
        return [line for line in self.stderr.splitlines() if line.strip()]

    def stdout_json_objects(self) -> List[dict]:
        """one-line json objects printed on stdout (v0's console span exporter writes one span per line)"""
        out = []
        for line in self.stdout.splitlines():
            if line.startswith('{'):
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return out


def _text(output: Union[str, bytes, None]) -> str:
    # `TimeoutExpired` carries what was read so far, as bytes on POSIX even when the run was in text mode
    if isinstance(output, bytes):
        return output.decode('utf-8', errors='replace')
    return output or ''


def _run(args: List[str], env: Dict[str, str], cwd: Path, timeout: float = SCENARIO_TIMEOUT_SECONDS) -> Result:
    try:
        proc = subprocess.run(args, env=env, cwd=str(cwd), capture_output=True, timeout=timeout,
                              encoding='utf-8', errors='replace')
    except subprocess.TimeoutExpired as e:
        return Result(args, -1, _text(e.stdout), f'TIMEOUT after {timeout}s\n{_text(e.stderr)}')
    return Result(args, proc.returncode, proc.stdout, proc.stderr, parse_results(proc.stdout))


def parse_results(stdout: str) -> Dict[str, object]:
    """
    the values a child emitted. each is one json object after the marker; whatever another thread of the child wrote
    on the same line (a console span exporter, say) is ignored
    """
    values: Dict[str, object] = {}
    decoder = json.JSONDecoder()
    for line in stdout.splitlines():
        at = line.find(RESULT_MARKER)
        if at >= 0:
            item, _ = decoder.raw_decode(line, at + len(RESULT_MARKER))
            values[item['key']] = item['value']
    return values


# ----------------------------------------------------------------------------------------------------------------------
# scenario registry
# ----------------------------------------------------------------------------------------------------------------------

_TMP_DIR: Optional[Path] = None
_TMP_LOCK = threading.Lock()
_EXECUTOR: Optional[ThreadPoolExecutor] = None
_REGISTRY: Dict[str, 'Scenario'] = dict()


def _tmp_dir() -> Path:
    global _TMP_DIR
    with _TMP_LOCK:
        if _TMP_DIR is None:
            _TMP_DIR = Path(tempfile.mkdtemp(prefix='otel_wrapper_v0_tests_'))
        return _TMP_DIR


def scenario_workers() -> int:
    """
    how many scenarios run at once: one per core, 2 to 8, unless `OTW_SCENARIO_WORKERS` says otherwise (a nested
    suite sets it, so the two runs together start fewer interpreters than two full pools)
    """
    configured = os.environ.get('OTW_SCENARIO_WORKERS', '').strip()
    if configured:
        return max(1, int(configured))
    return max(2, min(8, os.cpu_count() or 2))


def _executor() -> ThreadPoolExecutor:
    global _EXECUTOR
    if _EXECUTOR is None:
        _EXECUTOR = ThreadPoolExecutor(max_workers=scenario_workers())
    return _EXECUTOR


@dataclass(eq=False)
class Scenario:
    module: str
    name: str
    code: Optional[str] = None  # python source, run as `__main__` with the `_child` helpers star-imported
    script: Optional[Path] = None  # or an existing script, run as-is
    args: Sequence[str] = ()
    env: Optional[Dict[str, Optional[str]]] = None
    cwd: Path = REPO_ROOT
    timeout: float = SCENARIO_TIMEOUT_SECONDS
    _future: Optional[Future] = None

    def _command(self) -> List[str]:
        if self.script is not None:
            return [PYTHON, str(self.script), *self.args]
        path = _tmp_dir() / f'scenario_{self.name}.py'
        path.write_text(_PRELUDE + textwrap.dedent(self.code or ''), encoding='utf-8')
        return [PYTHON, str(path), *self.args]

    def start(self) -> None:
        if self._future is None:
            # the command and the environment are built here, in the calling (pytest's) thread, never in a worker:
            # pytest sets and deletes PYTEST_CURRENT_TEST in os.environ around every test, and a worker iterating
            # os.environ at that moment raises KeyError
            command, env = self._command(), clean_env(self.env)
            self._future = _executor().submit(_run, command, env, self.cwd, self.timeout)

    def result(self) -> Result:
        self.start()
        assert self._future is not None
        return self._future.result()


def scenario(module: str,
             name: str,
             code: Optional[str] = None,
             *,
             script: Union[Path, str, None] = None,
             args: Sequence[str] = (),
             env: Optional[Dict[str, Optional[str]]] = None,
             cwd: Path = REPO_ROOT,
             timeout: float = SCENARIO_TIMEOUT_SECONDS,
             ) -> Scenario:
    """register a scenario (call at module import time, so it can be started early)"""
    assert (code is None) != (script is None)
    assert name not in _REGISTRY, f'duplicate scenario name {name!r}'
    _REGISTRY[name] = Scenario(module, name, code, Path(script) if script else None, tuple(args), env, cwd, timeout)
    return _REGISTRY[name]


def start_scenarios(modules) -> None:
    """start every registered scenario belonging to one of the given test modules"""
    for s in _REGISTRY.values():
        if s.module in modules:
            s.start()


def shutdown() -> None:
    if _EXECUTOR is not None:
        _EXECUTOR.shutdown(wait=True, cancel_futures=True)
    if _TMP_DIR is not None:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)


def run_python(code: str, env: Optional[Dict[str, Optional[str]]] = None, args: Sequence[str] = ()) -> Result:
    """run a one-off script synchronously (prefer `scenario` so it runs in parallel)"""
    path = _tmp_dir() / f'oneoff_{abs(hash(code))}_{threading.get_ident()}.py'
    path.write_text(_PRELUDE + textwrap.dedent(code), encoding='utf-8')
    return _run([PYTHON, str(path), *args], clean_env(env), REPO_ROOT)


# ----------------------------------------------------------------------------------------------------------------------
# driving an ASGI app without httpx / TestClient (httpx is not installed)
# ----------------------------------------------------------------------------------------------------------------------

@dataclass
class AsgiResponse:
    status: int
    headers: Dict[str, str]
    body: bytes

    @property
    def text(self) -> str:
        return self.body.decode('utf-8', errors='replace')


async def asgi_request_async(app, path: str, *, method: str = 'GET', headers=(), query_string: bytes = b''):
    scope = {
        'type':         'http',
        'asgi':         {'version': '3.0'},
        'http_version': '1.1',
        'method':       method,
        'scheme':       'http',
        'path':         path,
        'raw_path':     path.encode(),
        'query_string': query_string,
        'root_path':    '',
        # ASGI servers lowercase header names
        'headers':      [(b'host', b'testserver'),
                         *((k.lower().encode('latin-1'), v.encode('latin-1')) for k, v in headers)],
        'client':       ('1.2.3.4', 1234),
        'server':       ('testserver', 80),
    }
    sent = []

    async def receive():
        return {'type': 'http.request', 'body': b'', 'more_body': False}

    async def send(message):
        sent.append(message)

    await app(scope, receive, send)
    start = [m for m in sent if m['type'] == 'http.response.start'][0]
    return AsgiResponse(status=start['status'],
                        headers={k.decode('latin-1').lower(): v.decode('latin-1') for k, v in start['headers']},
                        body=b''.join(m.get('body', b'') for m in sent if m['type'] == 'http.response.body'))


def asgi_request(app, path: str, **kwargs) -> AsgiResponse:
    return asyncio.run(asgi_request_async(app, path, **kwargs))


# the same helper, as source code for scenario scripts
ASGI_HELPER_SOURCE = 'from tests.v0._harness import asgi_request  # noqa\n'
