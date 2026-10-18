---
type: Decision
id: DEC-42
title: Global dataclass instrumentation is dropped
actor: owner
decided: 2026-10-08
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:e16d80c75b73d3c34331d84182b12b01da0e57fda9137a314867ace6bed8c33d
tags: [api]
tasks: [OTW-6]
---

- **Global dataclass instrumentation is dropped** (v0's `instrument_dataclasses()`): patching `dataclasses.dataclass`
  depends on import order, contradicting configuration rule 1, and its `__getattribute__` patching is behind several
  v0 bugs. `@otel` on the dataclass covers the real use.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
