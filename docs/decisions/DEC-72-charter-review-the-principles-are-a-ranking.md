---
type: Decision
id: DEC-72
title: 'Charter review: the principles are a ranking; never crash first, no secrets last'
actor: owner
decision_status: PROVISIONAL
refs: [DEC-41, DEC-57, DEC-54]
decided: 2026-10-18
session: 2026-10-18e
body_sha: sha256:a0c6249eef6da49ef529bcda2229821cd306858007034cf175e17c92fde5948e
---

Owner, reviewing the charter (`docs/charter.md`, reconstructed at adoption) in session 2026-10-18e, answering the
agent's review points: (1) the "higher goal wins" rule that PLAN.md never stated, with the example of a scrubbing
failure on export; (2) where the unranked G-9 (no secrets by default) and G-10 (upgrades don't break users) go;
(3) the anti-goals list; (4) the mandates. Verbatim, two messages:

*"Higher goal wins is probably not a bad idea, and can go into the context engine feedback too*

*In that specific case I think never crash should win, followed by telemetry output, and we should document that*

*No secrets as in we scrub secrets? That can go right at the bottom*

*Upgrades not breaking is also near the bottom, versions should be pinned, and we'll try to use semver to handle compat*

*Not all of those are anti goals but they're not in the current plan yes. The type checking is helpful to keep around
but we'll leave it in v0 for now"*

*"I don't read ci - yes that's why every push needs a babysitter"*

What it settles, as the agent applies it to the charter:

- The principles are a ranking: when two goals pull apart, the higher one wins.
- Never crash outranks telemetry output, which outranks no secrets; the charter documents the scrubbing-failure case.
- G-9 (no secrets by default: no arguments on spans, the claim denylist, scrubbing) ranks last; G-10 (upgrades don't
  break users) just above it. Versions stay pinned (DEC-57), and releases try to follow semver to signal compatibility.
- The anti-goals list becomes "not in the v1.0 plan": not all of it is ruled out for good. `type_checking.py` stays in
  v0 (as DEC-41).
- The mandate "automation must act by itself" stands, and is why every push gets a CI watcher.

## Amendments

- **2026-10-18e (claude-code/2.1.287):** **2026-10-18e, owner:** after the agent explained that G-9 is more than scrubbing (no arguments on spans, the `x-userinfo` claim denylist, then scrubbing as defence in depth), the owner: *"Oh then no secrets can bump up a little higher then"*. The agent reads "a little higher" as one place: G-9 moves above G-10, to 8th, and G-10 is last.

- **2026-10-18e (claude-code/2.1.287):** **2026-10-18e, owner**, after the charter review, on its source: *"Anc can you check the ppt which should be somewhere in this repo? That should give the best description of what this repo is meant to do"*. The deck is the v0 talk, `OpenTelemetry-Instrumentation-v6.pptx` (27 May 2024). It is not tracked: it sits in the gitignored `.scratch/`, beside its transcript. The agent compared it with the charter and put the gaps to the owner.

- **2026-10-18e (claude-code/2.1.287):** **2026-10-18e, owner**, on the deck's order (slide 17 puts "Safe: never crashes the running application" first; the charter had idempotency first): *"Okay never crash should be top. As in, it should never be the cause of an instrumented app crashing. Even if all else fails it should just not output spans, it shouldn't cause the instrumented app to fail. But I guess we also do need a way to debug the otel wrapper so maybe it should be allowed to output something if it was about to crash?"*

  Applied: never crash (G-3) is ranked first and idempotency (G-2) second. The fallback when all else fails is no spans, never a failure in the app. Whether, and how, the wrapper may report its own failure at runtime is an open question (ASK-19). Today G-4 and DEC-49 allow warnings only at startup.
