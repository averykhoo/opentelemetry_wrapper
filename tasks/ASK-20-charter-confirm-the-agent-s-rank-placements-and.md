---
type: Question
id: ASK-20
title: "Charter: confirm the agent's rank placements and the parsimony trims?"
brief: Agent rank placements and parsimony trims need the owner's yes before the charter changes
pri: NEXT
state: open
deps: []
source: session 2026-10-18g
created: 2026-10-18
moved: 2026-10-18g
updated: 2026-10-18g
last_asked: 2026-10-18g
---

Owner, 2026-10-18g: *"check if there's anything I haven't accepted yet or if there are any open decisions and bring them to me to think through, but make recommendations"*. Raised in chat the same session. The review behind items 3 to 6 is `docs/evidence/parsimony-review-2026-10-18.md`.

Nothing else is open: no open questions, and the one DEFERRED decision (DEC-61, un-instrumentation) is the owner's own parking. The 53 PROVISIONAL decisions are signed off and unbuilt, not open.

1. **The agent's rank placements.** G-11 (simple) 4th, G-12 (defaults) 5th, G-13 (context) 6th, and "a little higher" read as G-9 one place up (11th). *Recommended:* confirm as they stand: they follow the deck's tiers (Safe, then Unsurprising, then Helpful).
2. **The middle step of the scrubbing example.** "The telemetry still goes out" is no ranked goal (G-1 is unranked), so the ranking alone does not decide it. *Recommended:* write it into G-3 as "fail small": when a failure can be confined to one value or one span, only that is dropped and the rest still goes out. This is DEC-74's rule, made general.
3. **G-1 slimmed to what is its own.** It keeps: builds on the SDK and the contrib instrumentors; the `otel` decorator and context manager; instrumenting everything at once; and Prometheus. It is measured by the nine STORY-1 criteria. *Recommended:* yes.
4. **A charter trim.** State DEC-75 once (in G-4). Cut the scrubbing example to one line that points at DEC-74 and AC-13. Drop the provenance paragraph, "the order is PLAN.md's", the pins repeated in principle 12, DEC-26 repeated in "not in the plan", and the purpose's two sentences that restate G-11 and AC-28. Move the claim denylist from G-13 to G-9 alone. *Recommended:* yes. The agent drafts the diff and the owner approves it; no meaning changes.
5. **STORY-9 and STORY-10 copy decisions** (DEC-58; DEC-37 plus DEC-54, truncated). *Recommended:* keep both (confirmed today) and add an amendment naming those decisions as the authority. Do not retire them.
6. **Deck principles the charter lacks.** *Recommended:* G-2 becomes "hard to use incorrectly: idempotent, and sync and async alike", which is slide 17's "Hard to use incorrectly" and slide 23's "Idempotent, async-compatible". G-8 cites DEC-34 for "human-readable a close second": `OTEL_TRACES_EXPORTER=console` locally, and no pretty console in 1.0. Alternatively, say whether a human-readable console is wanted after all.
