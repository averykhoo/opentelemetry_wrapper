---
type: Decision
id: DEC-60
title: Auto-tracing a user's package (`otel.instrument(my_package)`)
actor: owner
decided: 2026-10-08
session: 2026-10-18a
decision_status: REJECTED
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:84eacb15b48dbfcab2d55478d65eaf522f7ba002118f7e7f401eb9fb89e00dc9
tags: [api]
reopen_if: auto-tracing can be installed without depending on import order
---

- Auto-tracing a user's package (`otel.instrument(my_package)`, i.e. logfire's `install_auto_tracing`): it has to run
  before the package is imported, against "import order doesn't matter". A module that isn't a known integration is
  an unsupported target: returned unchanged, one warning.

*Imported at adoption (2026-10-18) from `PLAN.md` § Non-goals, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
