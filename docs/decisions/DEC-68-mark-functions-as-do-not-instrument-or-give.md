---
type: Decision
id: DEC-68
title: Mark functions as do-not-instrument, or give them a sampling ratio
actor: owner
decided: 2022-09-27
session: 2026-10-18a
decision_status: REJECTED
narrowed_by: [DEC-53]
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:3feed599e2341c74a78bf900bd5c67301db62a373199c1d7b601591163330570
tags: [api]
reopen_if: per-function sampling becomes possible without breaking root-span sampling (DEC-23)
---

* ~~somehow mark functions/endpoints as do-not-instrument, for extremely spammy functions? specify a sampling ratio?~~
    * ~~the nearest sampling ratio should overwrite, but idk how to do that~~
    * ~~how to integrate with the instrumentors? seems impossible?~~

*Imported at adoption (2026-10-18) from `TODO.md` § won't do, as committed at `24a0430`; now at `docs/archive/TODO.md`.*

## Amendments

- **2026-10-18a (claude-code/2.1.287):** imported heading note: **relaxed by DEC-53**
