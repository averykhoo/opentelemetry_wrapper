---
type: Decision
id: DEC-45
title: 'Escape hatches: `otel.span`, `otel.trace_id`, `otel.span_id` (proposal 3)'
actor: owner + agent
decided: 2026-10-08
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:1f0be1818c96255ece52a6f3e08887c22fcebd96001e5ee11f6ed6f752e9d206
tags: [api]
tasks: [OTW-3]
---

3. **Escape hatches** (F4): `otel.span` (current span; a no-op span when there is none, never `None`), `otel.trace_id`
   / `otel.span_id` (hex strings, e.g. to return in an HTTP 500 body; all zeros when there's no span or telemetry is
   disabled). Document `record_exception`, `add_event`, marking a span failed without raising, and stdlib `logging`
   `extra={...}` (*verified*: becomes attributes on the log record).

*Imported at adoption (2026-10-18) from `PLAN.md` § Proposals, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
