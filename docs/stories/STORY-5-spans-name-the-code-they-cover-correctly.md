---
type: Story
id: STORY-5
title: Spans name the code they cover correctly
actor: agent (reconstructed from PLAN.md § Principles, item 4)
story_status: unconfirmed
goals: [G-5]
date: 2026-10-18
via: adoption, session 2026-10-18a
body_sha: sha256:bb98d2a9d3651d9670409e40996597e9162fc07f7e53edf9a847cfc7ea9ce605
---

AGENT: reconstructed at adoption (2026-10-18) from PLAN.md § Principles, item 4 (now `docs/archive/PLAN.md`), which the agent wrote from the owner's answers; not the owner's words. Unconfirmed until the owner reviews the charter. The source, verbatim:

4. **Introspection** (`CodeInfo`), rewritten per `HANDOFF.md` (`co_qualname`, no `cls` heuristics, stable attributes).

## Amendments

- **2026-10-18e (claude-code/2.1.287):** **2026-10-18e, owner confirmation:** after the agent explained why v1 drops v0's `cls` heuristics (v0 needed them on Python 3.8, which has no `co_qualname`; their last resort re-executes the user's source file with `exec_module`; on 3.12 `co_qualname` gives the same names, `Base.m` for an inherited method, plus `outer.<locals>.Inner.f`, which v0 cannot find), the owner: *"Okay to story 5 too"*. Confirmed as written; `story_status` moved from `unconfirmed` to `live`.
