---
type: Story
id: STORY-13
title: 'Telemetry carries the application context of each request: who called, and upstream latency'
actor: owner
story_status: live
goals: [G-13]
via: intake, session 2026-10-18f
date: 2026-10-18
body_sha: sha256:9e22e61bd13339965df79c88a9328c22d074c161520ac1c71d9e190f5431f1a6
---

Owner, 2026-10-18f, on the agent's proposed G-13 (application context): the agent had offered either folding G-7 (Kubernetes) into it or keeping G-7 and adding G-13 for request context. Verbatim: *"Okay with either, if you're not sure get an opinion from fable, but do add 13 in some shape or form, helpful is quite an important point"*

The goal is the owner's own, from their v0 talk (27 May 2024; summary in `docs/evidence/v0-talk-deck-2026-10-18.md`). Slide 17, "Design principles", verbatim:

- Helpful
  - Enriches spans with available application context

Slide 31, "Details: application context", verbatim:

- Extracts user context from the `X-UserInfo` OIDC request header
  - Decode base64, then parse JSON, then flatten the nested mapping
- Extracts upstream latency from response headers such as `X-Envoy-Upstream-Service-Time`
- Extracts the namespace and pod name if running in a Kubernetes deployment with the auto-mounted service account token
- Follows OTEL semantic conventions when injecting application context into spans

And the notes to slide 11, on why to instrument by hand, verbatim:

- This provides much more useful information (as much as you're willing to input)
  - E.g. user info of the person who called the endpoint
