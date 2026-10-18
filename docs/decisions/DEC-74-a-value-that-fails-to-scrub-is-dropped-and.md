---
type: Decision
id: DEC-74
title: A value that fails to scrub is dropped and replaced by its own 'scrubbing failed' placeholder
actor: owner
decided: 2026-10-18
session: 2026-10-18e
decision_status: PROVISIONAL
answers: ASK-18
body_sha: sha256:47cfbcf80991b5c7f28a1472ab209491b84f02cebefe3f4e2391a70a5586cdce
---

Owner, answering ASK-18: *"Owner, 2026-10-18e, answering ASK-18 (when scrubbing a value fails on export: drop it, as AC-13 says, or send it unscrubbed; the agent recommended dropping just that value and still exporting the record): *"If scrubbing fails, drop anyway - okay but the scrubbed value should say as such, not merely the same truncated or sanitized placeholder, it should also say scrubbing failed"*

Applied: a value that fails to scrub is still dropped, and the rest of the record is exported. It is replaced by a placeholder of its own, distinct from the normal `[REDACTED]`: `[REDACTED: scrubbing failed]` (the agent's wording). `opentelemetry_wrapper.scrubbed` names the failure too, with the path and the rule, never the value. AC-13 is reworded to match."*
