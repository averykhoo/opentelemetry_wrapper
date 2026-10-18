---
type: Decision
id: DEC-33
title: 'Resource precedence: our detectors < `OTEL_SERVICE_NAME` / `OTEL_RESOURCE_ATTRIBUTES` < explicit arguments'
actor: owner
decided: 2026-10-17
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:830518bb88267bc4410feb242cfab791124c7ea678e57a29145b65875a417e2c
tags: [resources]
tasks: [OTW-9]
---

- **Resource precedence:** our detectors (guesses) < `OTEL_SERVICE_NAME` / `OTEL_RESOURCE_ATTRIBUTES` < explicit
  `otel.configure(...)` arguments. *Verified* in the spike (`Resource.create()`, then our detectors, then
  `OTELResourceDetector().detect()`, then the explicit attributes): `OTEL_SERVICE_NAME` beats a k8s guess, and an
  explicit `service_name` beats `OTEL_SERVICE_NAME`. Test: `OTEL_SERVICE_NAME` wins in k8s.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
