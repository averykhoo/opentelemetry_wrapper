---
type: Task
id: OTW-15
title: Unpin sqlalchemy once the contrib instrumentor supports 2.1
brief: remove <2.1 from both dependency files and raise the instrumentor's minimum in the same change
pri: LATER
state: open
deps: []
source: session 2026-10-18a
created: 2026-10-18
moved: 2026-10-18a
updated: 2026-10-18a
labels: [upstream, v0]
---

From the old `HANDOFF.md` § Watch upstream (DEC-62), verbatim:

- **Unpin sqlalchemy.** `opentelemetry-instrumentation-sqlalchemy` (<= 0.66b0) declares `sqlalchemy < 2.1.0`, so on
  2.1 it logs a `DependencyConflict` and silently produces no spans. The hooks themselves work on 2.1 (verified with
  `skip_dep_check=True`); only the declared range is stale. Track
  [issue #5118](https://github.com/open-telemetry/opentelemetry-python-contrib/issues/5118) / PR #5120. Once a
  release supports 2.1: remove `<2.1` from both dependency files, set that release as the minimum for
  `opentelemetry-instrumentation-sqlalchemy`, and check `sqlalchemy_example.py` prints a `SELECT` span.

v1 may not need the pin at all: attaching `EngineTracer` directly skips upstream's dependency check (OTW-4).

## Traps

- The contrib release that supports sqlalchemy 2.1 may also need a newer OTel SDK: move the caps together (DEC-57).

## Read first

- [history](../docs/evidence/history-to-2026-10-18.md)
