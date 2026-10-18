---
type: Decision
id: DEC-51
title: Logfire's `distributed_tracing=True` option (proposal 9)
actor: owner
decided: 2026-10-17
session: 2026-10-18a
decision_status: REJECTED
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:1471aebe25d2a140d2006b3f2bbaff0d55d31670b679b79fc24de1b81f8cc917
tags: [telemetry]
reopen_if: v1 depends on logfire again (DEC-15 superseded)
---

9. *Withdrawn with logfire.* It was logfire's `distributed_tracing=True`. On the plain SDK an incoming `traceparent`
   is simply continued (the default W3C propagator), *verified*: same trace id, no warning. (Logfire without the option
   also exported a log span of its own, "Found propagated trace context".)

*Imported at adoption (2026-10-18) from `PLAN.md` § Proposals, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
