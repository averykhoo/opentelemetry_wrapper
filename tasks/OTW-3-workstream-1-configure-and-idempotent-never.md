---
type: Task
id: OTW-3
title: 'Workstream 1: configure, and idempotent, never-crash wrappers over the SDK and contrib'
brief: global providers set once under the configuration lock; wrappers keep the target's kind and signature
pri: NEXT
state: open
deps: [OTW-2]
source: session 2026-10-18a
created: 2026-10-18
moved: 2026-10-18a
updated: 2026-10-18a
aliases: [WS1]
labels: [v1]
---

Criteria: AC-1 to AC-7, AC-22; the plain `tests/v0` decorator tests under `OTW_IMPL=v1` (part of AC-8). Decisions: DEC-19, DEC-20, DEC-21, DEC-24, DEC-25, DEC-27, DEC-28, DEC-3, DEC-5, DEC-9, DEC-10, DEC-11, DEC-49.

*Workstream 1 of the v1 design, verbatim from the pre-adoption `PLAN.md` (`docs/archive/PLAN.md`); there, "workstream n" is the task aliased `WSn` (OTW-1 lists them), "Decided" / "proposal n" / "Qn" are decisions (`docs/evidence/adoption-map-2026-10-18.md`), and "`HANDOFF.md`" is the old note in `docs/evidence/history-to-2026-10-18.md`.*

- `configure`: providers for all three signals, OTLP/HTTP exporters per the standard env vars (only when an endpoint
  is set), the SDK's own sampler handling, resources per "Resource precedence", the scrubbing exporter wrappers
  (workstream 5b), swappable span and log sinks for the pytest plugin, the "someone else configured first" policy,
  a bounded shutdown (workstream 9), and an at-exit flush for forked `multiprocessing` children
  (`multiprocessing.util.Finalize`). Global providers are set once, under the configuration lock. Expect ~450 lines.
- One function per integration (`fastapi`, `requests`, `sqlalchemy`, `logging`, system metrics) that records what it
  already instrumented (weakref where the target is an object) and swallows/warns-once on failure, at instrumentation
  time only. Also warn once when an instrumentor hits a `DependencyConflict`: upstream only logs it and produces no
  spans (`HANDOFF.md`, the sqlalchemy and requests cases), which isn't an exception we'd catch.
- FastAPI: `FastAPIInstrumentor.instrument_app(app, exclude_spans=['send', 'receive'], ...)` (*verified*: only the
  server span remains, and a second call neither raises nor duplicates spans).
- `otel.instrument(app)` after the app has started can't add middleware (Starlette raises): warn once, return the app.
- Our own decorator creates spans with the OTel tracer and `CodeInfo` attributes (see "Decided"), and keeps the
  "already instrumented, return the cached wrapper" logic, keyed on the underlying function (see "v0 lessons").
- Wrappers keep the target's kind: `inspect.iscoroutinefunction`, `isgeneratorfunction`, `isasyncgenfunction` and the
  signature (via `__wrapped__`) must be the same as the original's. FastAPI uses them to pick threadpool vs `await`
  and to treat `yield` dependencies as context managers; pytest does the same for fixtures.
- `with otel:` keeps its state in a `ContextVar` holding an immutable value: `set()` on enter, `reset(token)` on
  exit. Never a list that gets mutated: `copy_context()` copies the mapping, not the values, so a mutated list leaks
  between tasks.
- Exception handling per Q3; re-raise with a bare `raise` so tracebacks are untouched, and set `__tracebackhide__`
  (pytest) / `__traceback_hide__` (Sentry and others) in wrapper frames.

**Done when:** functions (sync, async), `with otel:` / `with otel('x'):`, configure (implicit, explicit, final once
built, someone-else-configured-first), disabled mode and the pytest plugin pass their tests; the plain `tests/v0` decorator tests pass under
`OTW_IMPL=v1`.

## Traps

- An instrumentor's `DependencyConflict` is only logged by upstream and produces no spans: not an exception we would catch, so warn once ourselves.
- Starlette raises when middleware is added after the app started: warn once and return the app.
- A `ContextVar` must hold an immutable value: `copy_context()` copies the mapping, not the values.

## Read first

- The decisions: [DEC-19](../docs/decisions/index.md), [DEC-20](../docs/decisions/index.md), [DEC-21](../docs/decisions/index.md), [DEC-24](../docs/decisions/index.md), [DEC-25](../docs/decisions/index.md), [DEC-27](../docs/decisions/index.md), [DEC-28](../docs/decisions/index.md), [DEC-3](../docs/decisions/index.md), [DEC-5](../docs/decisions/index.md), [DEC-9](../docs/decisions/index.md), [DEC-10](../docs/decisions/index.md), [DEC-11](../docs/decisions/index.md), [DEC-49](../docs/decisions/index.md); [the criteria](../docs/criteria.md)
- [v0 lessons](../docs/evidence/v0-lessons-2026-10-07.md)
- [v1 design evidence](../docs/evidence/v1-design-evidence-2026-10-18.md): Public API notes (the shared span stack race)
