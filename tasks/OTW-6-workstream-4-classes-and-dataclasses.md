---
type: Task
id: OTW-6
title: 'Workstream 4: classes and dataclasses'
brief: wrap cls.__dict__ at decoration time; never patch __getattribute__
pri: NEXT
state: open
deps: [OTW-10]
source: session 2026-10-18a
created: 2026-10-18
moved: 2026-10-18l
updated: 2026-10-18l
aliases: [WS4]
labels: [v1]
---

Criteria: AC-11. Decisions: DEC-42, DEC-48, DEC-53.

*Workstream 4 of the v1 design, verbatim from the pre-adoption `PLAN.md` (`docs/archive/PLAN.md`); there, "workstream n" is the task aliased `WSn` (OTW-1 lists them), "Decided" / "proposal n" / "Qn" are decisions (`docs/evidence/adoption-map-2026-10-18.md`), and "`HANDOFF.md`" is the old note in `docs/evidence/history-to-2026-10-18.md`.*

Port `_instrument_class` onto the new decorator, avoiding v0's cache-keying bug, the bound-method leak and the
per-property-access `inspect.getsourcelines` (use `fget.__code__.co_firstlineno`). Class-based context managers get
one `__enter__` -> `__exit__` span (workstream 7).

- Wrap the functions in `cls.__dict__` (plain functions and the `staticmethod` / `classmethod` / `property`
  descriptors) at decoration time instead of patching `__getattribute__`, which is the root of v0's cache-keying bug,
  the leak and the per-access cost. Inherited methods: wrap the base's function into the subclass's `__dict__`.
- Which dunders, the properties opt-in and the per-method opt-out: proposal 11.
- `otel(LibraryClass)` modifies that class for the whole process (say so in the README). C types and classes that
  can't be modified are unsupported targets: returned unchanged, one warning.

**Done when:** the plain `tests/v0` class and dataclass tests pass under `OTW_IMPL=v1`, and the class-related strict
xfails (first-class-only spans, nested spans through instances, the leak) pass.

## Traps

- v0 keys its `__getattribute__` cache on `object.__getattribute__`, so only the first class gets method spans, and it leaks instances through cached bound methods.

## Read first

- The decisions: [DEC-42](../docs/decisions/DEC-42-global-dataclass-instrumentation-is-dropped.md), [DEC-48](../docs/decisions/DEC-48-property-on-top-otel-underneath-proposal-6.md), [DEC-53](../docs/decisions/DEC-53-classes-span-methods-and-constructors-selected.md); [the criteria](../docs/criteria.md)
- [v0 lessons](../docs/evidence/v0-lessons-2026-10-07.md)
