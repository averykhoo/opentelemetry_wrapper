---
type: Task
id: OTW-14
title: 'Workstream 11: typing'
brief: decorated objects keep their exact type under mypy
pri: NEXT
state: closed
deps: [OTW-2]
source: session 2026-10-18a
created: 2026-10-18
moved: 2026-10-18l
updated: 2026-10-18l
aliases: [WS11]
labels: [v1]
status: deprecated
closed: 2026-10-18l
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

- The decisions: [DEC-25](../docs/decisions/DEC-25-our-spans-come-from-the-otel-tracer-the-exposed.md), [DEC-48](../docs/decisions/DEC-48-property-on-top-otel-underneath-proposal-6.md); [the criteria](../docs/criteria.md)

## Log

- 2026-10-18l (claude-code/2.1.287): cf97eee (merged): tests/typing (46 reveal_type checks under mypy 2.4 for every decorated form, with- and async-with forms, instrument; wrong call is an arg-type error; sabotaged: Any return fails 21), overloads in _otel.py, [tool.mypy] in pyproject, mypy in the dev extra and requirements.txt so CI runs it. pyright skipped (needs Node). mypy on v1: 13 -> 10 errors (the rest in files other items own). Left: first CI run.
- 2026-10-18l (claude-code/2.1.287): closed: done in cf97eee: 46 reveal_type checks under mypy for every form; ran in CI run 39184909086 (38f04fe, all-extras jobs, 892 passed). pyright skipped (needs Node). @otel on a class returning it unchanged is OTW-6's.
