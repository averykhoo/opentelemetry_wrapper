---
type: Decision
id: DEC-81
title: Runtime warnings go to stderr once, never through warnings.warn
actor: owner
decided: 2026-10-19
session: 2026-10-18l
decision_status: PROVISIONAL
answers: ASK-24
body_sha: sha256:b7649d49a71d147517e48c0fb23537851d5423eec26afcc1b1cfea1764b19a48
---

Owner, answering ASK-24: *"Owner, 2026-10-19 (session 2026-10-18l), verbatim, choosing among "Stderr once at runtime (Recommended): At runtime, report such warnings to stderr once (like DEC-75) instead of warnings.warn, so no filter can make them raise. Applies to both cases." / "Keep warnings.warn" / "Drop the DEC-47 warning" (both cases: the second unnamed `with otel:` block, and a configure-time warning raised by implicit configuration at the first span):

> Stderr once at runtime (Recommended)"*
