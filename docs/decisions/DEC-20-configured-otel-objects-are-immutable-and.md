---
type: Decision
id: DEC-20
title: Configured `otel(...)` objects are immutable and stateless; span state lives in a `ContextVar`
actor: owner
decided: 2026-10-08
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:c2edca557acd1a31cd9246387102c4211eccafa04dc9a6b21d697b3eb0a7abab
tags: [api]
---

- **Configured objects (`otel(name=...)`) are immutable and stateless**; per-entry span state lives in a `ContextVar`.
  v0's sketch kept a span stack on the shared object, which breaks under concurrency (see "Public API notes").

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
