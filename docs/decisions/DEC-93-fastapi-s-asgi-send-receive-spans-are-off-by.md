---
type: Decision
id: DEC-93
title: FastAPI's ASGI send/receive spans are off by default; an env var turns them on for debugging
decision_status: PROVISIONAL
actor: owner
tasks: [OTW-22, OTW-3, OTW-16]
tags: [api]
decided: 2026-10-19
session: 2026-10-19a
body_sha: sha256:38eb05da7200d2b2314fb91c5b7be928aa3c932ca22b2a42e8151c88543bff5f
---

Owner, 2026-10-19 (session 2026-10-19a). The session asked (multiple choice): "v1 drops FastAPI's per-request ASGI 'http send' / 'http receive' child spans (exclude_spans=['send','receive']) and keeps only the server span. v0 emitted them. The choice comes from PLAN.md workstream 1 ('verified: only the server span remains'), but no decision records it. Keep it?" The owner answered, verbatim:

> Env var? I can see why it might be needed for debugging in edge cases but in most situations it just adds noise

Read as: off by default (one server span per request), with an env var that turns the ASGI send/receive spans back on for debugging. The Upgrading guide notes the change from v0.
