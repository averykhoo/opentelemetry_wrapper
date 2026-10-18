---
type: Decision
id: DEC-28
title: Exporters are chosen from the standard `OTEL_*` env vars
actor: owner
decided: 2026-10-08
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:72a14bb79482d1168eceae54cda342cfbbd2e379690a8bbbb3f413dc5d4539ee
tags: [config]
tasks: [OTW-3]
---

- **Exporters from the standard env vars:** `OTEL_EXPORTER_OTLP_{,TRACES_,METRICS_,LOGS_}ENDPOINT`, `..._HEADERS`,
  `..._TIMEOUT`, and `OTEL_{TRACES,METRICS,LOGS}_EXPORTER` (`otlp`, `console`, `none`). The OTLP exporters read most of
  these themselves; we only decide which exporters to build.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
