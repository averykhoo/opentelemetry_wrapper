---
type: Decision
id: DEC-64
title: Magic variable names through `varname`
actor: owner + agent
decided: 2026-10-07
session: 2026-10-18a
decision_status: REJECTED
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:130db7c18b1c4aadf69d061b6ac1029c023ee94b17c8eda78b31c5af448d6153
tags: [api]
reopen_if: '`co_qualname` leaves a naming case that `varname` would solve'
---

* [pip install varname](https://github.com/pwwang/python-varname) for magic varname extraction

| `varname` | drop; `co_qualname` covers most of the value |

*Imported at adoption (2026-10-18) from `PLAN.md` § `TODO.md` triage against the rebuild, `TODO.md` § todo, as committed at `24a0430`; now at `docs/archive/PLAN.md`, `docs/archive/TODO.md`.*
