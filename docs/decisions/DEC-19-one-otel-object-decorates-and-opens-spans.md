---
type: Decision
id: DEC-19
title: One `otel` object decorates and opens spans; integrations use `otel.instrument(x)`
actor: owner
decided: 2026-10-08
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:1c143b93f21ca00dcd9ae5034c9f893f0e4a6b61c5576479a50e944a3fa2f5fa
tags: [api]
tasks: [OTW-3]
---

- **One `otel` object** that decorates (functions, methods, classes, dataclasses, generators, context managers) and
  opens spans (`with otel:`, `with otel('name'):`). Libraries and apps use **`otel.instrument(x)`**, and
  `otel.instrument()` with no arguments instruments everything global that's installed (v0's `instrument_all()`).
  Bare `otel(app)` was rejected: unreadable in review, and the supported set is undiscoverable.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
