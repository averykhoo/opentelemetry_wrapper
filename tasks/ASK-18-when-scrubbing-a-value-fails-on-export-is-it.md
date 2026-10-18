---
type: Question
id: ASK-18
title: When scrubbing a value fails on export, is it dropped (AC-13) or sent unscrubbed?
brief: DEC-72 ranks telemetry output above no secrets; AC-13 drops only the failing value and still exports the record
pri: NEXT
state: open
deps: []
source: session 2026-10-18e
created: 2026-10-18
moved: 2026-10-18e
updated: 2026-10-18e
last_asked: 2026-10-18e
blocks: [OTW-8]
---

DEC-72: never crash wins, then telemetry output, then no secrets. AC-13 (from PLAN.md's workstream 5b) already resolves the case without giving up any of the three: if scrubbing a value fails, that one value is dropped and noted in `opentelemetry_wrapper.scrubbed`, and the span or log record is still exported. The ranking would bite only if 'telemetry output' means the failing value itself must go out, unscrubbed.

**Recommendation:** keep AC-13 as it is (drop the value, export the rest, note it). Nothing crashes, the record still goes out, and no unscrubbed value leaves. The charter documents the case either way.
