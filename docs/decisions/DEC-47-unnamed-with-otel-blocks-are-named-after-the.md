---
type: Decision
id: DEC-47
title: Unnamed `with otel:` blocks are named after the enclosing function (proposal 5)
actor: owner + agent
decided: 2026-10-08
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:f6c7d24b431150719469f423f23799e92b424fd4dd28850dabbee3c52cb88f81
tags: [api]
---

5. **Unnamed `with otel:` blocks** (F6): name them after the enclosing function, not `load_config:42`. A span name
   containing a line number changes whenever the file is edited, breaking dashboards and alerts. The line stays in
   `code.line.number`. Nudge users toward `with otel('name'):`. *(review)* Use module + `co_qualname`
   (`app.config.load_config`, `app.config.<module>`), the same shape as decorated functions, so same-named functions
   in different modules don't collide. The name cache is keyed by (code object, line), so when a second unnamed block
   shows up in the same function, warn once ("two unnamed blocks in X; name them").

*Imported at adoption (2026-10-18) from `PLAN.md` § Proposals, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
