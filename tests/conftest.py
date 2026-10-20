"""
shared fixtures for the whole suite

`tests/v0` is the characterization suite: written against v0's behaviour so that the v1 rewrite (epic OTW-1) could be
checked against it, it now runs against v1 (through `tests/impl.py`) and pins what v1 keeps of v0. its tests that
claim a criterion pin a v0 bug that v1 fixes; v0's details that v1 changed were dropped with v0 (1.0.0)
`tests/v1` holds v1's own tests, `tests/upstream` the canaries for upstream behaviour v1 relies on
references: `DEC-n` / `OTW-n` are decision and task records (`docs/decisions/`, `tasks/`); "the v0 bug list" is
the pre-adoption HANDOFF.md's TODO section, kept verbatim in `docs/evidence/history-to-2026-10-18.md`
"""
import os
import sys
from pathlib import Path

# the package reads its configuration from env vars when it configures, so sanitise them before anything does: no
# OTLP exporter (nothing must try to reach a collector), no prometheus port (nothing must bind :9464), not disabled
for _k in list(os.environ):
    if _k.upper().startswith('OTEL_'):
        del os.environ[_k]

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest  # noqa: E402

from tests import impl  # noqa: E402
from tests.v0 import _harness  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line('markers', 'upstream: a canary for upstream behaviour we rely on (tests/upstream, set '
                                       'automatically); `pytest -m upstream` runs just those')
    config.addinivalue_line('markers', 'criterion(id): the AC-n criterion in docs/criteria.md that this test claims')


_UPSTREAM_DIR = Path(__file__).resolve().parent / 'upstream'


def pytest_collection_modifyitems(config, items):
    for item in items:
        if _UPSTREAM_DIR in Path(item.fspath).resolve().parents:
            item.add_marker(pytest.mark.upstream)


def pytest_collection_finish(session):
    # start every scenario (subprocess) needed by the selected tests, all in parallel
    if session.config.option.collectonly:
        return
    _harness.start_scenarios({item.module.__name__ for item in session.items if getattr(item, 'module', None)})


def pytest_sessionfinish(session, exitstatus):
    _harness.shutdown()


@pytest.fixture(scope='session')
def otw():
    """the package's api under v0's names, through the adapter (`tests/impl.py`)"""
    return impl


@pytest.fixture(scope='session')
def _in_memory_exporter():
    return impl.span_exporter()  # v1's test sink (OTW-3)


class SpanCapture:
    def __init__(self, exporter):
        self._exporter = exporter

    def clear(self):
        self._exporter.clear()

    def records(self, *, include_library_spans=False):
        """finished spans (oldest first) as dicts, see `tests/v0/_child.py:span_record`; clears the buffer"""
        from tests.v0._child import take
        return take(self._exporter, include_library_spans=include_library_spans)

    def names(self, **kwargs):
        return [s['name'] for s in self.records(**kwargs)]


@pytest.fixture
def spans(_in_memory_exporter):
    """
    in-process span capture; only safe for things that don't patch globals (function decoration, FastAPI apps,
    requests). class instrumentation is NOT safe in-process (see test_v0_classes.py)
    """
    _in_memory_exporter.clear()
    yield SpanCapture(_in_memory_exporter)
    _in_memory_exporter.clear()
