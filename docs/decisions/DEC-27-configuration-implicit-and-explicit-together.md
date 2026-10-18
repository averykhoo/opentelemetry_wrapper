---
type: Decision
id: DEC-27
title: 'Configuration: implicit and explicit together, final once built (proposal 1)'
actor: owner
decided: 2026-10-08
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:a64c47165a8af4c4df5198290d2ec07eaec089bc0e6936bb9dcbaa6a234dc793
tags: [config]
---

- **Configuration: implicit and explicit together** (was proposal 1, with the review's changes; rule 2 changed
  2026-10-17 with the move to the plain SDK).
  1. Decorating never configures anything, so import order doesn't matter. The first span configures from env vars,
     **only if nothing has configured yet** (tracked in our own state, under a lock so "configure if not yet
     configured" is atomic across threads). `otel.instrument(...)` configures **eagerly**, since nearly every app
     calls it at startup; that keeps configuration (file reads, exporter threads, a port bind) off the first request
     and out of the event loop.
  2. `otel.configure(...)` takes a typed signature (not "env var names in lowercase"). Explicit > env > default. Same
     arguments again (normalised, env-derived defaults included): no-op. **Configuration is final once built** (by
     `otel.configure`, `otel.instrument` or the first span): a later call with different arguments warns once and is
     ignored, except for the log level (Q9). So `otel.configure(...)` goes before `otel.instrument(...)`, or
     configuration comes from env vars alone; the README says so. Reasons: the SDK's global providers can be set only
     once (replacing them means proxy providers for all three signals, ~800 lines in logfire), a Prometheus port can't
     be bound twice, and a second `PrometheusMetricReader` collides in the global registry. Instrumenting before
     configuring loses nothing: *verified*, contrib instrumentors created before any provider get the API's
     `ProxyTracer`, which picks up the provider set later.
  3. Test capture survives configuration: a pytest plugin (`pytest11` entry point, loads before app code) registers
     in-memory span and log processors **with us** (the SDK's `InMemorySpanExporter` / `InMemoryLogRecordExporter`,
     behind the same scrubbing wrapper as the real exporters, so tests see what would be exported). Because a
     `pytest11` plugin loads in **every** project that installs the package, auto-loading is passive: it only
     registers the `otel_spans` / `otel_logs` fixtures (reset per test). Exporters and Prometheus are switched off
     only when a test opts in (Q10), by swapping the sinks of our own span and log processors (public SDK API; works
     after configuration). Document `-p no:opentelemetry_wrapper`.
  4. `otel.config`: a read-only view of the effective configuration, secrets redacted (v0 logged its config and
     leaked the OTLP auth header).
  5. **Someone else configured first** (the app called `logfire.configure()`, or set its own provider): *verified*
     (second review, 2026-10-17), the SDK refuses a second `set_tracer_provider` with a log line, so either order gives two
     pipelines, never a crash. Policy: warn once; if the existing provider is an SDK `TracerProvider` /
     `LoggerProvider`, attach our processors to it, otherwise leave it alone.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
