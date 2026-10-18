---
type: Task
id: OTW-14
title: 'Workstream 11: typing'
brief: decorated objects keep their exact type under mypy
pri: LATER
state: open
deps: [OTW-2]
source: session 2026-10-18a
created: 2026-10-18
moved: 2026-10-18a
updated: 2026-10-18a
aliases: [WS11]
labels: [v1]
---

Criteria: AC-21. Decisions: DEC-25, DEC-48.

*Workstream 11 of the v1 design, verbatim from the pre-adoption `PLAN.md` (`docs/archive/PLAN.md`); there, "workstream n" is the task aliased `WSn` (OTW-1 lists them), "Decided" / "proposal n" / "Qn" are decisions (`docs/evidence/adoption-map-2026-10-18.md`), and "`HANDOFF.md`" is the old note in `docs/evidence/history-to-2026-10-18.md`.*

`@otel`, `@otel(...)`, `@otel` on a class and `otel.instrument(x)` keep the decorated object's type: `ParamSpec` /
overloads, so mypy and pyright see the original signature (and the original class). `with otel(...) as span` types
`span` as `trace.Span`. Proposal 6 covers `@property`.

**Done when:** `reveal_type` tests under mypy (and pyright, if available) for each form pass in CI.

## Traps

- mypy rejects any decorator above `@property` (DEC-48); pyright can't be installed here (it needs node).

## Read first

- The decisions: [DEC-25](../docs/decisions/index.md), [DEC-48](../docs/decisions/index.md); [the criteria](../docs/criteria.md)
