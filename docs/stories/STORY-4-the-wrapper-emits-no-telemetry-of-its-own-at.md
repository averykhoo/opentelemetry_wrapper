---
type: Story
id: STORY-4
title: The wrapper emits no telemetry of its own at runtime
actor: agent (reconstructed from PLAN.md § Principles, item 3)
story_status: unconfirmed
goals: [G-4]
date: 2026-10-18
via: adoption, session 2026-10-18a
body_sha: sha256:ad47baef26b92edf94384ea2ba890f62df2d220e9803d9f5cfc07409c821387a
---

AGENT: reconstructed at adoption (2026-10-18) from PLAN.md § Principles, item 3 (now `docs/archive/PLAN.md`), which the agent wrote from the owner's answers; not the owner's words. Unconfirmed until the owner reviews the charter. The source, verbatim:

3. **No telemetry of its own at runtime** (v0 deck: "emits zero logs/spans of its own"). Warnings are allowed only at
   startup / decoration / instrumentation time, once each, never per call. Our own entry points emit no spans (v0's
   do).
