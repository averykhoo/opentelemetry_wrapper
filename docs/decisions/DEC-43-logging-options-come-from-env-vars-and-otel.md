---
type: Decision
id: DEC-43
title: Logging options come from env vars and `otel.configure(...)` only
actor: owner
decided: 2026-10-08
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:fef7d845ffa5f31ea4e8d6f63bf5af1c5ba3e77a5499795686e2d72d970bd76f
tags: [logging]
tasks: [OTW-11]
---

- **Logging options** come from env vars and `otel.configure(...)` only, not `otel.instrument(logging, level=...)`:
  per-call options would make "instrument twice = once" ambiguous.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
