---
type: Task
id: OTW-23
title: 'scrubbing.report_failure: OTEL_WRAPPER_DEBUG=false turns tracebacks on; fold it into _warnings.report'
brief: one reporter for swallowed failures, one truthiness rule for OTEL_WRAPPER_DEBUG
pri: NOW
state: closed
deps: []
source: session 2026-10-19a
created: 2026-10-20
moved: 2026-10-19a
updated: 2026-10-19a
status: deprecated
closed: 2026-10-19a
---

Found by OTW-16 (2026-10-19a). opentelemetry_wrapper/v1/scrubbing.py report_failure treats any non-empty OTEL_WRAPPER_DEBUG as on (bool(os.environ.get(DEBUG_ENV))), so =false or =0 turns tracebacks on for scrubbing failures; _warnings._debug() accepts only true or 1. scrubbing.py also keeps its own reporter whose JSON record differs from _warnings.report's ('internal error swallowed' vs 'internal error, swallowed'; error vs error.type); its docstring says 'OTW-3 may replace this function', which never happened. DEC-74/75/82 govern scrubbing failures.

**Done when:** scrubbing failures go through _warnings.report (same record shape, once per site as DEC-81 says), OTEL_WRAPPER_DEBUG has one truthiness rule, and a test pins both (false/0 give no traceback).

## Log

- 2026-10-19a (claude-code/2.1.287): closed: done in d9e2d1c: scrubbing failures through _warnings.report, one OTEL_WRAPPER_DEBUG rule, DEC-94 A + shape
