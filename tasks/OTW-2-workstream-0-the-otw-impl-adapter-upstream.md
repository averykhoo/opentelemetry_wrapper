---
type: Task
id: OTW-2
title: 'Workstream 0: the OTW_IMPL adapter, upstream canaries and CI'
brief: Adapter first (OTW_IMPL=v0|v1), then canaries in tests/upstream, then CI; Renovate and auto-release moved to OTW-21
pri: NOW
state: open
deps: []
source: session 2026-10-18a
created: 2026-10-18
moved: 2026-10-18a
updated: 2026-10-18k
aliases: [WS0]
labels: [v1, ci]
---

Criteria: AC-8 (runnable), AC-23, AC-24. Decisions: DEC-38, DEC-54, DEC-55, DEC-56, DEC-57, DEC-63.

*Workstream 0 of the v1 design, verbatim from the pre-adoption `PLAN.md` (`docs/archive/PLAN.md`); there, "workstream n" is the task aliased `WSn` (OTW-1 lists them), "Decided" / "proposal n" / "Qn" are decisions (`docs/evidence/adoption-map-2026-10-18.md`), and "`HANDOFF.md`" is the old note in `docs/evidence/history-to-2026-10-18.md`.*

v0 characterization suite: done (`tests/v0`, committed 2026-10-08). Plain tests are behaviour v1 must keep; `v0_specific`
tests (79) mark intended changes; strict xfails are v0 bugs. v1 tests come after the API is settled, reusing the same
scenarios (and the subprocess harness in `tests/v0/_harness.py`).

- Add the `OTW_IMPL=v0|v1` adapter (see "Decided", Process).
- **Canary tests** (`tests/upstream/`): one test per upstream behaviour or semi-private API we rely on, so an OTel
  upgrade fails a test instead of production: the `EngineTracer` import path and signature; the `contextmanager`
  shared-`__code__` trick; `ReadableSpan(...)` constructor kwargs and the `opentelemetry.sdk._logs` names the
  scrubbing wrappers use; the SDK's post-fork resource update (`_handle_fork`, Linux CI only); `ProxyTracer` picking up
  a later provider; resource precedence; `FastAPIInstrumentor.instrument_app` idempotency and `exclude_spans`. These
  replace the local evidence scripts.
