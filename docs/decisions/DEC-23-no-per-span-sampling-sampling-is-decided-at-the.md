---
type: Decision
id: DEC-23
title: 'No per-span sampling: sampling is decided at the root span through the standard env vars'
actor: owner
decided: 2026-10-08
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:9d525f24d0c9417354ea556d2880b46957736e79626437be6f40543da62d683b
tags: [telemetry]
tasks: [OTW-3]
---

- **No per-span sampling.** Sampling is decided at the root span, via the standard `OTEL_TRACES_SAMPLER` /
  `OTEL_TRACES_SAMPLER_ARG`, which the SDK reads itself (all standard samplers; *verified*: `always_off` exports 0,
  `always_on` with an ARG exports everything).

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
