---
type: Task
id: OTW-20
title: 'Criteria parsimony: align measures with the Story column, add the G-8 and DEC-26 criteria, remove overlaps'
brief: Charter measures and criteria Story column must match; wait for ASK-20
pri: LATER
state: closed
deps: [ASK-20]
source: session 2026-10-18g
created: 2026-10-18
moved: 2026-10-18h
updated: 2026-10-18h
status: deprecated
closed: 2026-10-18h
---

Agent-level fixes from `docs/evidence/parsimony-review-2026-10-18.md` (findings 2, 3, 4, 8, 9). None of them changes owner words. Do them after ASK-20 is answered, so that the criteria's Story column and the charter's measures move together.

- Make the charter's "How it is measured" column a strict list of AC ids that matches the criteria's Story column. Fixes: AC-4 goes under G-3. AC-20 moves to STORY-1. G-2's xfail text becomes AC-11. Decide where AC-25 belongs (STORY-1 or STORY-3). This is charter text, so it goes into ASK-20's diff.
- Add a new AC for G-8: every object in slide 23's "not JSON-like" list, when logged, gives one valid JSON line on stderr (v0's `log_weird_things.py` check). Add a clause to AC-1: no argument or return value on the span (DEC-26).
- Remove the overlaps. AC-11 keeps only its strict-xfail part (its plain class tests are inside AC-8). AC-1 says "named per AC-10". The instrument-twice clauses of AC-9 and AC-18 point at AC-6. AC-30 says "claims as in AC-12". Split AC-12: decoding and flattening claim STORY-13; the denylist and the raw base64 claim STORY-9.
- Cut the criteria footer to one line.
- Fold in OTW-19's criteria bullet: the `sqlalchemy.ext.asyncio` extension goes into AC-9, and the negative UTC offset into AC-18.

## Log

- 2026-10-18h (claude-code/2.1.287): closed: OTW-20: criteria aligned with the charter's measures (DEC-77)
