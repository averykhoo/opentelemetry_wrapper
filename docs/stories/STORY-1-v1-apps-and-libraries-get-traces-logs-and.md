---
type: Story
id: STORY-1
title: v1 apps and libraries get traces, logs and metrics from one `otel` object on the plain OTel SDK
actor: agent (reconstructed from PLAN.md § Goal)
story_status: live
goals: [G-1]
date: 2026-10-18
via: adoption, session 2026-10-18a
body_sha: sha256:a330fc3c59bf0b6920d723d0b762c3b7bda5f2ba4fce18e0c6e3ceb4b7faea56
---

AGENT: reconstructed at adoption (2026-10-18) from PLAN.md § Goal (now `docs/archive/PLAN.md`), which the agent wrote from the owner's answers; not the owner's words. Unconfirmed until the owner reviews the charter. The source, verbatim:

Build directly on the OpenTelemetry SDK (providers, OTLP/HTTP exporters, samplers, resources) and the contrib
instrumentors, plus what neither provides: the `otel` decorator / context manager, idempotent never-crash
instrumentation, introspection, class support, Kubernetes resource detection, `x-userinfo` flattening, scrubbing,
one-line JSON logs and Prometheus. Python floor: **3.12** (the SDK itself needs >= 3.10).

## Amendments

- **2026-10-18e (claude-code/2.1.287):** **2026-10-18e, owner confirmation:** reviewing STORY-1 to STORY-10 one by one, the owner: *"Okay for 1 to 4"*. Confirmed as written; `story_status` moved from `unconfirmed` to `live`.
