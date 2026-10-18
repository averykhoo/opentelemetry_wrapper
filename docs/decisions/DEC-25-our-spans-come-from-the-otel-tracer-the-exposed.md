---
type: Decision
id: DEC-25
title: Our spans come from the OTel tracer; the exposed span type is OTel's `trace.Span` (proposal 2)
actor: owner
decided: 2026-10-08
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:b481574c4e4c83874c5ba6a1230b02fb8f18ba173f3f0712611f91da798b2e26
tags: [api]
tasks: [OTW-14, OTW-3]
---

- **Our spans come from the OTel tracer** (`trace.get_tracer(...)`), and the exposed span type is OTel's `trace.Span`
  (was proposal 2), the same in enabled and disabled mode.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
