---
type: Decision
id: DEC-59
title: 'Environment variables: standard names where they exist, `OTEL_WRAPPER_*` for ours'
actor: owner
decided: 2026-10-08
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:41e4add36375f1ddfa733182bd056d02fb814c20b2155f40af4a2eee7bf63b74
tags: [config]
tasks: [OTW-12, OTW-7]
---

| rename env vars to `OTEL_WRAPPER_*` | yes, for the non-standard ones only (table below) |

| v0 | v1 | notes |
|---|---|---|
| `OTEL_SERVICE_NAME` | same | standard |
| `OTEL_SERVICE_NAMESPACE` | `OTEL_RESOURCE_ATTRIBUTES=service.namespace=...` | not a standard variable |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | same, plus per-signal `..._{TRACES,METRICS,LOGS}_ENDPOINT` | standard; HTTP only |
| `OTEL_EXPORTER_OTLP_HEADER` + `_HEADER_SEPARATOR` | `OTEL_EXPORTER_OTLP_HEADERS` | standard |
| `OTEL_EXPORTER_OTLP_INSECURE` | removed | only meaningful for gRPC; use an `http://` / `https://` endpoint |
| `OTEL_EXPORTER_PROMETHEUS_PORT` | same | standard |
| (not read) | `OTEL_EXPORTER_PROMETHEUS_HOST` | standard; fixes the localhost-bind bug |
| `OTEL_EXPORTER_PROMETHEUS_ENDPOINT` | `OTEL_WRAPPER_PROMETHEUS_PATH` | ours, named like a standard variable in v0 |
| `OTEL_LOG_LEVEL` | `OTEL_WRAPPER_LOG_LEVEL` | v0's name **collides** with the standard SDK-internal log level, so the old name is only warned about, not read |
| `OTEL_HEADER_ATTRIBUTES` | `OTEL_WRAPPER_HEADER_ATTRIBUTES` | ours |
| (new) | `OTEL_WRAPPER_HEADER_ATTRIBUTES_EXCLUDE` | ours; claim denylist, workstream 5 |
| (hardcoded in v0) | `OTEL_WRAPPER_RESPONSE_HEADER_ATTRIBUTES` | ours; `requests` response headers, default v0's Kong / Envoy list |
| `OTEL_WRAPPER_DISABLED` | same | ours |
| (new) | `OTEL_WRAPPER_LOG_FORMAT` | `json` / `off` |
| (new) | `OTEL_WRAPPER_CAPTURE_COMMAND_ARGS` | default `true` |
| (new) | `OTEL_WRAPPER_PODINFO_DIR` | ours; Downward API volume with `labels` / `annotations`, default `/etc/podinfo` |
| (new) | `OTEL_TRACES_SAMPLER` / `OTEL_TRACES_SAMPLER_ARG` | standard; read by the SDK |
| (new) | `OTEL_{TRACES,METRICS,LOGS}_EXPORTER` | standard; `otlp` (default when an endpoint is set), `console`, `none` |

Old names are read for one release with a deprecation warning at startup (except `OTEL_LOG_LEVEL`, see above).
`OTEL_SDK_DISABLED=true` (standard) also means `OTEL_WRAPPER_DISABLED` (Q5).

*Imported at adoption (2026-10-18) from `PLAN.md` § Environment variables, `PLAN.md` § `TODO.md` triage against the rebuild, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
