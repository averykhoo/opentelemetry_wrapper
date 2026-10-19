---
type: Decision
id: DEC-92
title: OTEL_METRICS_EXPORTER=prometheus serves on 9464; a scrape path is served with and without its trailing slash, no redirect
decision_status: PROVISIONAL
actor: owner
tasks: [OTW-12]
tags: [api]
decided: 2026-10-19
session: 2026-10-19a
body_sha: sha256:5f044cdb1e7637d3cfc9be949051453068d7bf6fb173ecacd3fb4f6dc4c35cab
---

Owner, 2026-10-19 (session 2026-10-19a). The session asked two multiple-choice questions.

1. "Prometheus: should the standard SDK switch `OTEL_METRICS_EXPORTER=prometheus` start the standalone scrape server on the spec's default port 9464? The reviewer's fix already does this (it was rejected with a warning before). Otherwise the server starts only when OTEL_EXPORTER_PROMETHEUS_PORT is set, as in v0. DEC-59 lists only otlp, console and none." The owner chose, verbatim:

> Yes, keep it (Recommended)

whose option read: "Follow the standard: `prometheus` in OTEL_METRICS_EXPORTER serves on 9464 unless a port is given. It applies only when someone sets it explicitly, and DEC-59 is amended to say so."

2. "When the Prometheus path ends in '/', like '/metrics/', v1 adds that exact route, and Starlette answers '/metrics' with an absolute 307 redirect. v0 mounted the app on purpose, with a relative redirect, for forward proxies. What should v1 do?" The owner chose, verbatim:

> Serve both, no redirect (Recommended)

whose option read: "Register the scrape at both '/metrics' and '/metrics/'. No redirect at all, so there's nothing for a proxy to break, and both stay untraced."