- **Upstream bumps without anyone watching CI** (the author doesn't check CI results; decided 2026-10-18): automation
  is only worth having if it updates the repo by itself. Use **Renovate** (GitHub app) rather than a home-grown job:
  it opens a PR that raises the OTel caps, the PR's CI runs the suite and the canaries, and Renovate **auto-merges
  only if everything passes**; a failing PR just sits there and the old pins keep protecting users. OTel has shipped
  breaking changes without warning (twice during v0), which is why the pins stay strict (workstream 10). Config to
  get right (not verified yet): group all `opentelemetry-*` packages into one PR (SDK and contrib release in
  lockstep); a range strategy that moves the upper cap (`<1.45` -> `<1.46`); contrib versions like `0.66b0` are PEP
  440 pre-releases, so Renovate must not ignore them as unstable.
- **Auto-release of dependency-only bumps** (decided 2026-10-18): when such a PR merges, a release workflow bumps the
  patch version and publishes to PyPI (trusted publishing, no stored token). Only for merges that change nothing but
  dependency specifiers; anything else is released by hand. A patch release (not `.postN`) is the conventional
  signal, and both are picked up by default. If a bump should ever be opt-in, publish it as a pre-release (`rcN` /
  `.devN`), which pip skips unless asked (`--pre` or an explicit pre-release specifier); *verified* with `packaging`'s
  filtering. Local versions (`+tag`) can't be uploaded to PyPI.
- Without Renovate, the same check runs locally as `pytest -m upstream` whenever someone works on the repo.
- In-process fixtures strip `OTEL_*` (`tests/conftest.py` already does).
- Tests for the two-tasks-plus-a-thread interleaving from "Public API notes".
- A micro-benchmark of per-call overhead (v0 vs v1, with and without an exporter), so a regression is visible.
- **CI:** GitHub Actions on push and on pull requests (none yet; `.github/workflows/` doesn't exist). Kept
  (decided 2026-10-18): Renovate's auto-merge depends on it, and whoever pushes watches the run. Matrix: Python 3.12 / 3.13 / 3.14 × with and
  without the optional extras, so "optional at call time" is actually exercised. Keep the steps in a script so the
  workflow file stays thin.

**Order:** 0 -> 1 (configure, decorator, `with otel:`) -> 3 -> 7 -> 4 -> 5 -> 2 -> 8 -> 9, with 6 in parallel (pure
OTel, testable alone) and 10-11 alongside 1. Each workstream ends with a one-line **Done when**, given below.

**Done when:** the suite is committed, `OTW_IMPL=v1` runs (failures expected until v1 exists), canaries pass, CI runs
on push.

## Traps

- **Split (DEC-78):** Renovate and the auto-release (the two bullets below on upstream bumps and auto-release, DEC-54 and DEC-55, criterion AC-24) moved to OTW-21, which waits for the strict pins (OTW-13). OTW-2 is the rest, and is below the design-review threshold.
- The post-fork resource canary (`_handle_fork`) can only run on Linux CI: there is no fork on Windows.
- `asyncio.iscoroutinefunction` (v0's `instrument_decorator.py`, `type_checking.py`) is deprecated in Python 3.14, which the CI matrix runs (DEC-56): expect `DeprecationWarning`s there, and errors if warnings are errors (OTW-18).
- A CI run that collects no tests must fail (pytest exits 5): OTW-21's auto-merge will trust a green run.
- The evidence scripts this replaces exist only on the author's machine; the claims they checked are in the evidence doc below.

## Read first

- The decisions: [DEC-38](../docs/decisions/DEC-38-proven-safe-is-one-command-tests-v0-under-otw.md), [DEC-54](../docs/decisions/DEC-54-upstream-otel-bumps-renovate-prs-that-auto.md), [DEC-55](../docs/decisions/DEC-55-dependency-only-merges-are-released.md), [DEC-56](../docs/decisions/DEC-56-ci-github-actions-on-push-and-pull-requests.md), [DEC-57](../docs/decisions/DEC-57-strict-otel-pins-capped-at-the-next-minor.md), [DEC-63](../docs/decisions/DEC-63-v0-is-pinned-by-a-characterization-suite-plain.md); [the criteria](../docs/criteria.md)
- [v1 design evidence](../docs/evidence/v1-design-evidence-2026-10-18.md): the upstream behaviours the canaries pin

## Log

- 2026-10-18j (claude-code/2.1.287): Renovate behaviour, checked against its docs and tests (renovatebot/renovate main, docs/usage/configuration-options.md and lib/modules/versioning/pep440/index.spec.ts):
  (1) ignoreUnstable defaults on: it skips 0.65b0 -> 0.66b0 (it allows an unstable target only when major.minor.patch is unchanged), so the contrib packages need a packageRule with ignoreUnstable: false.
  (2) Automerge needs every status check green, and a PR with no checks is not merged unless ignoreTests is true: fail-safe as long as ignoreTests stays off.
  (3) The pep440 rangeStrategy 'replace' moves a window: '>=1.0.0,<1.1.0' with 1.2.0 becomes '>=1.2.0,<1.3.0' (spec line 169). No Renovate test covers a pre-release window such as '>=0.65b0,<0.66'; still unverified.
  (4) pyproject.toml pins no OTel package yet (strict pins come with OTW-13), so Renovate and auto-release have nothing to bump until then.
- 2026-10-18j (claude-code/2.1.287): Built the OTW_IMPL adapter (DEC-38): tests/impl.py binds neutral names (decorate, instrument_app, instrument_engine, setup, and the other v0 entry points under their own names) to v0, resolving them lazily; under v1 every name is a stub that raises NotImplementedError, and conftest skips v0_specific tests. Every test and scenario goes through it, except test_public_api, which checks v0's own names on the package itself. Gate: 214 passed, 1 skipped, 23 xfailed. OTW_IMPL=v1: 47 failed, 42 passed, 84 skipped, 20 xfailed, 45 errors (runs to completion).
  Not marked v0_specific but reaching into v0 internals, to settle when v1's API is: test_v0_extract_json_header.py (the whole module); the test_v0_sqlalchemy.py scenarios importing engine_typedef or instrument_sqlalchemy; test_v0_example_scripts.py (runs the v0 example scripts); every test using the spans fixture or setup_spans() (v0's init_tracer_provider), which is where v1's 45 errors come from.
  Left in OTW-2: the canaries (tests/upstream), the interleaving tests, the micro-benchmark, CI.
- 2026-10-18k (claude-code/2.1.287): Built the canaries (tests/upstream, 8 modules, 26 tests, marker 'upstream' set by tests/conftest.py): EngineTracer import path, signature, pre-existing engines, no duplicate spans (each tracer overwrites context._otel_span, so the earlier span is never ended), connect spans from the instrumentor only; the contextmanager/asynccontextmanager shared __code__ and __wrapped__; ReadableSpan, Event, Link and LogRecord copy kwargs and the sdk._logs names the scrubbing wrappers use; the post-fork resource update (Linux only, skipped on Windows, not yet run); ProxyTracer and an instrumentor created before the provider; resource precedence (DEC-33); FastAPI instrument_app exclude_spans and idempotency; the SDK LoggingHandler deprecation (comment on OTW-11). Each canary but the fork one was seen red under a monkeypatched break of its upstream behaviour (15 breaks, in a scratch worktree). Also tests/test_interleaving.py (two tasks plus a thread, against the OTel tracer, with the sketch's shared stack as the known-bad control), benchmarks/overhead.py with a smoke test (v0: ~32 us bare OTel span, ~58 us decorated, no processor), and CI: .github/workflows/tests.yml + ci/test.sh, Linux, 3.12/3.13/3.14. Gate: 243 passed, 2 skipped, 23 xfailed; OTW_IMPL=v1: 47 failed, 71 passed, 85 skipped, 20 xfailed, 45 errors. Left: the first push and its CI run (owner's yes needed), which is also the fork canary's first run; the extras axis of DEC-56's matrix waits for OTW-13, since v0 has no optional extras; interleaving through v1's 'with otel:' once tests/impl.py binds it.
