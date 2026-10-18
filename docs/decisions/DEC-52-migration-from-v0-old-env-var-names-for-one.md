---
type: Decision
id: DEC-52
title: 'Migration from v0: old env var names for one release, a port-4317 warning, Upgrading notes (proposal 10)'
actor: owner + agent
decided: 2026-10-08
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:2e784471b11a0150016c67d41cf7e5ceea663f1fe4bc0ce7c96f3ce7375fac97
tags: [config]
---

10. **Migration** (F9):
    - old env var names read for one release, with a startup warning. *(review)* Except `OTEL_LOG_LEVEL`: it's the
      SDK's own variable, so honouring it would keep the collision alive. Warn when it's set and
      `OTEL_WRAPPER_LOG_LEVEL` isn't, but don't use it;
    - warn at startup when the OTLP endpoint uses port `4317` or `grpc://` (v0's README example was `:4317`; an HTTP
      exporter posting to a gRPC port fails on every batch, visible only in the SDK's internal logger). *(review)*
      Same warning for `OTEL_EXPORTER_OTLP_PROTOCOL=grpc` and `OTEL_EXPORTER_OTLP_INSECURE`, both of which v0 users
      may have set;
    - *(review)* `OTEL_EXPORTER_OTLP_HEADERS` values are URL-decoded (*verified*, `opentelemetry/util/re.py`), so
      v0's `Authorization: Basic abc==` becomes `Authorization=Basic%20abc==` (the `=` padding is fine: it splits on
      the first `=`). Say so in "Upgrading";
    - keep v0's Downward API recipe for pods without a service account, rewritten for
      `OTEL_RESOURCE_ATTRIBUTES=service.namespace=$(POD_NAMESPACE)`;
    - list the dropped `async ` span-name prefix under "Upgrading".

*Imported at adoption (2026-10-18) from `PLAN.md` § Proposals, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
