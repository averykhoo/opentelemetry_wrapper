---
type: Decision
id: DEC-31
title: Stable semconv `code.*` keys everywhere
actor: owner
decided: 2026-10-08
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:6d3f658ecd19111a7a55eb0a8d7e213877d6a4313c814093bb10746da960a836
tags: [telemetry]
---

- **Stable semconv `code.*` keys** everywhere (workstream 3).

The `CodeInfo` rewrite in `HANDOFF.md`. Emit stable `code.*` keys, using the constants in
`opentelemetry.semconv.attributes.code_attributes` rather than string literals; put extras (wrapper chain,
`is_class`, end line) under our own prefix, e.g. `opentelemetry_wrapper.code.*`. Auto-name `with otel:` blocks from
the call site (see proposal 5 for the naming).

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, `PLAN.md` § Workstreams § 3. Introspection, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
