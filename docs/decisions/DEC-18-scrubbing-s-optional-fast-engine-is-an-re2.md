---
type: Decision
id: DEC-18
title: Scrubbing's optional fast engine is an `[re2]` hybrid
actor: owner
decided: 2026-10-18
session: 2026-10-18a
decision_status: SUPERSEDED
status: deprecated
superseded_by: [DEC-16]
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:db408fbc49e38b544395c4c543b2ba219e20e1d8a6f8ec676537ab01c059027b
tags: [scrubbing]
---

- **Q16. Scrubbing engine** (benchmark in workstream 5b). *Decided 2026-10-18:* stdlib `re` by default (factored
  alternation, no groups, 32-character prefilter), plus an optional fast engine. First decided as an `[re2]` hybrid
  (`re` for short strings, `re2` for long ones: same speed on attributes, 10-20x faster on log bodies), then replaced
  by `[hyperscan]` (below). Greenery not at runtime; `interegular` as a test-time lint (dev dependency).

*Imported at adoption (2026-10-18) from `PLAN.md` § Questions for later, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

## Amendments

- **2026-10-18a (claude-code/2.1.287):** imported heading note: **SUPERSEDED by Q-16**
