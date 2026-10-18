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
