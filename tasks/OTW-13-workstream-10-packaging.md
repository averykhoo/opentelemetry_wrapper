---
type: Task
id: OTW-13
title: 'Workstream 10: packaging'
brief: integrations become extras; no grpcio; OTel capped at the next minor
pri: NEXT
state: open
deps: [OTW-2]
source: session 2026-10-18a
created: 2026-10-18
moved: 2026-10-18a
updated: 2026-10-18l
aliases: [WS10]
labels: [v1]
---

Criteria: AC-20. Decisions: DEC-35, DEC-36, DEC-44, DEC-57, DEC-16.

*Workstream 10 of the v1 design, verbatim from the pre-adoption `PLAN.md` (`docs/archive/PLAN.md`); there, "workstream n" is the task aliased `WSn` (OTW-1 lists them), "Decided" / "proposal n" / "Qn" are decisions (`docs/evidence/adoption-map-2026-10-18.md`), and "`HANDOFF.md`" is the old note in `docs/evidence/history-to-2026-10-18.md`.*

- `requires-python = ">=3.12"` (v0's `">3.8.0"` also excluded 3.8.0 by accident). Side-by-side means v0 users get the
  3.12 floor in that release: make it a minor-version bump with a clear note, and the v0 deletion 1.0.0.
- Core dependencies: `opentelemetry-api`, `-sdk`, `-exporter-otlp-proto-http`, `-semantic-conventions`,
  `-instrumentation-logging` (its handler, see workstream 8) and `-exporter-prometheus`. Integrations become extras
  (`[fastapi]`, `[sqlalchemy]`, `[requests]`, `[system-metrics]`, each pulling the matching contrib instrumentor),
  plus `[hyperscan]` (the faster scrubbing engine, Q16), instead of hard dependencies on
  fastapi, uvicorn, sqlalchemy, requests and pydantic. Dev dependencies add `interegular` (rule-overlap lint). Drop
  `opentelemetry-exporter-otlp` (it pulls in gRPC).
- **Strict OTel pins, as in v0** (decided 2026-10-18): OTel has shipped breaking changes without warning, twice
  during v0's development. Cap the SDK family at the next minor (e.g. `opentelemetry-sdk>=1.44,<1.45`) and pin the
  contrib packages to the matching `0.XbY` window (they release in lockstep). Renovate's auto-merged bump PRs
  (workstream 0) and the canaries decide when a cap moves; the difference from logfire's caps is that we set the
  pace.
- `py.typed`.

**Done when:** `pip install opentelemetry_wrapper` without extras imports and runs `@otel`, and each extra enables
its integration; CI covers both.

## Traps

- none known

## Read first

- The decisions: [DEC-35](../docs/decisions/DEC-35-pydantic-2-only-optional-never-imported-by-us.md), [DEC-36](../docs/decisions/DEC-36-otlp-http-only-grpc-export-dropped.md), [DEC-44](../docs/decisions/DEC-44-v1-requires-python-3-12-or-later.md), [DEC-57](../docs/decisions/DEC-57-strict-otel-pins-capped-at-the-next-minor.md), [DEC-16](../docs/decisions/DEC-16-scrubbing-engine-stdlib-re-by-default-hyperscan.md); [the criteria](../docs/criteria.md)

## Log

- 2026-10-18l (claude-code/2.1.287): 576106a (merged): pyproject (requires-python >=3.12, SDK >=1.44,<1.45, contrib 0.65b0 window, extras fastapi/sqlalchemy/requests/system-metrics/hyperscan/dev, pytest11 entry point, no opentelemetry-exporter-otlp meta package), requirements.txt aligned, py.typed, ci/test.sh modes all|core + ci/smoke_core.py, workflow matrix python x extras, tests/test_packaging.py (22 static checks, 20 sabotages). v0's deps (incl. the gRPC exporter v0 imports) stay core until 1.0.0 (DEC-80, DEC-36 amended); main is the v1 line (DEC-84). Left: root becomes v1 with lazy v0 names (DEC-80, in progress); 'each extra enables its integration' is only checked statically; first CI run of the extras axis after the next push; hyperscan wheels on 3.14 unverified.
