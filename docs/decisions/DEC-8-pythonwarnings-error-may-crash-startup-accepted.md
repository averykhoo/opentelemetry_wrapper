---
type: Decision
id: DEC-8
title: '`PYTHONWARNINGS=error` may crash startup: accepted and documented (Q8)'
actor: owner
decided: 2026-10-18
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
aliases: [Q-8]
body_sha: sha256:7a06f207fdca0b6a20a98cadc72ef2f1adf3e454041ffab961336ba917ebe116
tags: [api]
tasks: [OTW-3]
---

- **Q8. `PYTHONWARNINGS=error` in production** turns our startup warnings into exceptions. Accept that as the one
  sanctioned exception to "never crash" (the user asked for it), or catch it? *Suggested:* accept and document. The
  author finds it defensible; the second opinion (2026-10-18) agrees, with high confidence: a startup crash is
  deterministic and happens before readiness, so a rollout halts without dropping traffic (true only because our
  warnings never fire lazily on a request); catching or downgrading would second-guess an explicit operator request,
  and `warnings.catch_warnings` isn't thread-safe. Mainstream libraries (requests, urllib3, SQLAlchemy, pydantic) use
  plain `warnings.warn`; the OTel SDK mostly uses `logging`, so proposal 7 is a deliberate departure. *Decided
  2026-10-18:* accepted, with proposal 7's amendments (emit after state is consistent; the pytest CI recipe).

*Imported at adoption (2026-10-18) from `PLAN.md` § Questions for later, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
