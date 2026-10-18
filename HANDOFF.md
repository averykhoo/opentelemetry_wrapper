# Handoff

Working notes for picking this repo back up. Last updated 2026-10-18.

## State

- **Committed 2026-10-08 on branch `v1-plan`** (not pushed, not merged into `main`), as three commits: the v0 fixes
  below, the `tests/` suite, and the docs. The 2026-10-17/18 doc updates (logfire dropped, questions answered) are
  not committed yet.
- **Docs:** `PLAN.md` (v1 design, reviewed 2026-10-07/08, updated with the author's answers and, 2026-10-17/18, the
  move to the plain OTel SDK), `README_v1.md` (draft v1 API, matching what's decided), `CLAUDE.md` (conda env,
  scratch space, CI-watching rule). `.gitignore` ignores `.scratch/`, local scratch space holding the evidence
  scripts, the Q15 spike, the scrubbing prototype, the ergonomics review and the v0 deck transcript (nothing tracked
  refers to it).
- **v1 status:** design only, no v1 code. **Logfire is dropped** (Q15, 2026-10-17): v1 builds on the plain OTel SDK +
  contrib instrumentors; `PLAN.md` "Why not logfire" has the evidence. Decided: everything under "Decided", proposals
  3-8, 10, 11, and Q1-Q5, Q9-Q11, Q13. Still open in `PLAN.md` "Questions for later":
  - Q8, Q12 and Q16 were decided 2026-10-18 (accept `PYTHONWARNINGS=error` crashes; no Kubernetes API calls, Downward
    API volume instead; stdlib `re` by default + an optional `[hyperscan]` extra; possessive quantifiers measured
    and rejected).
  - **Upstream bumps** (decided 2026-10-18): Renovate PRs that raise the OTel caps and auto-merge when CI passes, then
    an automatic patch release to PyPI for dependency-only merges (`PLAN.md` workstream 0). Renovate's config for
    OTel's pre-release-numbered contrib packages is unverified.
- **Decisions from the review that aren't obvious from the docs alone:** hosting stays on GitHub (the v0 deck's move
  to GitLab + Artifactory is off); `type_checking.py` stays in the repo, working, but v1 doesn't import or export it;
  logs are real OTel log records (logs-as-spans was never the intent); OTel stays strictly pinned, as in v0, because
  OTel has shipped breaking changes without warning (twice during v0).
- **Next steps:** workstream 0 in `PLAN.md`: the `OTW_IMPL=v0|v1` adapter in the test harness, canary tests in
  `tests/upstream/`, a GitHub Actions workflow, Renovate + the auto-release workflow; then workstream 1.
- **v0 fixes** (committed 2026-10-08, first commit):
  - `engine_typedef.py`: sync/async engine detection imported separately, so a missing asyncio extension
    (e.g. sqlalchemy 2.1 without greenlet) no longer breaks `import opentelemetry_wrapper`
  - `instrument_logging.py`: passes `inject_trace_context=True, enable_log_auto_instrumentation=False` to
    `LoggingInstrumentor` (newer versions stopped injecting `otelTraceID`/`otelSpanID` by default, and add a
    duplicate otel log handler); record factory defaults missing ids to zero instead of crashing
  - `instrument_sqlalchemy.py`: warns once at startup (and skips instrumenting) if the installed sqlalchemy is
    outside the range supported by `opentelemetry-instrumentation-sqlalchemy`, which otherwise silently does nothing
  - `experiment_otel_logging.py`: imports `typecheck` from `opentelemetry_wrapper.v0.utils.type_checking`
    (it is deliberately not exported from the package)
  - `requirements.txt` / `pyproject.toml`: `sqlalchemy` -> `sqlalchemy[asyncio]<2.1` (temporary pin, see below)
- **Conda env** `opentelemetry_wrapper` was rebuilt on **Python 3.12.15** (was 3.8.19) with `requirements.txt`, plus
  `logfire`, `pytest`, `flake8`, `mypy`, `types-requests` (the extras are not in `requirements.txt`). Added
  2026-10-18 for the scrubbing-engine benchmark only: `greenery` 4.2.2, `interegular` 0.3.3, `regex` 2026.9.29,
  `google-re2` 1.1.20251105, `hyperscan` 0.9.1. `logfire` is no longer needed by the design (it was kept for the Q15 comparison).
  Notable versions: opentelemetry 1.44.0 / 0.65b0, sqlalchemy 2.0.54, fastapi 0.142.2, pydantic 2.13.5.

## How to verify

