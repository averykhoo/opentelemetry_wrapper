---
type: Task
id: OTW-19
title: 'Migration verification leftovers: charter tie-break, two uncovered v0 bugs, adoption-map errata'
brief: What the 2026-10-18c verification confirmed but left for the owner or a correction
pri: LATER
state: open
deps: []
source: session 2026-10-18c
created: 2026-10-18
moved: 2026-10-18c
updated: 2026-10-18e
---

The 2026-10-18c verification (five independent checkers plus a skeptic each) found no lost content and no blocker; these confirmed findings remain.

- **Charter:** `docs/charter.md` states "when two goals pull apart, the higher one wins". PLAN.md's principles are a plain numbered list with no ranking; settle it in the owner's charter review.
- **Criteria:** the adoption map says v1 fixes the missing `sqlalchemy.ext.asyncio` extension under OTW-4/AC-9 and the negative UTC offset under OTW-11, but no AC's text covers either (only AC-8's "plain tests pass" does implicitly). Add them to AC-9 and AC-18, or correct the claim.
- **Adoption map (frozen, so a correction rather than an edit):** the old HANDOFF's "Also pinned" bullet (the `/metrics` regex search, `instrument_decorate(42)`, the second `instrument_all()`, generator spans, v0's own spans) has no row; the `/metrics` path default is cited to DEC-59 but is stated in OTW-12; "moved unchanged" omits the 2-line ARCHIVED header; `docs/archive/TODO.md`'s link to `next_version_intended_usage.py` broke with the move.
- **Nits:** DEC-65/67/68's `decided` dates are inferred from git history; AC-18, AC-20 and AC-21 trim a CI clause each from their workstream's Done when; OTW-14 is LATER while OTW-13 (both "alongside 1") is NEXT.

## Log

- 2026-10-18e (claude-code/2.1.287): Charter bullet settled in the owner's review (DEC-72): the owner kept 'the higher goal wins' as a real ranking, never crash first. The other bullets (criteria, adoption-map errata, nits) remain.
