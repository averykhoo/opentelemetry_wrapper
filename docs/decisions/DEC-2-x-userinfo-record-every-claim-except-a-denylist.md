---
type: Decision
id: DEC-2
title: '`x-userinfo`: record every claim except a denylist (Q2)'
actor: owner
decided: 2026-10-07
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
aliases: [Q-2]
body_sha: sha256:761df033b6e3d45ff31f8089b2cc285584f1cde1210bd17c9ffd4e69f56a380a
tags: [headers]
---

- **Q2. `x-userinfo` by default.** *Decided 2026-10-07*, see workstream 5: capture every claim except a denylist.
  Default denylist confirmed 2026-10-18 (`*token*,at_hash,c_hash,nonce,session_state,sid`; personal data captured
  unless added).

**Which claims (Q2, decided 2026-10-07): everything except a denylist.** Site-specific claims such as an
`employee_id` come through without being named anywhere. The denylist is
`OTEL_WRAPPER_HEADER_ATTRIBUTES_EXCLUDE`: comma-separated glob patterns matched against the flattened claim path
(`realm_access.roles`, `email`). Denied claims are **dropped** before they're recorded, not scrubbed with a marker.
Everything else is recorded as-is, so the scrubber lets all remaining `http.request.header.x-userinfo.*` attributes
through (a generic scrubber would mangle `auth_time`, `session_state` and `iss`; see Evidence). Default (confirmed
2026-10-18): credentials and session handles, `*token*,at_hash,c_hash,nonce,session_state,sid`. Personal data
(`email`, `name`) is captured unless added to the list; README says so.

*Imported at adoption (2026-10-18) from `PLAN.md` § Questions for later, `PLAN.md` § Workstreams § 5. Headers, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
