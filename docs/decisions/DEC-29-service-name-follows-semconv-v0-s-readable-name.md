---
type: Decision
id: DEC-29
title: "`service.name` follows semconv; v0's readable name moves to `opentelemetry_wrapper.instance.label`"
actor: owner
decided: 2026-10-08
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:cffd8526cbf97d010da6a60eb195b5298d889f7a2a7fbe327cefb4963e8c120d
tags: [resources]
---

- **`service.name` follows semconv** (the workload name); breaking existing dashboards is accepted. v0's readable
  `ns/workload/pod` or `user@host:main.py` string moves to `opentelemetry_wrapper.instance.label`, and
  `service.instance.id` stays a per-process UUID (workstream 6, "Service identity").

**Service identity: strict semconv names, v0's readable label kept separately.**

- `service.name`: `OTEL_SERVICE_NAME` (or `service.name` in `OTEL_RESOURCE_ATTRIBUTES`) if set; otherwise the
  semconv k8s derivation (annotation, `app.kubernetes.io/*` labels, workload name from an unambiguous pod-name
  shape); otherwise `unknown_service:<process.executable.name>`.
- `service.namespace`: the k8s namespace.
- `service.instance.id`: keep the SDK's random UUID per process. Stable semconv recommends UUIDs, treats pod/namespace
  as data to expose in other attributes, and wants one id per worker process. The k8s-derived
  `<ns>.<pod>.<container>` is the same for every uvicorn/gunicorn worker in a container, so it breaks uniqueness. Use
  it only if the annotation sets it explicitly.
- **`opentelemetry_wrapper.instance.label`** (resource attribute, ours): v0's string, `<namespace>/<workload>/<pod>` in
  k8s, `<user>@<host.domain>:<main.py>` elsewhere. Every part is *also* in its own semconv attribute (`k8s.*`,
  `process.owner`, `host.name`, `process.command_args`); the label is the readable one-glance version.
- It shows up as a resource attribute on every span and log (searchable in Tempo/Grafana etc.) and in Prometheus as a
  `target_info` label (verified with the pull exporter). With OTLP push, Prometheus derives `job` from
  `service.namespace/service.name` and `instance` from `service.instance.id`, per the OTel spec (not verified here).

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, `PLAN.md` § Workstreams § 6. Resource detectors, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
