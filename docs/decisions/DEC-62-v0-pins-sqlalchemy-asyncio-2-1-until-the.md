---
type: Decision
id: DEC-62
title: v0 pins `sqlalchemy[asyncio]<2.1` until the contrib instrumentor supports 2.1
actor: owner + agent
decided: 2026-10-08
session: 2026-10-18a
decision_status: BUILT
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:264d6bed5a7e3064eed8f3be2f48460e94393b90d3a93bc27b672500f75578ae
tags: [v0]
tasks: [OTW-4, OTW-15]
---

  - `requirements.txt` / `pyproject.toml`: `sqlalchemy` -> `sqlalchemy[asyncio]<2.1` (temporary pin, see below)

- **Unpin sqlalchemy.** `opentelemetry-instrumentation-sqlalchemy` (<= 0.66b0) declares `sqlalchemy < 2.1.0`, so on
  2.1 it logs a `DependencyConflict` and silently produces no spans. The hooks themselves work on 2.1 (verified with
  `skip_dep_check=True`); only the declared range is stale. Track
  [issue #5118](https://github.com/open-telemetry/opentelemetry-python-contrib/issues/5118) / PR #5120. Once a
  release supports 2.1: remove `<2.1` from both dependency files, set that release as the minimum for
  `opentelemetry-instrumentation-sqlalchemy`, and check `sqlalchemy_example.py` prints a `SELECT` span.

*Imported at adoption (2026-10-18) from `HANDOFF.md` § State § v0 fixes, `HANDOFF.md` § Watch upstream, as committed at `24a0430`; now at `docs/evidence/history-to-2026-10-18.md`.*
