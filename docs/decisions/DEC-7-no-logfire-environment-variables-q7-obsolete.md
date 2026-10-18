---
type: Decision
id: DEC-7
title: No `LOGFIRE_*` environment variables (Q7, obsolete with logfire)
actor: owner
decided: 2026-10-17
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
aliases: [Q-7]
body_sha: sha256:e678cf577d5ba875df698ce31461325c7b4044ca63db4f1e7ba3c7b458532ad8
tags: [config]
---

- **Q6, Q7.** *Obsolete* (logfire's `add_baggage_to_attributes` and `LOGFIRE_*` env vars). Baggage is never copied
  onto spans.

*Imported at adoption (2026-10-18) from `PLAN.md` § Questions for later, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
