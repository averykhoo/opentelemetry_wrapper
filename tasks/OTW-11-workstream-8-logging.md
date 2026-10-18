---
type: Task
id: OTW-11
title: 'Workstream 8: logging'
brief: two handlers on the root logger, no global log record factory
pri: LATER
state: open
deps: [OTW-4]
source: session 2026-10-18a
created: 2026-10-18
moved: 2026-10-18a
updated: 2026-10-18a
aliases: [WS8]
labels: [v1]
---

Criteria: AC-18. Decisions: DEC-13, DEC-32, DEC-34, DEC-43.

*Workstream 8 of the v1 design, verbatim from the pre-adoption `PLAN.md` (`docs/archive/PLAN.md`); there, "workstream n" is the task aliased `WSn` (OTW-1 lists them), "Decided" / "proposal n" / "Qn" are decisions (`docs/evidence/adoption-map-2026-10-18.md`), and "`HANDOFF.md`" is the old note in `docs/evidence/history-to-2026-10-18.md`.*

Two handlers on the root logger, nothing else:

- **OTLP:** the `LoggingHandler` from `opentelemetry-instrumentation-logging` (the SDK's own is deprecated in 1.44,
  see "Decided"), on our `LoggerProvider`. Use only its handler, not `LoggingInstrumentor`'s record-factory
  injection. Re-check with this handler what PLAN verified with the SDK one (ids, extras, stable `code.*` keys).
- **stderr:** one-line JSON logs with `otelTraceID` / `otelSpanID` (for log pipelines that aren't OTLP, e.g.
  fluentd/Loki), plus v0's `otelTraceSampled`, `tz_name`, `tz_utc_offset_seconds` and local ISO `asctime`. The ids
  come from a `logging.Filter` on this handler that reads `trace.get_current_span().get_span_context()`: no global
  log record factory (v0's needs an `update_wrapper` workaround). The line goes through the scrubber (workstream 5b)
  before it's written.

Keep v0's "JSON-encode anything" (NaN/inf, complex, Decimal, modules, functions, classes, extra args; pydantic per the
decision) and long-string truncation. Fix the negative-UTC-offset bug (and recompute the offset per record, for DST).
`OTEL_WRAPPER_LOG_FORMAT=off` turns the stderr handler off. v0's `clobber_other_log_handlers` has no equivalent yet;
if needed, `otel.configure(replace_log_handlers=True)`.

`uvicorn.access` logs duplicate the request spans: leave them on stderr but don't send them over OTLP by default.

**Done when:** a log inside a span is exported as a log record with that span's ids and extras; a log outside spans
is exported with zero ids; the JSON line on stderr carries the same ids; instrumenting logging twice leaves two
handlers, not four; `tests/v0` logging tests pass under `OTW_IMPL=v1`.

## Traps

- What PLAN verified with the SDK's `LoggingHandler` (ids, extras, stable `code.*` keys) is not yet re-checked with the contrib handler v1 uses.

## Read first

- The decisions: [DEC-13](../docs/decisions/index.md), [DEC-32](../docs/decisions/index.md), [DEC-34](../docs/decisions/index.md), [DEC-43](../docs/decisions/index.md); [the criteria](../docs/criteria.md)
- [v1 design evidence](../docs/evidence/v1-design-evidence-2026-10-18.md): Logs
