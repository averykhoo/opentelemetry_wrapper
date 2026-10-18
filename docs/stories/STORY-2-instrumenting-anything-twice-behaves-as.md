---
type: Story
id: STORY-2
title: Instrumenting anything twice behaves as instrumenting it once
actor: agent (reconstructed from PLAN.md § Principles, item 1)
story_status: unconfirmed
goals: [G-2]
date: 2026-10-18
via: adoption, session 2026-10-18a
body_sha: sha256:62dcabb99475f1dbde64cdbfc602f629a6bcb17212499a059b1e9bef01e0b6c2
---

AGENT: reconstructed at adoption (2026-10-18) from PLAN.md § Principles, item 1 (now `docs/archive/PLAN.md`), which the agent wrote from the owner's answers; not the owner's words. Unconfirmed until the owner reviews the charter. The source, verbatim:

1. **Idempotency.** Every public entry point can be called any number of times, from anywhere, and behaves as if it was
   called once. Includes methods reached through instances (v0 gets this wrong, see "v0 lessons").
