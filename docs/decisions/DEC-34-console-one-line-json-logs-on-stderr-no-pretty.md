---
type: Decision
id: DEC-34
title: 'Console: one-line JSON logs on stderr; no pretty console in 1.0'
actor: owner
decided: 2026-10-17
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:2543f0adc2466ccd05437685aaa54e4e9b932d118820afa7d6fb414e0d06b089
tags: [logging]
---

- **Console:** one-line JSON logs on stderr (`OTEL_WRAPPER_LOG_FORMAT=json|off`). No pretty console in 1.0 (decided
  2026-10-17; it was logfire's); for local debugging of spans, `OTEL_TRACES_EXPORTER=console` gives the SDK's
  `ConsoleSpanExporter`.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
