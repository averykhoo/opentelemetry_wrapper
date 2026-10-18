---
type: Decision
id: DEC-4
title: '`process.executable.name` is the base name of `sys.executable` (Q4)'
actor: owner
decided: 2026-10-18
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
aliases: [Q-4]
body_sha: sha256:06ec0dcc1cebb0298c2d011affdf8bc95ff245417f849606c355b8aa1e6dc11e
tags: [resources]
---

- **Q4. `process.executable.name`.** *Decided 2026-10-18:* `os.path.basename(sys.executable)` (*verified*:
  `python.exe` on Windows, same as `psutil.Process().name()`), or `python` when that's empty (e.g. Pyodide). The
  fallback `service.name` is therefore `unknown_service:python.exe` on Windows; `README_v1.md` to match.

*Imported at adoption (2026-10-18) from `PLAN.md` § Questions for later, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
