---
type: Task
id: OTW-1
title: 'v1: rebuild on the plain OpenTelemetry SDK (epic)'
brief: 'closes last: every workstream task in deps closed, AC-8 green, v0 entry points aliased'
pri: NEXT
state: open
deps: [OTW-2, OTW-3, OTW-4, OTW-5, OTW-6, OTW-7, OTW-8, OTW-9, OTW-10, OTW-11, OTW-12, OTW-13, OTW-14, OTW-16]
source: session 2026-10-18a
created: 2026-10-18
moved: 2026-10-18a
updated: 2026-10-18a
---

Epic: everything v1.0 needs, as one checklist (G-1). v1 rebuilds the wrapper directly on the OpenTelemetry SDK and
the contrib instrumentors (DEC-15), adding only what neither provides. This item closes last: its `deps` are the
tasks below.

**Rollout** (DEC-37, DEC-38): v1 ships beside v0 in the same package until `tests/v0` passes under `OTW_IMPL=v1`
(AC-8); then v1 becomes the default and v0 is deleted, with v0's entry points kept as thin deprecated aliases for one
release. The Python floor rises to 3.12 in that release, as a minor-version bump; the v0 deletion is 1.0.0 (DEC-44).

**Order** (from the design): 0 -> 1 (configure, decorator, `with otel:`) -> 3 -> 7 -> 4 -> 5 -> 2 -> 8 -> 9, with 6
in parallel (pure OTel, testable alone) and 10-11 alongside 1. 5b (scrubbing) feeds 1's exporter wrappers, 5 and 6.

| Workstream | Task | Done when (criteria) |
|---|---|---|
| 0. Tests, canaries, CI, Renovate, auto-release | OTW-2 | AC-23, AC-24; `OTW_IMPL=v1` runs; CI on push |
| 1. Configure, idempotent never-crash wrappers | OTW-3 | AC-1 to AC-7, AC-22; plain v0 decorator tests under v1 |
| 2. SQLAlchemy | OTW-4 | AC-9 |
| 3. Introspection | OTW-5 | AC-10 |
| 4. Classes and dataclasses | OTW-6 | AC-11 |
| 5. Headers | OTW-7 | AC-12 |
| 5b. Scrubbing | OTW-8 | AC-13 |
| 6. Resource detectors | OTW-9 | AC-14 to AC-16 |
| 7. Generators and context managers | OTW-10 | AC-17 |
| 8. Logging | OTW-11 | AC-18 |
| 9. Metrics: push and scrape | OTW-12 | AC-19 |
| 10. Packaging | OTW-13 | AC-20 |
| 11. Typing | OTW-14 | AC-21 |
| Docs: `README_v1.md` becomes `README.md`, Upgrading guide | OTW-16 | the README matches the decisions |

**v1.0 is done when** every task above is closed, `tests/v0`'s plain tests pass under `OTW_IMPL=v1` (AC-8), v0's
entry points are deprecated aliases over v1, and a release is published (`docs/runbooks/release.md`, `CLAUDE.md` §
Release).

Not part of v1.0: OTW-15 (unpinning sqlalchemy, upstream-driven), OTW-17 and OTW-18 (SOMEDAY).

## Traps

- The board shows this item blocked until its last dep closes; that is by design (no parent field yet).

## Read first

- [The decisions index](../docs/decisions/index.md) and [the criteria](../docs/criteria.md)
- [Adoption map](../docs/evidence/adoption-map-2026-10-18.md): where each part of the pre-adoption plan went
