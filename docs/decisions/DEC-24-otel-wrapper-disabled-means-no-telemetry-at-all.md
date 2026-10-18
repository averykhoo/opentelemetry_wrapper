---
type: Decision
id: DEC-24
title: '`OTEL_WRAPPER_DISABLED` means no telemetry at all'
actor: owner
decided: 2026-10-08
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:242f065930f0112af90950029ed50f1f29464f5b15a345a7acf7eaa8df5f4ffe
tags: [config]
tasks: [OTW-3]
---

- **`OTEL_WRAPPER_DISABLED`** means no telemetry at all, for test envs with nowhere to export, where only stack traces
  matter: decorators return the target unchanged (no wrapper frames in tracebacks), `otel.instrument` is a no-op, and
  `with otel as span` yields OTel's standard `NonRecordingSpan` (`trace.INVALID_SPAN`). *Verified:* every method
  works and records nothing, and exceptions propagate untouched. It's read at decoration time, so wrappers that
  already exist also check it at call time (e.g. a test that sets it after import).

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
