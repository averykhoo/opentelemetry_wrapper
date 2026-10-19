---
type: Task
id: OTW-4
title: 'Workstream 2: SQLAlchemy'
brief: engines that already exist need a per-engine EngineTracer; the global patch only reaches later ones
pri: NEXT
state: open
deps: [OTW-7]
source: session 2026-10-18a
created: 2026-10-18
moved: 2026-10-19a
updated: 2026-10-19a
aliases: [WS2]
labels: [v1]
---

Criteria: AC-9. Decisions: DEC-1, DEC-11, DEC-62.

*Workstream 2 of the v1 design, verbatim from the pre-adoption `PLAN.md` (`docs/archive/PLAN.md`); there, "workstream n" is the task aliased `WSn` (OTW-1 lists them), "Decided" / "proposal n" / "Qn" are decisions (`docs/evidence/adoption-map-2026-10-18.md`), and "`HANDOFF.md`" is the old note in `docs/evidence/history-to-2026-10-18.md`.*

Two ways in (Q1, decided 2026-10-07), both idempotent and combinable:

- **`otel.instrument(sqlalchemy)`** (the module): global. Runs `SQLAlchemyInstrumentor().instrument()` once, which
  patches `create_engine` and `connect`, so every engine created **afterwards** is traced, with `connect` spans.
  Engines that already exist at that point aren't reached by upstream's patch (Evidence, e2), and there's no registry
  to find them, so document "instrument sqlalchemy before creating engines, or also pass the existing ones in".
- **`otel.instrument(engine)`**: that engine only, via a per-engine `EngineTracer`, tracked in a `WeakSet` (see
  evidence). Query spans, **no `connect` spans** (those come only from the global patch). Also handles
  `AsyncEngine` via `.sync_engine`. The README's engine section states this constraint.
- Both together: an engine created after the global call and also passed in gets a second `EngineTracer`, which
  doesn't duplicate spans (*verified*), and the `WeakSet` skips it anyway.
- `otel.instrument()` with no arguments doesn't include sqlalchemy (v0's default too: query spans are noisy); Q11.

- `connections_usage` is a local inside upstream's `_instrument`, not something to fetch: create our own
  `db.client.connections.usage` up-down counter from the same meter.
- `EngineTracer` also takes `enable_commenter` / `commenter_options` / `enable_attribute_commenter`, which v0 exposes
  (`instrument_sqlalchemy.py`). Keep them, as `otel.instrument(engine, commenter=...)` or an env var.
- Attaching `EngineTracer` directly skips upstream's dependency check, which may let v1 drop the `sqlalchemy<2.1` pin
  (`HANDOFF.md`, "Watch upstream"); the hooks work on 2.1.

**Done when:** two pre-existing engines and one created later (and passed in) all produce `SELECT` spans;
after `otel.instrument(sqlalchemy)`, an engine created later and never passed in produces `connect` and `SELECT`
spans; instrumenting an engine twice gives one span per query; `AsyncEngine` works; no sqlalchemy installed ->
warning, no crash.

## Traps

- `EngineTracer` lives in a non-`__init__` module and `connections_usage` is a local in upstream's `_instrument`: canary both (OTW-2), and keep our own `WeakSet`.

## Read first

- The decisions: [DEC-1](../docs/decisions/DEC-1-sqlalchemy-otel-instrument-sqlalchemy-is-global.md), [DEC-11](../docs/decisions/DEC-11-otel-instrument-with-no-arguments-logging.md), [DEC-62](../docs/decisions/DEC-62-v0-pins-sqlalchemy-asyncio-2-1-until-the.md); [the criteria](../docs/criteria.md)
- [v1 design evidence](../docs/evidence/v1-design-evidence-2026-10-18.md): SQLAlchemy
