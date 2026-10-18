---
type: Decision
id: DEC-38
title: '"Proven safe" is one command: `tests/v0` under `OTW_IMPL=v0|v1`'
actor: owner
decided: 2026-10-08
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:7b14c5d37dba3899f89ce3913bac5688d071838f4ddfddf4204ce9dc1c34a4ff
tags: [testing]
---

- **"Proven safe" is one command.** The v0 tests call v0 names directly, so the harness gets a small adapter
  (`decorate` / `instrument_app` / `instrument_engine` / `setup`) selected by `OTW_IMPL=v0|v1`; plain tests must pass
  under both, `v0_specific` tests are v0-only. Commit the suite first so the baseline is pinned.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
