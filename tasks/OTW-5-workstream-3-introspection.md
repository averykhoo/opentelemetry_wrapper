---
type: Task
id: OTW-5
title: 'Workstream 3: introspection'
brief: read name, file and line from the same object; no source files, no strong references
pri: LATER
state: open
deps: [OTW-3]
source: session 2026-10-18a
created: 2026-10-18
moved: 2026-10-18a
updated: 2026-10-18a
aliases: [WS3]
labels: [v1]
---

Criteria: AC-10. Decisions: DEC-21, DEC-31, DEC-47.

*Workstream 3 of the v1 design, verbatim from the pre-adoption `PLAN.md` (`docs/archive/PLAN.md`); there, "workstream n" is the task aliased `WSn` (OTW-1 lists them), "Decided" / "proposal n" / "Qn" are decisions (`docs/evidence/adoption-map-2026-10-18.md`), and "`HANDOFF.md`" is the old note in `docs/evidence/history-to-2026-10-18.md`.*

The `CodeInfo` rewrite in `HANDOFF.md`. Emit stable `code.*` keys, using the constants in
`opentelemetry.semconv.attributes.code_attributes` rather than string literals; put extras (wrapper chain,
`is_class`, end line) under our own prefix, e.g. `opentelemetry_wrapper.code.*`. Auto-name `with otel:` blocks from
the call site (see proposal 5 for the naming).

**Done when:** every row of the Evidence introspection table gives the right name, file and line (including callable
instances and decorators that set `__wrapped__` without `@wraps`); no source needed; no strong references to user
objects.

## Traps

- v0's `CodeInfo` takes the name from the wrapper but the line from the wrapped function (`inspect.unwrap` inside `getsourcelines`): the bug to avoid.

## Read first

- The decisions: [DEC-21](../docs/decisions/DEC-21-no-blocked-behaviour-code-info-is-looked-up-at.md), [DEC-31](../docs/decisions/DEC-31-stable-semconv-code-keys-everywhere.md), [DEC-47](../docs/decisions/DEC-47-unnamed-with-otel-blocks-are-named-after-the.md); [the criteria](../docs/criteria.md)
- [v1 design evidence](../docs/evidence/v1-design-evidence-2026-10-18.md): Introspection
- [history](../docs/evidence/history-to-2026-10-18.md): the old `HANDOFF.md` § TODO, `CodeInfo` bugs
