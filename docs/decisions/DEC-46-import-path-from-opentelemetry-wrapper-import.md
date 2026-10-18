---
type: Decision
id: DEC-46
title: 'Import path: `from opentelemetry_wrapper import otel` (proposal 4)'
actor: owner + agent
decided: 2026-10-08
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:c2126e40d1504a71691b9bedcfec108b1e914180eff1ad629b305cbc5f253b1e
tags: [api]
---

4. **Import path** (F5): `from opentelemetry_wrapper import otel`, so users change imports once, not twice. *Verified:*
   nothing in v0's `__all__` is called `otel`. `opentelemetry_wrapper.v1` stays the implementation module.

*Imported at adoption (2026-10-18) from `PLAN.md` § Proposals, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
