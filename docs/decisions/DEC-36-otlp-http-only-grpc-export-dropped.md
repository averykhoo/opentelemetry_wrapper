---
type: Decision
id: DEC-36
title: 'OTLP/HTTP only: gRPC export dropped'
actor: owner
decided: 2026-10-08
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:ad0dff26fbba9337a6a64b8906f1242955481c1cbc0044d22f9dbd8fbb51822e
tags: [packaging]
tasks: [OTW-13]
---

- **gRPC export dropped** for now: OTLP/HTTP only (collectors listen on 4318 by default), which avoids `grpcio`. A
  `[grpc]` extra can come later if someone needs it.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

## Amendments

- **2026-10-18l (claude-code/2.1.287):** 2026-10-19 (session 2026-10-18l, recorded by the agent): the owner's DEC-80 keeps v0's dependencies core until v0 is deleted at 1.0.0, and v0 imports opentelemetry.exporter.otlp.proto.grpc, so the gRPC exporter stays a core dependency until 1.0.0. v1 itself exports over HTTP only; the opentelemetry-exporter-otlp meta package is dropped now (OTW-13).
