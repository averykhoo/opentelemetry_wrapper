---
type: Decision
id: DEC-56
title: 'CI: GitHub Actions on push and pull requests, Python 3.12-3.14, with and without extras'
actor: owner
decided: 2026-10-18
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:91cab672a6ad72f6302e701a08d89e7f85a7d8645d5d873fe15e68e6643c3722
tags: [testing]
tasks: [OTW-2]
---

- **CI:** GitHub Actions on push and on pull requests (none yet; `.github/workflows/` doesn't exist). Kept
  (decided 2026-10-18): Renovate's auto-merge depends on it, and whoever pushes watches the run. Matrix: Python 3.12 / 3.13 / 3.14 × with and
  without the optional extras, so "optional at call time" is actually exercised. Keep the steps in a script so the
  workflow file stays thin.

*Imported at adoption (2026-10-18) from `PLAN.md` § Workstreams § 0. Tests, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
