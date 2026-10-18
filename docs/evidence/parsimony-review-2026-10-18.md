# Parsimony review of the charter, stories and criteria

FROZEN 2026-10-18 (session 2026-10-18g). At the owner's request (*"get a subagent to check that everything you've read
is parsimonious"*), one subagent read `docs/charter.md`, STORY-1 to STORY-13, `docs/criteria.md`, the cleaned deck
summary (`docs/evidence/v0-talk-deck-2026-10-18.md`), the deck transcript and the decisions they cite, and asked: is
this the smallest set that says everything needed, with nothing said twice and nothing unsupported? The session
checked findings 2 and 7 against the files. The owner's choices are ASK-20; the agent's fixes are OTW-20.

**Verdict:** close to parsimonious. The goal set is sound and every goal is supported by the deck or the owner's
decisions, but several things are said two or three times, the charter carries provenance and mechanism, and three
measurement links are wrong or missing.

## Findings

1. **G-1 repeats the rest of the charter.** Only "builds on the OTel SDK and contrib instrumentors", the `otel`
   decorator / context manager and Prometheus are its own; the rest restates G-2, G-3, G-5 to G-9 and G-13. Its measure
   ("OTW-1 closes ... `README_v1.md` works") is circular and overlaps AC-28, while the nine criteria that claim STORY-1
   (AC-1, 2, 3, 5, 9, 17, 19, 21, 26) appear in no goal's measure. Owner.
2. **The charter's "How it is measured" column disagrees with the criteria's Story column.** AC-4 claims STORY-3 but
   is not under G-3; AC-20 claims STORY-10 but is not under G-10 (it is about install and extras, so STORY-1 fits
   better); G-2's extra measure is AC-11's text; AC-25 (DEC-3's exception-status table) is how exceptions are
   recorded rather than never crashing. Agent drafts, owner confirms (charter text).
3. **Unmeasured goal content.** G-8's "JSON-encode anything, one line" has no criterion (AC-18 tests id correlation
   and handler counts); it was the deck's showcase (slides 23, 30). G-9's "no arguments on spans" (DEC-26) has none
   either. Agent.
4. **Criteria that overlap.** AC-11's "plain class tests pass under v1" is inside AC-8; AC-1's naming clause is AC-10;
   the instrument-twice clauses of AC-9 and AC-18 are AC-6; AC-30's `x-userinfo` half is AC-12. Agent.
5. **DEC-75 is stated twice in the charter, with mechanism:** in G-4 and in principle 1. Owner.
6. **The scrubbing-failure example is told four times** (charter, DEC-74, AC-13, DEC-58). Its middle tier, "the
   telemetry still goes out", is no ranked goal (G-1 is unranked), so the ranking alone cannot settle the example.
   Owner.
7. **G-11 and G-12 at 4th and 5th, and G-13 at 6th, are the agent's placements** (the charter says so); no owner words
   confirm them. Owner.
8. **The `x-userinfo` claim denylist is in both G-9 and G-13;** it is a secrets control. Owner (G-13's text), agent
   (splitting AC-12 between STORY-9 and STORY-13).
9. **Provenance and process inside the charter:** the reconstruction paragraph, "the order is PLAN.md's ...", the
   mandate pointing at `CLAUDE.md`, principle 12's pins (the first mandate), and the purpose's two sentences that
   restate G-11 and AC-28. Owner. The criteria footer is provenance too. Agent.
10. **STORY-9 and STORY-10 are copies of decisions:** STORY-9 is DEC-58's paragraph; STORY-10 is DEC-37 plus DEC-54,
    cut off mid-sentence. Owner (retire and restate) or agent (an amendment naming the decisions as the authority).
11. **"No function arguments or return values" (DEC-26) is in both G-9 and "Not in the v1.0 plan".** Owner.

## Deck principles the charter misses

From slide 17: "Hard to use incorrectly" (the Safe tier's second line) survives only as idempotency (G-2);
"human-readable a close second" is dropped from G-8 without a reason (DEC-34, no pretty console in 1.0, would be it);
async compatibility (slide 23, "Idempotent, async-compatible") is in AC-1 but in no goal. Not scope creep: one owner
question.
