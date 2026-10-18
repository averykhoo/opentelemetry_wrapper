---
type: Decision
id: DEC-11
title: '`otel.instrument()` with no arguments: logging, requests, system metrics (Q11)'
actor: owner
decided: 2026-10-18
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
aliases: [Q-11]
body_sha: sha256:9805bbd8f0f4d64876cb2332f4a1dc709caa0d1f6df42602d50d6254a7e54ea5
tags: [api]
tasks: [OTW-3, OTW-4]
---

- **Q11. `otel.instrument()` with no arguments:** logging, requests, system metrics (the `[system-metrics]` extra);
  never apps, engines or SQLAlchemy. That's v0's `instrument_all()` set minus global dataclass instrumentation
  (dropped). *Decided 2026-10-18.*

*Imported at adoption (2026-10-18) from `PLAN.md` § Questions for later, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
