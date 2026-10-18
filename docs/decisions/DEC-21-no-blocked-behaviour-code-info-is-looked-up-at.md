---
type: Decision
id: DEC-21
title: 'No "blocked" behaviour: code info is looked up at run time from the target'
actor: owner
decided: 2026-10-08
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:db51cc22ff57cd77212de6f3542cbc84f2513536d2e0fe9bd8cf86bfdb6814ba
tags: [api]
---

- **No "blocked" behaviour.** It existed because code info cached on the object could be reused for the wrong target.
  Instead, code info is looked up at run time from the target: the decorated function's code object at decoration
  time, the caller's frame (`f_code`, `f_lineno`) at `__enter__`, cached by code object + line, never stored on `otel`.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