**Test suite (added 2026-10-07, committed 2026-10-08):** `python -m pytest -q tests/v0` -> `203 passed, 23 xfailed` (~22 s).
It characterizes v0 so v1 can be checked against it. Plain tests pin behaviour v1 should keep. Known bugs are
`xfail(strict=True)` tests asserting the *correct* behaviour, so they error once fixed. `@pytest.mark.v0_specific`
(79 tests) marks v0 details PLAN.md intends to change (name formats, deprecated `code.*` keys, env var parsing,
`user@host` service name). Global OTel state is handled by running scenarios in subprocesses (`tests/v0/_harness.py`).

The older manual checks, with the repo root on `PYTHONPATH`:

| Check | Expected |
|---|---|
| `python experiment_otel_logging.py` | exit 0 (final assert passes), every log's `otelSpanID` matches a span |
| `python setup_otel_logging.py` | exit 0, 9x `A.__new__` and 9x `A.__init__` spans, all status OK |
| `python log_weird_things.py` | exit 0, every stderr line is valid one-line JSON |
| `python sqlalchemy_example.py` | exit 0 **and** `connect` + `SELECT :memory:` spans in stdout |
| `python fastapi_main.py` | `/hello-hello` returns `"hello hello"`, `/metrics` and `:9464` return 200 |
| `python opentelemetry_wrapper/v0/utils/type_checking.py` | same output under pydantic 2 and pydantic 1 |
| `pytest --doctest-modules opentelemetry_wrapper/v0/config opentelemetry_wrapper/v0/utils/extract_json_header.py` | 4 passed |
| `flake8 --max-line-length 119 ./opentelemetry_wrapper/` | 26 findings, all pre-existing (none in changed files) |
| `mypy ./opentelemetry_wrapper/` | 19 errors, all pre-existing (one fewer than `HEAD`) |

All of the above passed on 2026-10-04.

## Watch upstream

- **Unpin sqlalchemy.** `opentelemetry-instrumentation-sqlalchemy` (<= 0.66b0) declares `sqlalchemy < 2.1.0`, so on
  2.1 it logs a `DependencyConflict` and silently produces no spans. The hooks themselves work on 2.1 (verified with
  `skip_dep_check=True`); only the declared range is stale. Track
  [issue #5118](https://github.com/open-telemetry/opentelemetry-python-contrib/issues/5118) / PR #5120. Once a
  release supports 2.1: remove `<2.1` from both dependency files, set that release as the minimum for
  `opentelemetry-instrumentation-sqlalchemy`, and check `sqlalchemy_example.py` prints a `SELECT` span.

## TODO

### Bugs (confirmed by running them)

- [ ] **Memory leak in class instrumentation.** `instrument_decorator.py:263` wraps every bound method on attribute
  access and `:110` caches it in `_CACHE_INSTRUMENTED` forever; a bound method holds its instance, so instances of
  instrumented classes are never freed (verified: instance alive after `del` + `gc.collect()`). `CodeInfo` in
  `introspect.py:138` is an unbounded `lru_cache` with the same effect.
- [ ] **Only the first sqlalchemy engine gets traced.** `SQLAlchemyInstrumentor` is a singleton, so the second
  `instrument_sqlalchemy_engine()` call (`instrument_sqlalchemy.py:88`) logs "Attempting to instrument while already
  instrumented" and does nothing (verified: no `SELECT` span for engine 2). Logfire has the same bug: only engines
  created *after* the first call are traced, via upstream's `create_engine` patch. Fix (verified): attach
  `EngineTracer(tracer, engine, connections_usage)` per engine, tracked in a `WeakSet`. Evidence and details in
  `PLAN.md` ("SQLAlchemy").
- [ ] **Update `CodeInfo` (`introspect.py`).** Two bugs:
  - **Callable instances are not resolved**: `CodeInfo(obj).name` is `<module>.<unknown function>` with no path or
    line, because it never falls back to `type(obj).__call__` (logfire does).
  - **Name and line can come from different functions**: for a decorator that sets `__wrapped__` without
    `@functools.wraps`, `CodeInfo` deliberately doesn't unwrap it (so the name is the wrapper's, e.g.
    `renaming.<locals>.other`), but `inspect.getsourcelines` / `getsourcefile` call `inspect.unwrap` internally, so
    `lineno` / `path` are the wrapped function's. Read `co_firstlineno` / `co_filename` from the same object the
    name came from.

  While there: on 3.11+ derive the name from `co_qualname` + module (which is what `code.function.name` wants) and
  drop the `cls` heuristics, especially the branch that imports the source file; emit the stable
  `code.function.name` / `code.file.path` / `code.line.number` instead of the deprecated `SpanAttributes` keys.
- [ ] **Wrong timezone offset for negative offsets.** `logging_json_formatter.py:99` uses `timedelta.seconds`, so
  UTC-5 logs `68400` instead of `-18000`; use `total_seconds()`. (The tz is also computed once at formatter init, so
  DST changes are missed.)

