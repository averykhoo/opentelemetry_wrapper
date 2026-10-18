---
type: Decision
id: DEC-76
title: G-13 added for request context; G-7 stays; G-13 leads the Helpful tier
actor: owner + agent
decision_status: BUILT
refs: [DEC-73, DEC-2]
tasks: [OTW-7]
decided: 2026-10-18
session: 2026-10-18f
body_sha: sha256:f66f6fc4d9d6477bb0761396f7375dc726b1bae07170f040624d0c872a13fdb2
---

Owner, 2026-10-18f, leaving the shape to the agent: *"Okay with either, if you're not sure get an opinion from fable, but do add 13 in some shape or form, helpful is quite an important point"*

The agent's choice of shape (no second opinion: the agent was sure, for the reason below):

- **G-7 stays; G-13 is added** for the context that comes with each request: the calling user (`x-userinfo`, flattened, with the claim denylist) and upstream latency (`X-Envoy-Upstream-Service-Time` and the like), under OTel semantic-convention names. G-7 keeps where the service runs (Kubernetes). Together they are the deck's "Enriches spans with available application context" (STORY-13).
- **Why not fold G-7 into G-13:** a story's goals cannot be rewritten, so folding would mean retiring STORY-7, which the owner confirmed the same day, and moving AC-14 and AC-16. That is churn without a change in intent.
- **Rank:** first of the deck's "Helpful" tier, 6th, above introspection (G-5). The owner called helpful "quite an important point", and this is the context that makes manual instrumentation worth more than auto-instrumentation (slide 11).
- **Measured by** AC-12 (the `x-userinfo` claims) and a new AC-30 (both kinds of context recorded with no configuration). Built in OTW-7 (headers).
