---
type: Decision
id: DEC-49
title: One `OtelWrapperWarning` through `warnings.warn`, on startup paths only (proposal 7)
actor: owner + agent
decided: 2026-10-08
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:83f920a010e392ac6eb3e209e57cf7d10969accf2633554820cfb43925212e4f
tags: [api]
---

7. **Warning channel** (F8): one `OtelWrapperWarning(UserWarning)` via `warnings.warn(..., stacklevel=2)`, only on
   startup paths (decoration, `instrument`, `configure`, env var parsing), never through `logging` and never per call.
   The default filter shows each message once per call site, and an error filter in CI turns misuse into a test
   failure without ever crashing production. The CI recipe is pytest's `filterwarnings =
   error::opentelemetry_wrapper.OtelWrapperWarning` (ini) or `pytest -W error::...`, **not** `python -W
   error::opentelemetry_wrapper.OtelWrapperWarning` / `PYTHONWARNINGS=...`: *verified* (2026-10-18), the interpreter
   parses `-W` before `site` adds site-packages, so a category from an installed package prints `Invalid -W option
   ignored` and the run exits 0. *(review)* Call `warnings.warn` outside our own `try`/`except` blocks so an
   error-filtered warning isn't swallowed, and only once state is consistent (collect warnings during `configure` /
   decoration and emit them at the end), so an error filter can't leave configuration half-built. Whether
   `PYTHONWARNINGS=error` in production may crash at startup is Q8.

*Imported at adoption (2026-10-18) from `PLAN.md` § Proposals, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
