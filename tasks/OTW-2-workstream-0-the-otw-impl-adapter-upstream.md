---
type: Task
id: OTW-2
title: 'Workstream 0: the OTW_IMPL adapter, upstream canaries, CI, Renovate and auto-release'
brief: Renovate must group opentelemetry-*, move the upper cap and accept 0.XbY pre-releases; auto-merge only on green CI
pri: NOW
state: open
deps: []
source: session 2026-10-18a
created: 2026-10-18
moved: 2026-10-18a
updated: 2026-10-18a
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

- Renovate's config for OTel's contrib packages is unverified: they are PEP 440 pre-releases (`0.66b0`), which Renovate may skip as unstable; SDK and contrib must move in one grouped PR (DEC-54).
- The post-fork resource canary (`_handle_fork`) can only run on Linux CI: there is no fork on Windows.
- Above the design-review threshold (it ships automation that merges and publishes by itself: `shipped`, `write-op`): write its `## Design review` and `task set OTW-2 --set review=[shipped, write-op]` before building (FRAMEWORK §5.2).
- `asyncio.iscoroutinefunction` (v0's `instrument_decorator.py`, `type_checking.py`) is deprecated in Python 3.14, which the CI matrix runs (DEC-56): expect `DeprecationWarning`s there, and errors if warnings are errors (OTW-18).
- The evidence scripts this replaces exist only on the author's machine; the claims they checked are in the evidence doc below.

## Read first

- The decisions: [DEC-38](../docs/decisions/DEC-38-proven-safe-is-one-command-tests-v0-under-otw.md), [DEC-54](../docs/decisions/DEC-54-upstream-otel-bumps-renovate-prs-that-auto.md), [DEC-55](../docs/decisions/DEC-55-dependency-only-merges-are-released.md), [DEC-56](../docs/decisions/DEC-56-ci-github-actions-on-push-and-pull-requests.md), [DEC-57](../docs/decisions/DEC-57-strict-otel-pins-capped-at-the-next-minor.md), [DEC-63](../docs/decisions/DEC-63-v0-is-pinned-by-a-characterization-suite-plain.md); [the criteria](../docs/criteria.md)
- [v1 design evidence](../docs/evidence/v1-design-evidence-2026-10-18.md): the upstream behaviours the canaries pin
