---
type: Decision
id: DEC-69
title: RED metrics computed in the library
actor: owner
decided: 2024-04-09
session: 2026-10-18a
decision_status: REJECTED
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:93f5bd1d9c301575f53a219f87257d2768cd8c56c2de109a043727aba91ebe9a
tags: [telemetry]
reopen_if: the platform's collector can no longer derive RED metrics from spans
---

* ~~add RED metrics, e.g. whatever `prometheus-fastapi-instrumentator` is doing~~
    * this should be automatically done in the backend otel collector

*Imported at adoption (2026-10-18) from `TODO.md` § won't do, as committed at `24a0430`; now at `docs/archive/TODO.md`.*