### Bugs found by the test suite (2026-10-07, strict xfails in `tests/v0`)

- [ ] **Only the first instrumented class gets method/property spans.** The `__getattribute__` cache is keyed by the
  original `__getattribute__`, which is `object.__getattribute__` for every ordinary class, so the second class
  instrumented in a process (every later dataclass, nested classes) gets constructor spans only.
- [ ] **Already-instrumented methods get two nested spans when reached through an instance** (a method decorated
  inside an instrumented class, explicit `x.__call__()` / `x.__enter__()`, `__post_init__` via `__init__`). This breaks
  "decorate twice -> one span".
- [ ] **base64 `x-userinfo` fails to decode for 2 of 3 lengths on Python 3.12** (and 1 of 3 on 3.11). `_extract_userinfo`
  always appends `==` and decodes strictly, which newer Pythons reject. Regressed with the 3.8 -> 3.12 env move. The
  undecoded header is recorded raw on the span instead, PII included. Fix: pad to `-len % 4`.
- [ ] **Without sqlalchemy's asyncio extension, `instrument_sqlalchemy_engine` crashes** with
  `TargetModuleNotFoundError` (import and engine detection are fine).
- Also pinned (plain tests, maybe intended): the `/metrics` span exclusion is a regex *search*, so `/api/metrics` and
  `/metricsfoo` get no spans. `instrument_decorate(42)` raises `AssertionError`. A second `instrument_all()` logs
  "already instrumented" (system metrics has no guard). Generator spans end at creation. v0 emits spans for its own
  entry points (e.g. `instrument_logging`), contrary to the "zero spans of its own" principle.

### Bugs / risks (from reading the code; reproduced by the test suite 2026-10-07 unless noted)

- [ ] **Secrets in logs.** `instrument_all()` logs `OTEL_EXPORTER_OTLP_HEADER` verbatim (`__init__.py:71`), which
  usually carries an auth token. Redact header values.
- [ ] **Prometheus port only binds to localhost** (`otel_providers.py:112`, `addr="localhost"`), so it can't be
  scraped from outside the pod. Fix: bind to the standard `OTEL_EXPORTER_PROMETHEUS_HOST` (see `PLAN.md`, "Metrics").
- [ ] **"Never crash" holes in `instrument_decorate`:** raises `TypeError` for unsupported types
  (`instrument_decorator.py:107`); unhashable callables break the cache lookup; every property access on an
  instrumented class calls `inspect.getsourcelines` (`:247`), which is slow and raises `OSError` when source is
  unavailable (e.g. frozen apps).
- [ ] **Other instrumentors can fail silently the same way sqlalchemy did** (dependency conflict -> logged error,
  no spans), e.g. `instrument_requests.py:55`. Consider the same startup warning there, ideally as a shared helper.
- [ ] `x-userinfo` (decoded user identity) is captured on every request span by default
  (`OTEL_HEADER_ATTRIBUTES`). Intended, but worth a conscious decision / README note.

### Cleanup

- [ ] Dead duplicates in `otel_providers.py:126` (`LOGGING_FORMAT_VERBOSE`) and `:135` (`_OUR_ROOT_HANDLERS`).
- [ ] `instrument_system_metrics` is imported in `__init__.py` but missing from `__all__` (`:89`).
- [ ] Wrong docstrings: `instrument_fastapi.py:18` claims it instruments logging and requests;
  `getenv_otel_service_namespace` (`otel_service_name.py:219`) describes the service name.
- [ ] `get_hostname()` returns the deployment name early in its k8s branch (`otel_service_name.py:40`).
- [ ] `requires-python = ">3.8.0"` (`pyproject.toml:12`) excludes 3.8.0; probably meant `>=`. Also decide the real
  minimum now that dev is on 3.12.
- [ ] Response headers captured by `requests` are hardcoded (`instrument_requests.py:11`).
- [ ] Pre-existing flake8 (26) and mypy (19) findings.
- [ ] `TODO.md` testing notes are stale: `sqlalchemy2-stubs` (`TODO.md:7`) targets sqlalchemy 1.4 and conflicts
  with 2.x's inline types; drop it.

### Bigger picture

- [ ] Real pytest suite + CI (also in `TODO.md` as "CICD the tests"); the example scripts above are a starting point.
- [ ] v1 rebuild: **design in `PLAN.md`**. Originally planned on the Logfire SDK; since 2026-10-17 on the plain OTel
  SDK + contrib instrumentors (`PLAN.md` "Why not logfire").

See also `TODO.md` for the existing longer-term ideas (env var renames, context-manager spans, generators,
etc.), which are not duplicated here.
