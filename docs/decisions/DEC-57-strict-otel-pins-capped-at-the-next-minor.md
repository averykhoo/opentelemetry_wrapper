---
type: Decision
id: DEC-57
title: Strict OTel pins, capped at the next minor
actor: owner
decided: 2026-10-18
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:3aa1beece008f20ab69173c3bbdbbf8e32e8489f786a16c197f03e1d4619b13d
tags: [packaging]
tasks: [OTW-13, OTW-2]
---

- **Strict OTel pins, as in v0** (decided 2026-10-18): OTel has shipped breaking changes without warning, twice
  during v0's development. Cap the SDK family at the next minor (e.g. `opentelemetry-sdk>=1.44,<1.45`) and pin the
  contrib packages to the matching `0.XbY` window (they release in lockstep). Renovate's auto-merged bump PRs
  (workstream 0) and the canaries decide when a cap moves; the difference from logfire's caps is that we set the
  pace.

*Imported at adoption (2026-10-18) from `PLAN.md` § Workstreams § 10. Packaging, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

## Amendments

- **2026-10-18a (claude-code/2.1.287):** Correction at adoption (2026-10-18): "as in v0" overstates it. v0's pyproject.toml pins no OTel package today: the one OTel pin, opentelemetry-sdk<=1.24.0 (e99c0d9, 2024-08-02), was removed on 2024-08-15 (9523d9b). Strict pins start with v1 (OTW-13); v0 users are not protected from an OTel release.
