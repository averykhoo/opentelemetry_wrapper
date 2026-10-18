---
type: Decision
id: DEC-54
title: 'Upstream OTel bumps: Renovate PRs that auto-merge only when CI passes'
actor: owner
decided: 2026-10-18
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:c8d5eca09a8a6fd5745753c216709d8f6a41ab285d70b70a42740604712414f7
tags: [process]
tasks: [OTW-2]
---

- **Upstream bumps without anyone watching CI** (the author doesn't check CI results; decided 2026-10-18): automation
  is only worth having if it updates the repo by itself. Use **Renovate** (GitHub app) rather than a home-grown job:
  it opens a PR that raises the OTel caps, the PR's CI runs the suite and the canaries, and Renovate **auto-merges
  only if everything passes**; a failing PR just sits there and the old pins keep protecting users. OTel has shipped
  breaking changes without warning (twice during v0), which is why the pins stay strict (workstream 10). Config to
  get right (not verified yet): group all `opentelemetry-*` packages into one PR (SDK and contrib release in
  lockstep); a range strategy that moves the upper cap (`<1.45` -> `<1.46`); contrib versions like `0.66b0` are PEP
  440 pre-releases, so Renovate must not ignore them as unstable.

- Without Renovate, the same check runs locally as `pytest -m upstream` whenever someone works on the repo.

*Imported at adoption (2026-10-18) from `PLAN.md` § Workstreams § 0. Tests, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
