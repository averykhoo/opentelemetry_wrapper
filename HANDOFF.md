# HANDOFF

LIVING. Orientation note (FRAMEWORK §5.1): what is true now, the next session's first steps, and facts not
derivable from the code. The board is `context-engine task list`; this note keeps no copy of it. The banner is
written at each clean close by `context-engine banner set`.

## Banner (2026-10-19a)

- **Engine mode since 2026-10-18a** (engine `7fd3997`, framework 0.5): the v1 design is records now (DEC-n, the
  board, AC-n); `docs/evidence/adoption-map-2026-10-18.md` maps the archived `PLAN.md` / `TODO.md` onto them.
- **The charter is the owner's since 2026-10-18e** (DEC-72, DEC-73, trimmed by DEC-77): the higher goal wins, never
  crash first; scrub failures get their own placeholder (DEC-74); swallowed runtime failures go to stderr (DEC-75).
- **v1 is built (2026-10-19a, DEC-87: one build/review/fix workflow per task, the session merging and gating).**
  Every v1 workstream is closed; `tests/v0` passes under `OTW_IMPL=v1` and the gate checks it (AC-8, OTW-22);
  `README.md` is v1's, v0's is `docs/archive/README_v0.md` (OTW-16). Owner decisions this session: DEC-88 to DEC-94.
- **Left on OTW-1:** OTW-21 (auto-release) waits for the owner, who said "don't release" (DEC-85); ASK-25 is open;
  OTW-15 waits on upstream; OTW-19 (records errata) is NOW. No release has been cut: v1 is on `main` only.
- **v0 is not touched** (DEC-71). `main` is the v1 line, v0 patches go from a tag (DEC-84).
- **On `main`, every merge pushed; CI green on all 6 jobs** (python 3.12-3.14 x extras all/none). The GitHub token in
  `.scratch/gh_token` is rejected now; listing runs and jobs needs none, reading a job's log does.
- **Commits are automatic here, pushes need the owner's yes** (DEC-70; this session had it, DEC-88). Every clean close
  appends to `context-engine-feedback.md`. The local gate takes about 150 s (1151 passed, 5 skipped, 23 xfailed).

## Next session: start here

1. `CLAUDE.md` (loads automatically): environment, gate, the overrides of the global rules, and the framework
   contract it imports.
2. The `SessionStart` hook prints `context-engine orient` (banner, batons, open sessions, the NEXT tier, questions
   to raise, the top item); then `context-engine session start`, in the order `docs/runbooks/procedures.md` gives.
   Raise any question it lists in chat, one line each, then `context-engine ask raised <ids>`.
3. `context-engine task show <id>` for the top item. The v1 rebuild is the epic `OTW-1`, which lists its
   workstreams; `OTW-2` (workstream 0: the `OTW_IMPL` adapter, canaries, CI, Renovate) comes first.
4. The v1 design is records now: `docs/decisions/index.md` (DEC-n), each workstream's task body, and the evidence
   docs. The pre-adoption `PLAN.md` and `TODO.md` are archived unchanged in `docs/archive/`, and
   `docs/evidence/adoption-map-2026-10-18.md` says where each of their parts went.
5. Read the rest of this note only if needed, and say which part in the ledger entry's `read:` line.

## Facts not derivable from the code (dated)

- **2026-10-18, branches:** `v1-plan` holds the v1 design commits on top of `main`; it is pushed to origin (at
  `24a0430`), not merged. `adopt-context-engine` (this adoption) branches from it and is not pushed. Hosting is
  GitHub + PyPI (DEC-40).
- **2026-10-18, history before adoption:** the old orientation note, verbatim, with the v0 fixes of 2026-10-08 and
  the v0 bug inventory, is `docs/evidence/history-to-2026-10-18.md`. Commit messages from before the adoption keep
  the old ids (`PLAN.md` workstreams, `Q15`, `HANDOFF.md` sections); the test comments were rewritten to cite records.
- **2026-10-18, local-only material:** the author's untracked notes (the evidence scripts, the Q15 spike, the
  scrubbing prototype, the full ergonomics review with findings F1-F12, the v0 talk deck transcript) exist on the
  author's machine only. Everything the design needs from them is in the decisions and evidence docs; OTW-2 turns
  the evidence scripts into canary tests.
- **2026-10-18, upstream watch:** `opentelemetry-instrumentation-sqlalchemy` (<= 0.66b0) declares `sqlalchemy <
  2.1.0`, hence the temporary `sqlalchemy[asyncio]<2.1` pin (DEC-62); unpinning is OTW-15.
- **2026-10-18, the user never reads CI results** (DEC-54): automation is only worth having if it acts by itself.
- **2026-10-18, v0 pins no OTel package** (DEC-57's amendment): an OTel release can break v0 users today; strict
  pins arrive with v1 (OTW-13).
