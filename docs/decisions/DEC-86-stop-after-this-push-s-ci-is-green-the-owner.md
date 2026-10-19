---
type: Decision
id: DEC-86
title: Stop after this push's CI is green; the owner clears context before more work. A 7-day GitHub token for CI logs lives in .scratch
actor: owner
decision_status: PROVISIONAL
tasks: [OTW-10]
tags: [process]
decided: 2026-10-19
session: 2026-10-18l
body_sha: sha256:572bd00821ff493bd8180e3f0daf119d4642d5d13d671447daf13d12dc8b2dcc
---

Owner, 2026-10-19 (session 2026-10-18l), verbatim:

> Okay to push

(answering whether to push main at 38f04fe for CI to confirm OTW-13 and OTW-14), then, while the push ran:

> Don't continue work after this, just get the ci green then stop, I'll clear context before continuing

Earlier the same session, asked how to read the failing CI log (the global CLAUDE.md's token is a GitLab token GitHub rejects), the owner supplied a GitHub token with these words (the token itself redacted here; it is in the gitignored .scratch/gh_token, never committed):

> ghp_[REDACTED] - this will last 7 days so just dump it in .scratch for now
