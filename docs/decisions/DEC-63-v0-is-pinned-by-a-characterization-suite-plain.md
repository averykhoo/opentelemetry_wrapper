---
type: Decision
id: DEC-63
title: 'v0 is pinned by a characterization suite: plain tests, strict xfails for bugs, `v0_specific` for intended changes'
actor: owner + agent
decided: 2026-10-07
session: 2026-10-18a
decision_status: BUILT
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:76df5247dd1261f8a1120b85043f8b6c82a1fcf8ca5a74f1c175ccffe75d7d41
tags: [testing]
tasks: [OTW-2]
---

**Test suite (added 2026-10-07, committed 2026-10-08):** `python -m pytest -q tests/v0` -> `203 passed, 23 xfailed` (~22 s).
It characterizes v0 so v1 can be checked against it. Plain tests pin behaviour v1 should keep. Known bugs are
`xfail(strict=True)` tests asserting the *correct* behaviour, so they error once fixed. `@pytest.mark.v0_specific`
(79 tests) marks v0 details PLAN.md intends to change (name formats, deprecated `code.*` keys, env var parsing,
`user@host` service name). Global OTel state is handled by running scenarios in subprocesses (`tests/v0/_harness.py`).

*Imported at adoption (2026-10-18) from `HANDOFF.md` § How to verify, as committed at `24a0430`; now at `docs/evidence/history-to-2026-10-18.md`.*
