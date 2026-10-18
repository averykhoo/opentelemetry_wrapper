---
type: Task
id: OTW-3
title: 'Workstream 1: configure, and idempotent, never-crash wrappers over the SDK and contrib'
brief: global providers set once under the configuration lock; wrappers keep the target's kind and signature
pri: NOW
state: open
deps: [OTW-2]
source: session 2026-10-18a
created: 2026-10-18
moved: 2026-10-18l
updated: 2026-10-18l
aliases: [WS1]
labels: [v1]
---

Criteria: AC-1 to AC-7, AC-22, AC-25 to AC-27, AC-32; the plain `tests/v0` decorator tests under `OTW_IMPL=v1` (part of AC-8). Decisions: DEC-19, DEC-20, DEC-21, DEC-23, DEC-24, DEC-25, DEC-26, DEC-27, DEC-28, DEC-3, DEC-5, DEC-8, DEC-9, DEC-10, DEC-11, DEC-45, DEC-46, DEC-49, DEC-50, DEC-52.

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
- A failure swallowed at runtime is reported (DEC-75): one stderr JSON line per failure site, written directly inside our own `try`/`except`, never through `warnings` (`PYTHONWARNINGS=error` would raise it into the app, DEC-8) or `logging` (our JSON handler could recurse); every occurrence with the traceback under an opt-in variable, named per DEC-59.
- The exporter wrappers take their scrubber from OTW-8 (5b): build them with a pluggable scrubber (identity until OTW-8 lands), so this task does not wait on 5b.

## Read first

- The decisions: [DEC-19](../docs/decisions/DEC-19-one-otel-object-decorates-and-opens-spans.md), [DEC-20](../docs/decisions/DEC-20-configured-otel-objects-are-immutable-and.md), [DEC-21](../docs/decisions/DEC-21-no-blocked-behaviour-code-info-is-looked-up-at.md), [DEC-24](../docs/decisions/DEC-24-otel-wrapper-disabled-means-no-telemetry-at-all.md), [DEC-25](../docs/decisions/DEC-25-our-spans-come-from-the-otel-tracer-the-exposed.md), [DEC-27](../docs/decisions/DEC-27-configuration-implicit-and-explicit-together.md), [DEC-28](../docs/decisions/DEC-28-exporters-are-chosen-from-the-standard-otel-env.md), [DEC-3](../docs/decisions/DEC-3-exception-status-error-on-the-innermost-span.md), [DEC-5](../docs/decisions/DEC-5-otel-sdk-disabled-true-also-means-otel-wrapper.md), [DEC-9](../docs/decisions/DEC-9-only-the-log-level-may-change-after.md), [DEC-10](../docs/decisions/DEC-10-pytest-plugin-opt-in-requesting-otel-spans-otel.md), [DEC-11](../docs/decisions/DEC-11-otel-instrument-with-no-arguments-logging.md), [DEC-49](../docs/decisions/DEC-49-one-otelwrapperwarning-through-warnings-warn-on.md), [DEC-75](../docs/decisions/DEC-75-the-wrapper-reports-its-own-swallowed-runtime.md); [the criteria](../docs/criteria.md)
- [v0 lessons](../docs/evidence/v0-lessons-2026-10-07.md)
- [v1 design evidence](../docs/evidence/v1-design-evidence-2026-10-18.md): Public API notes (the shared span stack race)
