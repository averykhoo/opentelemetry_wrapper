---
type: Decision
id: DEC-48
title: '`@property` on top, `@otel` underneath (proposal 6)'
actor: owner + agent
decided: 2026-10-08
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:f23d3ad590a7e7e2066e84fdc18c23e508bba6d68ed3e8588a74587a058b6574
tags: [api]
---

6. **Decorator order with `@property`** (F7): document `@property` on top, `@otel` underneath. *Verified:* mypy
   rejects *any* decorator above `@property` (`[prop-decorator]`). This is a mypy limitation; Python accepts both
   orders, and v1 handles both at runtime.

*Imported at adoption (2026-10-18) from `PLAN.md` § Proposals, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
