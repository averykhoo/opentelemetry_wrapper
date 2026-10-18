---
type: Story
id: STORY-9
title: Exported telemetry carries no secrets by default
actor: agent (reconstructed from PLAN.md § v0 lessons and § Workstreams 5b)
story_status: live
goals: [G-9]
date: 2026-10-18
via: adoption, session 2026-10-18a
body_sha: sha256:36015804833dff28163165f611e183ca2a6362cf79e14ee86d5a0c2cea04f2a8
---

AGENT: reconstructed at adoption (2026-10-18) from PLAN.md § v0 lessons and § Workstreams 5b (now `docs/archive/PLAN.md`), which the agent wrote from the owner's answers; not the owner's words. Unconfirmed until the owner reviews the charter. The source, verbatim:

- **Never log secrets** (v0's `instrument_all()` logs the OTLP auth header).

Our own rules, designed from examples (2026-10-18), not copied from logfire's list. Applied in wrappers around every
exporter we build (spans: attributes, event and link attributes; logs: attributes and body; the in-memory test
exporters too), on the exporter thread, so the cost stays off the caller's path; also to the stderr JSON logs
(decided 2026-10-17) and, via `scrub_argv`, to `process.command_args`. Defence in depth: the primary controls remain
"no arguments on spans" and the header denylist. Anything not behind our wrappers (a user's own processors) is
unscrubbed; README says so.

## Amendments

- **2026-10-18e (claude-code/2.1.287):** **2026-10-18e, owner confirmation:** reviewing STORY-1 to STORY-10 one by one, the owner: *"Okay for 6 to 10"*. Confirmed as written; `story_status` moved from `unconfirmed` to `live`.
