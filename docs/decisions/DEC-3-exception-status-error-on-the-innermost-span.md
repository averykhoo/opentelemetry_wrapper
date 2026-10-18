---
type: Decision
id: DEC-3
title: 'Exception status: ERROR on the innermost span; cancellation and interrupts stay unset (Q3)'
actor: owner
decided: 2026-10-18
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
aliases: [Q-3]
body_sha: sha256:8bc50e98712c93ad0554d2fbaa4bcd003b44dfebb154382ec32ddcb0904f97cd
tags: [api]
---

- **Q3. Exception status.** *Decided 2026-10-18* as follows:

  | raised through the span | status | recorded |
  |---|---|---|
  | `Exception` subclasses, on the innermost span it passes through | ERROR | `exception` event with stack trace, `error.type` |
  | the same exception on each outer span | ERROR | `error.type` only (the stack trace is already on the inner span) |
  | `StopIteration` / `StopAsyncIteration` | unset | nothing (normal end of iteration) |
  | `GeneratorExit` (generator closed early) | unset | `opentelemetry_wrapper.closed_early = true` (workstream 7) |
  | `asyncio.CancelledError` | unset | `opentelemetry_wrapper.cancelled = true` |
  | `KeyboardInterrupt` | unset | `opentelemetry_wrapper.interrupted = true` |
  | `SystemExit` | ERROR if the code is non-zero, else unset | `process.exit.code` |

  `error.type` (fully qualified class name) is semconv's stable attribute for "this operation failed, and why".
  Cancellation is normal control flow (timeouts, client disconnects), so the inner spans aren't errors. Where a
  timeout causes it, `asyncio.timeout` turns it into `TimeoutError` at the scope that set the timeout, and that span
  is ERROR. "Already recorded" is a marker attribute set on the exception object (*verified*: exceptions accept
  attributes but not weak references; `error.type` and `process.exit.code` are semconv constants). Spans always end in `finally`, and exceptions are re-raised with a bare `raise`.

*Imported at adoption (2026-10-18) from `PLAN.md` § Questions for later, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
