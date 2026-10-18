---
type: Decision
id: DEC-66
title: "No sanitizer: just don't log secrets"
actor: owner
decided: 2023-06-05
session: 2026-10-18a
decision_status: SUPERSEDED
status: deprecated
superseded_by: [DEC-58]
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:3d4eb1ac552c7634fd3e0e6e8e6ae0b7b4e9268bd3bf1b81d4fedd92300f388e
tags: [scrubbing]
---

* ~~add a (regex-based?) sanitizer to erase strings/patterns from log output~~ (just don't log secrets)

*Imported at adoption (2026-10-18) from `TODO.md` § won't do, as committed at `24a0430`; now at `docs/archive/TODO.md`.*

## Amendments

- **2026-10-18a (claude-code/2.1.287):** imported heading note: **SUPERSEDED by DEC-58**
