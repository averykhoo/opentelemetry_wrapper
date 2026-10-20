---
type: Decision
id: DEC-97
title: OTW-21 waits until after v1 and ships push-only first; publishing is turned on after a couple of correct pushes
actor: owner
decision_status: PROVISIONAL
tasks: [OTW-21]
tags: [release, process]
decided: 2026-10-20
session: 2026-10-20a
body_sha: sha256:1766229cad73b586b4970b9cf79127329dab9567f06eeea9c5073f7141ed36fd
---

Owner, 2026-10-20 (session 2026-10-20a), verbatim, on OTW-21 (Renovate auto-merge of OTel bumps and auto-release of dependency-only merges), which the session recommended doing after the first v1 release:

> 3 - we'll do that later, after v1, and we'll start with just a push without publish, then turn on publish after we've seen it push correctly a couple of times

Read as: OTW-21 waits until after the v1 release. It is built in two stages: first the automation runs up to the push (the auto-merged bump and the release commit or tag) without publishing to PyPI; publishing is turned on only after the owner has seen it push correctly a couple of times.
