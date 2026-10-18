---
type: Decision
id: DEC-35
title: Pydantic 2 only, optional, never imported by us
actor: owner
decided: 2026-10-08
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:a5093a9addcc69170c45800b8dacf62e2b6a0bd4195d21bf94498b3e5f2b99e8
tags: [packaging]
---

- **Pydantic 2 only, optional, never imported by us.** Pydantic models can only exist if the app imported pydantic, so
  the encoder checks `sys.modules.get('pydantic')` when it meets an unknown object instead of importing it (~120 ms)
  at startup. If it's v2, use encoders for its real types (`isinstance` / type lookup, no duck typing), e.g.
  `BaseModel` -> `model_dump(mode="json")`. Pydantic 1 counts as absent (warn once); `pydantic.v1` models get the
  generic encoder. FastAPI 0.142 requires `pydantic>=2.9` anyway. v0 keeps supporting both.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
