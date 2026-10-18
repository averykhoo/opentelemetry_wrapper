---
type: Decision
id: DEC-80
title: Root is v1; v0's names load lazily; v0's dependencies stay core until 1.0.0
actor: owner
decided: 2026-10-19
session: 2026-10-18l
decision_status: PROVISIONAL
answers: ASK-23
body_sha: sha256:b4422b5bd885ab107938c9bb9faaf19850c196e6c8b97d14aa13efdfd6ea6088
---

Owner, answering ASK-23: *"Owner, 2026-10-19 (session 2026-10-18l), verbatim, answering ASK-23 put as a multiple-choice question whose recommended option was "Root v1, v0 lazy: Root exports otel/OtelWrapperWarning; v0's old names still resolve via a lazy module __getattr__ (v0's setup then runs on first use of a v0 name, not at import). v0's deps become a [v0] extra.":

> Does option 1 mean full backwards compat? If so let's do that. But does v0 even work on the same otel versions?

The session answered: code-level yes (same names, same behaviour once used; v0's import-time setup moves to first use of a v0 name), install-level only if v0's dependencies stay core; and yes, v0's characterization suite passes on OTel 1.44.0 / 0.65b0 and CI was green on the latest releases on 3.12-3.14. Follow-up question: "With root = v1 and v0's names lazy: where do v0's heavy dependencies (fastapi, sqlalchemy, requests, pydantic, asgiref, prometheus_client, gRPC exporter, the contrib instrumentors) live until v0 is deleted at 1.0.0?" Owner chose, verbatim:

> Core until 1.0.0 (Recommended)

(That option read: "Full backwards compat: plain `pip install opentelemetry_wrapper` keeps working for v0 users. The lean no-extras install (AC-20, DEC-36 no-gRPC) arrives only at 1.0.0 when v0 is deleted. Imports stay lazy, so v1 users don't pay the import cost, only the install size.")"*
