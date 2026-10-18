---
type: Decision
id: DEC-44
title: v1 requires Python 3.12 or later
actor: owner
decided: 2026-10-08
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:ace435341851b9c5c09b7ee4bb4f5fc7f18176be6e263f56daa9dec564382c02
tags: [packaging]
tasks: [OTW-13]
---

one-line JSON logs and Prometheus. Python floor: **3.12** (the SDK itself needs >= 3.10).

- `requires-python = ">=3.12"` (v0's `">3.8.0"` also excluded 3.8.0 by accident). Side-by-side means v0 users get the
  3.12 floor in that release: make it a minor-version bump with a clear note, and the v0 deletion 1.0.0.

*Imported at adoption (2026-10-18) from `PLAN.md` § Goal, `PLAN.md` § Workstreams § 10. Packaging, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
