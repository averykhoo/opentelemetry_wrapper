# Session ledger

Append-only, newest first, one entry per session (FRAMEWORK §7.1).

---

## 2026-10-20b · kind: open

- **opened:** 2026-10-20T11:47:26+08:00 by claude-code/2.1.287
- **asked:** ASK-27

---

## 2026-10-20a · kind: close

- **rows:** OTW-24, OTW-25, OTW-26, OTW-27, OTW-21, OTW-19, ASK-25, ASK-26
- **receipts:**
  - guards: gate PASSED in 111.4s (1047 passed, 4 skipped, 2 warnings in 108.85s (0:01:48)) on
    g1/code:4a978efe3985ed79; lint clean
  - read: orient; OTW-19, ASK-25, OTW-21, OTW-15, OTW-17; DEC-31, DEC-42, DEC-44, DEC-80, DEC-81,
    DEC-83, DEC-84, DEC-85; README upgrade section
  - asked: ASK-26
- **summary** (the owner digest):
  - ASK-25 answered (DEC-95): only is_class emitted, the other DEC-31 extras commented out with the
    reason; OTW-24 done.
  - DEC-96 (owner): the first v1 release is 1.0.0, a hard cutover; supersedes DEC-80, amends DEC-44.
  - OTW-25 built and merged on main: v0 deleted, warn-once aliases onto v1, lean install, OTel caps
    1.45/0.66, version 1.0.0.
  - DEC-97 (owner): OTW-21 after v1, push-only first, publish after a couple of correct pushes.
  - Not pushed, not released; v0.1.25 tagged locally at 34e18ce. ASK-26 (drop v0's OTEL_* root
    values) raised.
