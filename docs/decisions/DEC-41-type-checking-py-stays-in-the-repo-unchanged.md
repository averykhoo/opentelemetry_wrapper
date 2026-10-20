---
type: Decision
id: DEC-41
title: "`type_checking.py` stays in the repo, unchanged, outside v1's API"
actor: owner
decided: 2026-10-08
session: 2026-10-18a
decision_status: BUILT
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:35348178fdfa6b205330da53251ab37e70ce9ba9e9a305dcc5713c53322f5285
tags: [api]
tasks: [OTW-18]
---

- **`type_checking.py` stays in the repo, unchanged** (it works), but v1 doesn't import or export it, as v0 already
  doesn't.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

## Amendments

- **2026-10-20a (claude-code/2.1.287):** 2026-10-20 (session 2026-10-20a): v0 was deleted at 1.0.0 (DEC-96, OTW-25), and opentelemetry_wrapper/v0/utils/type_checking.py with it; it is in git history and at tag v0.1.25. The charter line that says it stays in v0 is the owner's to update.
