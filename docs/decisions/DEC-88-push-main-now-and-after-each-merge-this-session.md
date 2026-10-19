---
type: Decision
id: DEC-88
title: Push main now and after each merge this session, gated and CI-watched, no release
decision_status: PROVISIONAL
actor: owner
tasks: [OTW-1]
tags: [process]
decided: 2026-10-19
session: 2026-10-19a
body_sha: sha256:583568d6974aa07c146f2322d7a23a4a304591c74cc210ad3a875ebe60a203d5
---

Owner, 2026-10-19 (session 2026-10-19a), asked "May I push main? It holds 7 record-only commits from last session, DEC-87 and the merged OTW-10 (gate green, 915 passed). A CI watcher will run on the push, and nothing will be released.", chose, verbatim:

> Push now

whose option read: "Push main now and after each later merge this session, gating every time and watching CI each time."
