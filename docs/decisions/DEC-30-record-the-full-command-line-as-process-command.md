---
type: Decision
id: DEC-30
title: Record the full command line as `process.command_args`, plus the Python environment
actor: owner
decided: 2026-10-08
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:556d43c0190f5b9f19dac73d35de7a6f2dda66b30a21aadfe6f57d0e3e716903
tags: [resources]
tasks: [OTW-9]
---

- **Full command line** recorded as `process.command_args` (from `sys.orig_argv`, sanitized), plus our
  `opentelemetry_wrapper.python.environment` (conda / venv / system / pyodide / frozen), so it's clear which
  interpreter ran the process.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
