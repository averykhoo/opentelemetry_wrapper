---
type: Task
id: OTW-22
title: 'AC-8: the remaining plain tests/v0 tests pass under OTW_IMPL=v1'
brief: v1 proven safe against tests/v0 (DEC-37's gate before v1 becomes the default)
pri: NOW
state: closed
deps: [OTW-12]
source: session 2026-10-19a
created: 2026-10-19
moved: 2026-10-19a
updated: 2026-10-19a
status: deprecated
closed: 2026-10-19a
---

Carries out AC-8 (DEC-38) and DEC-37's 'until it's proven safe against tests/v0'. After OTW-12, 9 plain v0 tests still fail under OTW_IMPL=v1 (OTW-12's report, 2026-10-19a):

- test_v0_fastapi test_request_spans, test_instrumenting_twice_does_not_duplicate_spans_or_raise: expect 'http send' spans that v1 leaves out on purpose (FASTAPI_EXCLUDE_SPANS); mark v0_specific citing the decision, or adapt.
- test_v0_fastapi test_fastapi_main_example_app: fastapi_main.py imports v0 names directly, so its spans never reach the v1 capture.
- test_v0_setup test_instrument_all_* (4): v1's deprecation warning lands on stderr as plain text and breaks the every-line-is-JSON parse; v0's config log has no v1 equivalent; system_metrics_instrumented reads False; the OTLP-header-secret xfail should be v0-only.
- test_v0_setup test_service_name_and_namespace_* (2): tests/impl.py load() does not configure v1, which configures lazily, so the tracer provider is still a proxy.

**Done when:** OTW_IMPL=v1 pytest tests has 0 failures and AC-8 is tested; any behaviour change against v0 is a decision or an owner question, never silent.

## Log

- 2026-10-19a (claude-code/2.1.287): closed: done in 06a00a7: tests/v0 passes under OTW_IMPL=v1 (0 failures), AC-8 tested and gated; DEC-93 switch
