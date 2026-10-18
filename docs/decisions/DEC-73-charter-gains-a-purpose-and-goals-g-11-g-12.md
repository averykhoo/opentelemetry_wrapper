---
type: Decision
id: DEC-73
title: Charter gains a purpose and goals G-11, G-12 from the v0 talk; only a cleaned deck summary is committed
actor: owner
decision_status: BUILT
refs: [DEC-72]
decided: 2026-10-18
session: 2026-10-18e
body_sha: sha256:7d71ce2646d8da2c136ae778363fd5012f1c6d8588d6882bf9ccf821d8577208
---

Owner, 2026-10-18e, answering the agent's comparison of the v0 talk deck (`OpenTelemetry-Instrumentation-v6.pptx`, 27 May 2024, the owner's own talk, which they called "the best description of what this repo is meant to do") with the charter. The agent had proposed adding a purpose statement and the goals the deck states but the charter lacks: "simple, idiomatic, succinct and pretty" (G-11), "reasonable documented defaults" (G-12) and "application context" (G-13). It had also proposed committing a cleaned summary of the deck to `docs/evidence/` rather than the deck, which carries internal details and would go into a public repo. Verbatim:

*"And I agree with your proposal adding the purpose, the simple idiomatic succint pretty goals, sensible defaults, and yes only commit the cleaned version"*

Applied: the charter gains a `## Purpose` section and goals G-11 and G-12 (STORY-11, STORY-12). The deck itself stays out of git; a cleaned summary, with no team, project, host or user names, is committed as `docs/evidence/v0-talk-deck-2026-10-18.md`. G-13 (application context) was not named in the answer, so it is not added.
