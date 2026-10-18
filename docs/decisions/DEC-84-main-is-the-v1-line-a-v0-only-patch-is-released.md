---
type: Decision
id: DEC-84
title: main is the v1 line; a v0-only patch is released from a branch cut at the last v0 tag
actor: owner
decision_status: PROVISIONAL
tasks: [OTW-13, OTW-21]
tags: [release]
decided: 2026-10-19
session: 2026-10-18l
body_sha: sha256:349eb92bd2460d61c77108fa14acd6bc37cfddeeabae483b81f5ff5e554c72c1
---

Owner, 2026-10-19 (session 2026-10-18l), verbatim, asked "OTW-13 puts requires-python >=3.12 and strict OTel pins into pyproject on main. Once merged, any release cut from main (incl. a DEC-55 dependency-only v0 patch) carries them. How should main relate to v0 releases?", choosing between "Main is v1; v0 from a tag (Recommended): Merge OTW-13 to main now. A v0-only patch, if ever needed, is released from a branch cut at the last v0 release tag." and "Hold OTW-13 on a branch":

> Main is v1; v0 from a tag (Recommended)
