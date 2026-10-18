---
type: Decision
id: DEC-32
title: Logs are real OTel log records, never spans
actor: owner
decided: 2026-10-08
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:bbc7fd2785d6c69ab51a0741f394164f4871cbc46c3998004686435a4f65ce51
tags: [logging]
tasks: [OTW-11]
---

- **Logs are real OTel log records**, never spans: a handler on the root logger feeding a `LoggerProvider` we always
  install (exporter only when an endpoint is set). The handler is the one from `opentelemetry-instrumentation-logging`
  (decided 2026-10-17): *verified*, the SDK's own `LoggingHandler` emits a `DeprecationWarning` at construction in
  1.44 pointing there. A record logged inside a span carries that span's `trace_id` / `span_id` (that's how backends
  show it on the span: it's correlated, not a child in the span tree), `extra={...}` becomes attributes, and the code
  location uses the stable keys (*verified* with the SDK handler; re-check with the contrib one). Logs are **not**
  affected by head sampling: at a 0% ratio the spans are dropped but every log record is still exported (with
  `trace_flags=0`), and a log outside any span has no trace ids. Both span and log capture are tested through the same
  pytest plugin.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
