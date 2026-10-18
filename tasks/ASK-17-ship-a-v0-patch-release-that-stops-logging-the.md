---
type: Question
id: ASK-17
title: Ship a v0 patch release that stops logging the OTLP auth header?
brief: 'owner-only: a release is outward-facing; v1 fixes it by design (DEC-27, DEC-58)'
pri: NEXT
state: open
deps: []
source: session 2026-10-18a
created: 2026-10-18
moved: 2026-10-18a
updated: 2026-10-18a
last_asked:
---

**Question:** v0's `instrument_all()` logs `OTEL_EXPORTER_OTLP_HEADER` verbatim at startup (`opentelemetry_wrapper/__init__.py`, the config dict it logs), and that header usually carries an auth token, so every v0 user's startup log holds their collector credential. Patch v0 (redact the header values in that log line, release `0.1.26`), or leave it until v1 replaces v0?

**Why the owner:** a release to PyPI is outward-facing and the owner cuts v0 releases by hand (`CLAUDE.md` § Release).

**Options:**
1. Patch v0 now: a one-line redaction plus a test, then `flit publish`. *Recommended:* v1 is many workstreams away, the leak is in every v0 deployment that sets the header, and the fix is small and testable against the existing suite (the bug is in the old `HANDOFF.md` § TODO, "Secrets in logs").
2. Leave it for v1, which never logs its configuration (`otel.config` redacts secrets, DEC-27) and scrubs exports (DEC-58); say so in the README.

**Blocks:** nothing on the board; OTW-18 (v0 cleanup) points here.
