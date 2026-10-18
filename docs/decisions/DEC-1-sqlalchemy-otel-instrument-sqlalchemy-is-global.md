---
type: Decision
id: DEC-1
title: 'SQLAlchemy: `otel.instrument(sqlalchemy)` is global, `otel.instrument(engine)` is per engine (Q1)'
actor: owner
decided: 2026-10-07
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
aliases: [Q-1]
body_sha: sha256:ad6eb7c76788729ddc22066bdee2d148bdbec09e07cf11e9caf62f5c73ce6ba1
tags: [sqlalchemy]
---

- **Q1. SQLAlchemy engines created later.** *Decided 2026-10-07*, see workstream 2: `otel.instrument(sqlalchemy)`
  instruments globally (later engines included, `connect` spans on); `otel.instrument(engine)` instruments that engine
  only, without `connect` spans; the engine docs state this.

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

*Imported at adoption (2026-10-18) from `PLAN.md` § Questions for later, `PLAN.md` § Workstreams § 2. SQLAlchemy, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
