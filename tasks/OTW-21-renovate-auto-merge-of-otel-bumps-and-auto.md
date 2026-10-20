---
type: Task
id: OTW-21
title: Renovate auto-merge of OTel bumps and auto-release of dependency-only merges
brief: 'Split from OTW-2 (DEC-78): Renovate bumps of the strict OTel pins, auto-merged on green CI; patch release (AC-24)'
pri: LATER
state: open
deps: [OTW-2, OTW-13, OTW-25]
source: session 2026-10-18j
created: 2026-10-18
moved: 2026-10-18j
updated: 2026-10-20a
review: [shipped, write-op]
---

Split from OTW-2 by DEC-78: it waits for the strict OTel pins (OTW-13, DEC-57), since until then there is nothing for it to bump. What it covers is DEC-54 (Renovate, grouped `opentelemetry-*` PRs that move the cap, auto-merged only when CI is green) and DEC-55 (a patch release to PyPI by trusted publishing when a dependency-only PR merges); OTW-2's text, verbatim from the pre-adoption plan, has the detail.

Owner-side setup it needs: install the Renovate GitHub app on the repo, add a PyPI trusted publisher for the release workflow, and require the CI checks on `main`.

## Traps

- Above the design-review threshold (it ships automation that merges and publishes by itself): write its `## Design review` before building (FRAMEWORK §5.2); `review: [shipped, write-op]` is set.
- Renovate skips 0.65b0 -> 0.66b0 by default (`ignoreUnstable`): the contrib packages need `ignoreUnstable: false`. The pep440 `replace` strategy moves a window such as `>=1.0.0,<1.1.0`, but no Renovate test covers a pre-release window like `>=0.65b0,<0.66` (OTW-2's log, 2026-10-18j). An exact pin (`==0.65b0`) is covered.
- Never set `ignoreTests`: with it off, a PR that has no checks is not merged, which fails safe. A CI run that collects no tests must fail too.
- `node` is not installed on the owner's machine, so Renovate cannot be dry-run locally; it is verified on GitHub.

## Read first

- [DEC-54](../docs/decisions/DEC-54-upstream-otel-bumps-renovate-prs-that-auto.md), [DEC-55](../docs/decisions/DEC-55-dependency-only-merges-are-released.md), [DEC-57](../docs/decisions/DEC-57-strict-otel-pins-capped-at-the-next-minor.md), [DEC-78](../docs/decisions/DEC-78-building-starts-otw-2-is-split-renovate-and.md); `docs/runbooks/release.md`

## Log

- 2026-10-20a (claude-code/2.1.287): DEC-97 (owner, 2026-10-20): after the v1 release; build it push-only first, publish turned on after a couple of correct pushes.
