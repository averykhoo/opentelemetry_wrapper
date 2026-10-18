---
type: Decision
id: DEC-26
title: No arguments or return values on spans
actor: owner
decided: 2026-10-08
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:47a59f002572da036908f0c7d9dd0c36c12484681dec98fe9bad99c95b66c580
tags: [telemetry]
tasks: [OTW-3]
---

- **No arguments or return values on spans.** PII, payload size, and parameter names colliding with real attribute
  keys. (*Verified* counter-example: `logfire.instrument` records every argument by default as a top-level attribute
  named after the parameter.) Users add what they need via `attributes={...}` or the span.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
