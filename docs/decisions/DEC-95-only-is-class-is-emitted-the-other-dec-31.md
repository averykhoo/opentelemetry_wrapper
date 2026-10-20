---
type: Decision
id: DEC-95
title: Only is_class is emitted; the other DEC-31 extras stay commented out with the reason
actor: owner
decided: 2026-10-20
session: 2026-10-20a
decision_status: PROVISIONAL
answers: ASK-25
body_sha: sha256:3f0ea12e99c3b5c4b7abe68d0d519876b6b37bdd8f766de5fe5b513401725b82
tasks: [OTW-24]
---

Owner, answering ASK-25: *"Owner, 2026-10-20 (session 2026-10-20a), verbatim, answering ASK-25 (options (a) emit all three DEC-31 extras, (b) is_class only, recommended (b)):

> 1 - okay with b, implement but comment out the other attribs with the reason they're not included

Read as: emit only `opentelemetry_wrapper.code.is_class`; the wrapper chain and end line stay in the code as commented-out lines, each with the reason it is left out (no consumer yet, and each adds an attribute to every span)."*
