---
type: Decision
id: DEC-37
title: 'Rollout: v1 ships beside v0, becomes the default, then v0 is deleted after one release of aliases'
actor: owner
decided: 2026-10-08
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:5c0cb46732461eb14abb92aaf570c459071d661faf140ae0e1fc77c0b98772e0
tags: [process]
---

- **Rollout: side by side.** v1 ships next to v0 in the same package until it's proven safe against `tests/v0`, then
  becomes the default and v0 is deleted. For one release after that, v0's entry points (`instrument_decorate`,
  `instrument_all`, `instrument_fastapi_app`, `instrument_sqlalchemy_engine`, ...) stay as thin deprecated aliases
  over v1, so users can migrate incrementally.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
