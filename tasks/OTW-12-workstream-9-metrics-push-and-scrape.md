---
type: Task
id: OTW-12
title: 'Workstream 9: metrics, push and scrape'
brief: bind OTEL_EXPORTER_PROMETHEUS_HOST; add_route, never mount; bound the exit flush
pri: LATER
state: open
deps: [OTW-11]
source: session 2026-10-18a
created: 2026-10-18
moved: 2026-10-18a
updated: 2026-10-18a
aliases: [WS9]
labels: [v1]
---

Criteria: AC-19. Decisions: DEC-27, DEC-59.

*Workstream 9 of the v1 design, verbatim from the pre-adoption `PLAN.md` (`docs/archive/PLAN.md`); there, "workstream n" is the task aliased `WSn` (OTW-1 lists them), "Decided" / "proposal n" / "Qn" are decisions (`docs/evidence/adoption-map-2026-10-18.md`), and "`HANDOFF.md`" is the old note in `docs/evidence/history-to-2026-10-18.md`.*

We don't control the platform, so support both and let it choose:

- **Push (OTLP)**: a `PeriodicExportingMetricReader(OTLPMetricExporter())` when `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT`
  (or the generic endpoint) is set. Works with a collector or Prometheus 3's OTLP receiver (`/api/v1/otlp/v1/metrics`).
  The SDK default temporality (cumulative) is what Prometheus' OTLP receiver expects.
- **Scrape (Prometheus pull)**: keep both v0 modes:
  - standalone server on `OTEL_EXPORTER_PROMETHEUS_PORT` (standard, default 9464), **bound to
    `OTEL_EXPORTER_PROMETHEUS_HOST`** (standard, default `localhost`) instead of v0's hardcoded `localhost`. In k8s it
    must be `0.0.0.0`, because Prometheus scrapes the pod IP from outside.
  - FastAPI route at `OTEL_WRAPPER_PROMETHEUS_PATH` (default `/metrics`), for setups that only expose the app's
    port; excluded from request spans by exact path. Use `app.add_route(path, ...)`, not `app.mount`: a mount also
    serves everything under `/metrics/` and redirects `/metrics` there, which an exact-path exclusion would miss
    (the v0 `TODO.md` notes the trailing-slash behaviour).
- Our `PrometheusMetricReader` goes into the `MeterProvider`'s readers at configure time (readers can't be added
  later, one more reason configuration is final once built). *Verified* in the spike: `target_info` is served.
- **Several workers per container** (uvicorn/gunicorn `--workers N`): each worker has its own metrics, but only one
  can bind the Prometheus port (the others get "address in use": warn once, carry on), and the FastAPI route answers
  from whichever worker took the request. That's the `prometheus_client` multiprocess problem. Document: in
  multi-worker deployments use push, or one worker per container.
- **Shutdown:** an unreachable collector can delay process exit while exports retry. Bound the flush at exit (e.g.
  via `OTEL_EXPORTER_OTLP_TIMEOUT`), so a missing collector never holds up a pod's termination or a CLI's exit.
  (*Verified* in the spike: with a dead collector and a 1 s timeout, shutdown took ~2 s.)

Background, verified:

- Prometheus pulls: it finds targets (host:port) via its own service discovery and requests `metrics_path` (default
  `/metrics`) from its scrape config. Neither HOST nor PORT is a remote address; both describe the app's listening
  socket.
- `prometheus_client.start_http_server` serves metrics on **every** path (`/metrics`, `/`, `/anything/at/all` all
  return 200), which is why the spec defines no path variable. Our FastAPI mount does need a path because it shares
  the app's port.
- The SDK marks both variables experimental, and the exporter only reads them itself when created via
  `OTEL_METRICS_EXPORTER=prometheus` (`_AutoPrometheusMetricReader`). When we build `PrometheusMetricReader` ourselves
  we call `start_http_server` ourselves, so we must read HOST ourselves.
- Trade-off: scrape needs every pod reachable from Prometheus plus discovery config (annotations / ServiceMonitor) but
  gives a free `up` health signal; push only needs outbound access to one known address, but a silent pod looks the
  same as an idle one.

**Done when:** standalone server binds `OTEL_EXPORTER_PROMETHEUS_HOST`; `/metrics` on FastAPI returns 200 and makes
no request span, while `/api/metrics` does; with two workers, the second warns once and doesn't crash.

## Traps

- Readers can't be added to a `MeterProvider` later: the Prometheus reader goes in at configure time.

## Read first

- The decisions: [DEC-27](../docs/decisions/DEC-27-configuration-implicit-and-explicit-together.md), [DEC-59](../docs/decisions/DEC-59-environment-variables-standard-names-where-they.md); [the criteria](../docs/criteria.md)
