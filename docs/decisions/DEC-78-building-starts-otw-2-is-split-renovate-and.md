---
type: Decision
id: DEC-78
title: 'Building starts; OTW-2 is split: Renovate and auto-release move to a new item after the strict pins'
actor: owner
decided: 2026-10-18
decision_status: PROVISIONAL
tasks: [OTW-2, OTW-21]
tags: [process]
session: 2026-10-18j
body_sha: sha256:808c4d1a0224f22cf3ff393d2d7d847d38e3a9f41834d29edd521749238d050e
---

Owner, 2026-10-18j: *"I think the plan is mostly done and we can start building?"*

Asked how to start, given that OTW-2 bundles the test infrastructure (the `OTW_IMPL` adapter, the canaries, CI) with the self-acting automation (Renovate auto-merge, auto-release), that the automation has nothing to bump until OTW-13 adds the strict OTel pins, and that it needs setup on the owner's side (the Renovate app, a PyPI trusted publisher), the owner chose *"Split it (Recommended)"*, whose description read: *"Build the adapter, canaries and CI now, which is below the design-review threshold. Move Renovate and auto-release to a new item that depends on OTW-13; its design review gets written then, against real pins."*

What it settles:

1. Planning is done; building starts with OTW-2.
2. OTW-2 keeps the `OTW_IMPL` adapter, the upstream canaries, the remaining tests and the micro-benchmark it lists, and CI (DEC-38, DEC-56, DEC-63). Without the automation it is below the design-review threshold.
3. Renovate (DEC-54) and the auto-release of dependency-only merges (DEC-55) move to a new item that depends on OTW-13 (the strict pins, DEC-57). That item carries `review: [shipped, write-op]`, and its design review is written before it is built, against the real pins.
