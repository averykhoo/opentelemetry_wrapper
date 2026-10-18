---
type: Decision
id: DEC-13
title: Log records keep the bare `record.funcName` (Q13)
actor: owner
decided: 2026-10-18
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
aliases: [Q-13]
body_sha: sha256:1818873d8da64d58d2a109a8c709e43a18e55c109cd5c3dfde1b9e7531d677bf
tags: [logging]
tasks: [OTW-11]
---

- **Q13. Function name on log records:** accept the bare `record.funcName` the handler writes (`load_config`); a log
  record doesn't carry the qualified name, and rebuilding it means a stack walk per log call. *Decided 2026-10-18.*

*Imported at adoption (2026-10-18) from `PLAN.md` § Questions for later, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
