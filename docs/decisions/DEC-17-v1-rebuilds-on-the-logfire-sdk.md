---
type: Decision
id: DEC-17
title: v1 rebuilds on the Logfire SDK
actor: owner
decided: 2026-10-04
session: 2026-10-18a
decision_status: SUPERSEDED
status: deprecated
superseded_by: [DEC-15]
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:c1f19d87ed5d9950febfc4428b1d3c1f772486e3c34de4b337df00c51facac1a
tags: [architecture]
---

Started 2026-10-04, last updated 2026-10-18. This is the design for the next major version ("v1"; the current code is
v0), written to be reviewed cold. It started as a rebuild on the Logfire SDK; the 2026-10-17 spike (Q15) showed v1
used little of it, and logfire was dropped (see "Why not logfire").

- [ ] v1 rebuild: **design in `PLAN.md`**. Originally planned on the Logfire SDK; since 2026-10-17 on the plain OTel
  SDK + contrib instrumentors (`PLAN.md` "Why not logfire").

*Imported at adoption (2026-10-18) from `HANDOFF.md` § TODO § Bigger picture, `PLAN.md` § the preamble, as committed at `24a0430`; now at `docs/archive/PLAN.md`, `docs/evidence/history-to-2026-10-18.md`.*

## Amendments

- **2026-10-18a (claude-code/2.1.287):** imported heading note: **SUPERSEDED by Q-15**