- **Still owed:**
  - push of this session's commits and the v0.1.25 tag (owner's yes, then a CI watcher); the 1.0.0
    release (OTW-26, owner's word)

---

## 2026-10-19a · kind: close

- **rows:** OTW-10, OTW-6, OTW-7, OTW-4, OTW-11, OTW-12, OTW-22, OTW-16, OTW-23, OTW-19
- **receipts:**
  - guards: gate PASSED in 148.5s (1151 passed, 5 skipped, 23 xfailed in 146.14s (0:02:26)) on
    g1/code:ee6a2b3e7f0c285c
  - read: orient, BATON-1, OTW-10/6/16/19 bodies, DEC-37, DEC-53, DEC-79, each workflow's journal,
    CI runs via the REST API
  - asked: DEC-22 parenting, push permission, DEC-89 inherited methods, DEC-90 denylist, DEC-91
    commenter and aiosqlite, DEC-92 prometheus switch and trailing slash, DEC-93 ASGI spans, DEC-94
    debug message; ASK-25 left open
- **summary** (the owner digest):
  - BATON-1 done; closed OTW-10, 6, 7, 4, 11, 12 (the whole v1 chain), OTW-22 (AC-8: tests/v0 passes
    under v1) and OTW-16 (README.md is v1's), OTW-23 (scrubbing-failure reports)
  - Owner decisions DEC-87 to DEC-94; DEC-22 and DEC-59 amended; DEC-94 amended twice (final: A +
    shape)
  - Criteria tested now include AC-8, 9, 11, 12, 17, 18, 19, 28, 29, 30, 31, 33
  - Every merge pushed and CI green on 6 jobs (last checked e96536f); no release (DEC-85)
  - Waiting on the owner: ASK-25, OTW-21; OTW-15 waits on upstream; OTW-19 (records errata) is NOW
  - The GitHub token in .scratch/gh_token is rejected (Bad credentials): CI logs need a new one
- **Still owed:**
  - ASK-25 and OTW-21 need the owner; a new GitHub token for CI logs

---

## 2026-10-18l · kind: close

- **rows:** OTW-2, OTW-3, OTW-5, OTW-8, OTW-9, OTW-13, OTW-14, OTW-10, OTW-6, OTW-11, OTW-16,
  ASK-21, ASK-22, ASK-23, ASK-24, ASK-25
- **receipts:**
  - guards: gate PASSED in 538.3s (889 passed, 5 skipped, 23 xfailed in 516.71s (0:08:36)) on
    g1/code:539c576c1d826387; lint: clean
  - read: docs/runbooks/procedures.md (Housekeeping, Intake, Push and CI, Clean close),
    docs/runbooks/fan-out.md, DEC-31, DEC-46, tasks OTW-3/8/13/5/14/21/19
  - asked: ASK-21, ASK-22, ASK-23, ASK-24, ASK-25
- **summary** (the owner digest):
  - Pushed 55bac69, e9ff619, 6a44bd6, 38f04fe (no release, DEC-85); CI green on 38f04fe, all 6 jobs
    (python 3.12-3.14 x extras all/none).
  - Closed OTW-2 (3.14 partial fix in the v0 tests), OTW-3, OTW-5, OTW-8, OTW-9, OTW-13, OTW-14; 19
    criteria tested.
  - Owner decisions: DEC-79 (one ultracode agent per task, minimal tokens), DEC-80 to DEC-83
    (ASK-21..24), DEC-84 (main is v1; v0 patches from a tag), DEC-85, DEC-86; DEC-36 amended.
  - OTW-10 stopped mid-build at the owner's request: WIP on branch worktree-agent-a322b3ebbf1274cd5
    (BATON-1).
  - Open: ASK-25 (DEC-31's code.* extras); OTW-21 waits for the owner (auto-release vs 'don't
    release').
- **Still owed:**
  - BATON-1: resume OTW-10 from its WIP branch; ASK-25; OTW-21 needs the owner's call on
    auto-release before it is built

---

## 2026-10-18k · kind: close

- **rows:** OTW-2, OTW-11
- **receipts:**
  - guards: gate PASSED in 25.3s (243 passed, 2 skipped, 23 xfailed in 22.99s) on
    g1/code:3acf814a149e6230; log .context/gate/20261018T195321-19132.log
  - read: orient, task show OTW-2, docs/evidence/v1-design-evidence-2026-10-18.md, DEC-22, DEC-33,
    DEC-56, docs/archive/PLAN.md (fork, FastAPI and scrubbing notes)
  - asked: none
- **summary** (the owner digest):
  - OTW-2: canaries in tests/upstream (8 modules, 26 tests, marker upstream), each but the fork one
    seen red under a monkeypatched upstream break (83070c3)
  - OTW-2: interleaving test (two tasks plus a thread) against the OTel tracer, the sketch's shared
    stack as the known-bad control
  - OTW-2: benchmarks/overhead.py with a smoke test; v0 ~58 us decorated vs ~32 us bare OTel span
  - OTW-2: CI workflow .github/workflows/tests.yml + ci/test.sh, Linux, Python 3.12-3.14; never run
    yet (unpushed)
  - OTW-11: the SDK LoggingHandler is deprecated in 1.44 in favour of contrib's; which handler v1
    uses is OTW-11's call
  - Left for the owner: the push (2026-10-18j and k), whose CI run is OTW-2's last step
- **Still owed:**
  - the push of 2026-10-18j and 2026-10-18k (owner's yes), its CI run and the fork canary's first
    result; then close OTW-2

---

## 2026-10-18j · kind: close

- **rows:** OTW-2, OTW-21, OTW-1
- **receipts:**
  - guards: gate PASSED in 22.7s (214 passed, 1 skipped, 23 xfailed in 20.50s) on
    g1/code:863faf3faac7c989; lint: clean
  - read: orient, tasks/OTW-2, DEC-38, DEC-54, DEC-55, DEC-56, DEC-57, docs/criteria.md,
    procedures.md, manual-mode.md (task set, promote), tests/conftest.py, tests/v0/_harness.py,
    tests/impl.py
  - asked: none
- **summary** (the owner digest):
  - Owner: the plan is done, start building; chose to split OTW-2 (DEC-78).
  - OTW-21 (LATER, after OTW-13) takes Renovate and auto-release, with review: [shipped, write-op]
    and its design review owed.
  - Renovate checked against its docs and tests: contrib needs ignoreUnstable: false; no checks
    means no automerge; pre-release windows unverified.
  - Built the OTW_IMPL=v0|v1 adapter (tests/impl.py, DEC-38); v0_specific tests skip under v1;
    test_public_api still checks v0's own names.
  - Gate 214 passed, 1 skipped, 23 xfailed; OTW_IMPL=v1 runs to completion (failures expected).
  - Next in OTW-2: the canaries (tests/upstream), then CI. Not pushed.
- **Still owed:**
  - push of 2026-10-18j's commits needs the owner's yes; OTW-21's design review before it is built

---

## 2026-10-18i · kind: close

- **rows:** none
- **receipts:**
  - guards: gate PASSED in 23.0s (203 passed, 23 xfailed in 20.66s) on g1/code:912d9e4af5fe1d93;
    lint: clean
  - read: orient (from 2026-10-18g), procedures § Push and CI
- **summary** (the owner digest):
  - Fast-forwarded main to adopt-context-engine (12 commits, sessions 2026-10-18g and h); deleted
    the merged local branches adopt-context-engine and v1-plan.
  - One worktree, no stashes; origin's v1-plan is fully merged into main and left for the owner's
    word.
  - Pushed main at close; no workflow exists, so no CI run; the code scope matches the last verified
    push, so no fresh-env run.
- **Still owed:**
  - delete origin/v1-plan (owner's call)

---

## 2026-10-18h · kind: close

- **rows:** ASK-20, OTW-20, OTW-19, OTW-3, OTW-7, OTW-11, STORY-9, STORY-10
- **receipts:**
  - guards: require code: green (code: covered on g1/code:912d9e4af5fe1d93 by the all run of
    2026-10-18T15:16:50+08:00, 23.1s; no code changed); lint: clean
  - read: orient (from 2026-10-18g), charter, criteria, history-to-2026-10-18.md lines 125-145, task
    criteria lines
- **summary** (the owner digest):
  - Owner: 'Okay to all' on ASK-20, recorded as DEC-77.
  - Charter: ranking confirmed; G-1 slimmed; G-2 is 'hard to use incorrectly' (sync and async
    alike); G-3 fails small; DEC-75 stated once; the denylist only in G-9; G-8 cites DEC-34.
  - Criteria: every goal's measures equal the rows citing its story (checked by script); new AC-31
    (JSON-encode anything), AC-32 (no arguments on spans), AC-33 (the x-userinfo denylist split from
    AC-12).
  - STORY-9 and STORY-10 amended to name their decisions as the authority; OTW-3, OTW-7, OTW-11
    point at the new criteria; OTW-20 closed.
  - Nothing pushed: 2026-10-18g and 2026-10-18h are local commits.
- **Still owed:**
  - push (owner's yes); OTW-19's remaining errata and nits

---

## 2026-10-18g · kind: close

- **rows:** ASK-20, OTW-20, OTW-19
- **receipts:**
  - guards: require code: green (code: covered on g1/code:912d9e4af5fe1d93 by the all run of
    2026-10-18T15:16:50+08:00, 23.1s); lint: clean
  - read: orient, charter, STORY-1..13, criteria, HANDOFF.md (whole), OTW-2, OTW-19, ASK-17..19,
    DEC-28/34/45/61/72/73/76, deck slides 17/23/26-28
  - asked: ASK-20
- **summary** (the owner digest):
  - Read the charter, the 13 stories, the criteria and the v0 deck; a subagent reviewed them for
    parsimony (docs/evidence/parsimony-review-2026-10-18.md).
  - Verdict: close to parsimonious; repeats, provenance in the charter and three wrong or missing
    measure links.
  - Nothing open on the board besides it; DEC-61 is the owner's deferral; the PROVISIONAL decisions
    are signed off, unbuilt.
  - Owner: ASK-20, six choices with recommendations (agent rank placements, fail-small in G-3,
    slimmer G-1, charter trim, STORY-9/10, deck principles).
  - Agent: OTW-20 (LATER, after ASK-20) aligns measures and criteria; OTW-19's criteria bullet folds
    into it.
- **Still owed:**
  - ASK-20 answer (owner); then OTW-20; push not asked

---

## 2026-10-18f · kind: close

- **rows:** DEC-76, STORY-13, AC-12, AC-30, OTW-7
- **receipts:**
  - guards: gate PASSED in 23.1s (203 passed, 23 xfailed in 20.63s) on g1/code:912d9e4af5fe1d93; log
    .context/gate/20261018T151650-1824.log
  - read: orient (2026-10-18e banner); docs/runbooks/procedures.md § Push and CI; tasks/OTW-7;
    docs/criteria.md
- **summary** (the owner digest):
  - Owner: 'Okay with either, if you're not sure get an opinion from fable, but do add 13 in some
    shape or form, helpful is quite an important point'.
  - G-13 added (request context: the calling user via x-userinfo, upstream latency); G-7 kept, since
    folding would retire the owner-confirmed STORY-7; G-13 ranked 6th, first of the Helpful tier
    (DEC-76, STORY-13, AC-30). No fable opinion needed.
  - Owner: 'When done merge everything into main and push': main fast-forwarded to this close and
    pushed; CI watcher started (no workflow exists yet, so it expects no run).
  - Framework feedback appended.
- **Still owed:**
  - none

---

## 2026-10-18e · kind: close

- **rows:** DEC-72, DEC-73, DEC-74, DEC-75, ASK-18, ASK-19, STORY-1..12, AC-13, AC-22, AC-28, AC-29,
  OTW-3, OTW-8, OTW-19
- **receipts:**
  - guards: gate PASSED in 23.1s (203 passed, 23 xfailed in 20.82s) on g1/code:912d9e4af5fe1d93; log
    .context/gate/20261018T134848-20368.log
  - read: orient (2026-10-18d banner); docs/runbooks/procedures.md § Housekeeping, § Intake, § Clean
    close; docs/charter.md; STORY-1..10; .scratch/OpenTelemetry-Instrumentation-v6.md (the deck
    transcript)
  - asked: ASK-18, ASK-19
- **summary** (the owner digest):
  - Owner reviewed the charter: 'the higher goal wins' kept as a rule; never crash ranked first; G-9
    above G-10, both at the bottom (DEC-72).
  - STORY-1..10 confirmed (live). From the owner's v0 talk: a Purpose section and goals G-11
    (succinct, idiomatic) and G-12 (documented defaults), with STORY-11/12 and AC-28/29 (DEC-73).
  - Cleaned deck summary committed as docs/evidence/v0-talk-deck-2026-10-18.md; the deck stays in
    .scratch (internal details, public repo).
  - ASK-18 -> DEC-74: a value that fails to scrub is dropped and replaced by its own '[REDACTED:
    scrubbing failed]' placeholder (AC-13).
  - ASK-19 -> DEC-75: swallowed runtime failures go to stderr, one JSON line per site, never via
    warnings/logging; tracebacks opt-in (relaxes DEC-49; AC-22, G-4).
  - Framework feedback appended (the ranking rule, as the owner asked; no story-confirm operation).
    Nothing pushed.
- **Still owed:**
  - push of adopt-context-engine (unpushed commits since 2026-10-18c), with the owner's yes
  - G-13 (application context: x-userinfo, upstream latency, k8s) was proposed but not named in the
    owner's answer; ask whether to add it

---

## 2026-10-18d · kind: close

- **rows:** ASK-17, OTW-18
- **receipts:**
  - guards: code: covered on g1/code:912d9e4af5fe1d93 by the all run of 2026-10-18T11:07:54+08:00
    (23.2s, .context/gate/20261018T110754-24408.log)
  - read: orient (2026-10-18c context); docs/runbooks/procedures.md § Intake
- **summary** (the owner digest):
  - Owner: "We won't touch v0, record that and I'll check the charter and stories next session".
  - ASK-17 answered as DEC-71 (no v0 patch release); OTW-18 (v0 cleanup for a further release)
    closed as moot.
  - Charter and STORY-1..10 review is next session's, with the owner (banner).
- **Still owed:**
  - none

---

## 2026-10-18c · kind: close

- **rows:** OTW-18, OTW-19
- **receipts:**
  - guards: gate PASSED in 23.2s (203 passed, 23 xfailed in 20.88s) on g1/code:912d9e4af5fe1d93; log
    .context/gate/20261018T110754-24408.log
  - read: orient; docs/runbooks/procedures.md § Clean close; the five verification reports
  - asked: ASK-17
- **summary** (the owner digest):
  - Owner: "Check if the context engine mcp is up"; it is (session_start, ask_raised, lint answered
    over MCP).
  - Owner: "use ultracode to send out cheaper agents (maybe sonnet) to do a manual verification then
    push it to master and clean up the temp stuff used to test the migration".
  - Verification: 5 Sonnet checkers + skeptics over decisions, board/criteria, archive/map,
    code/config, charter/engine; no content lost, no blocker.
  - Fixed: OTW-18's garbled sentence, CLAUDE.md's actor-rule attribution, archive README's DEC-64
    count (338412e); the rest is OTW-19.
  - Pushed: main fast-forwarded 26a4ee4..338412e (master = main here); CI watcher started on
    338412e.
  - Cleanup: migration scratch removed from .scratch (otw-trial, ce-env, engine clone, orig, audit,
    verify, drafts); design scratch kept.
- **Still owed:**
  - none

---

## 2026-10-18b · kind: close

- **rows:** ASK-17
- **receipts:**
  - guards: gate PASSED in 22.2s (203 passed, 23 xfailed in 19.98s) on g1/code:912d9e4af5fe1d93;
    lint: clean
  - read: none beyond CLAUDE.md and orient
  - asked: ASK-17
- **summary** (the owner digest):
  - Installed the context-engine plugin at project scope; its MCP server
    (plugin:context-engine:engine) connects; restart Claude Code to load it.
  - context-engine-feedback.md: the prefix friction in full (kit vs README vs DEC-38, hardcoded G-n
    and INV-n, Q-n aliases, ASK-17).
  - Still owed by the owner: review of the charter, stories and decisions; ASK-17; the push of
    adopt-context-engine.
- **Still owed:**
  - owner review of the charter, stories and decisions; ASK-17; push of adopt-context-engine
    (owner's yes)

---

## 2026-10-18a · kind: close

- **rows:** OTW-1,OTW-2,OTW-3,OTW-4,OTW-5,OTW-6,OTW-7,OTW-8,OTW-9,OTW-10,OTW-11,OTW-12,OTW-13,OTW-14,OTW-15,OTW-16,OTW-17,OTW-18,ASK-17
- **receipts:**
  - guards: gate PASSED in 22.1s (203 passed, 23 xfailed in 19.83s) on g1/code:912d9e4af5fe1d93;
    lint: clean
  - read: CLAUDE.md, HANDOFF.md (all: rewritten this session), PLAN.md, TODO.md, the engine's kit
    README, contract, procedures
  - asked: ASK-17
- **summary** (the owner digest):
  - Adopted context-engine at engine 7fd39975554a5a5edfb7a74e90ccbdcc5a0bd7e3 (framework 0.5); env
    .context-engine/env, plugin enabled.
  - PLAN.md, HANDOFF.md and TODO.md migrated: DEC-1..69 (Q-n aliases), charter G-1..10, STORY-1..10,
    AC-1..27, OTW-1..18.
  - PLAN.md and TODO.md archived in docs/archive/; docs/evidence/adoption-map-2026-10-18.md maps
    every part.
  - Owner's adoption words: DEC-70 (engine defaults, automatic commits, full migration, v1 epic
    OTW-1, feedback file).
  - An independent audit re-checked the migration; its 11 must-fix findings are fixed (81d86c6).
  - Owner to review: the charter and STORY-1..10 (unconfirmed reconstructions) and the decisions;
    ASK-17 raised.
  - Not pushed: adopt-context-engine needs the owner's yes; frictions and AAR are in
    context-engine-feedback.md.
- **Still owed:**
  - owner review of the charter, stories and decisions; ASK-17; push of adopt-context-engine
    (owner's yes)
