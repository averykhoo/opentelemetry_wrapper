# Adoption map: where the pre-adoption docs went

FROZEN 2026-10-18 (session 2026-10-18a). The repo adopted `context-engine` (engine `7fd3997`, framework 0.5) and
migrated its three working docs, as committed at `24a0430`, into records. The originals are unchanged in
`docs/archive/` (`PLAN.md`, `TODO.md`) and in `docs/evidence/history-to-2026-10-18.md` (`HANDOFF.md`). The
decisions' id map is `docs/evidence/decision-id-map-2026-10-18.md`, and the log they were imported from is
`docs/evidence/decision-log-import-2026-10-18.md`. The id map prints every status as BUILT, the import's
default: the statuses were set right after it (below), and `docs/decisions/index.md` is current.

## Conventions used

- **Decision status:** BUILT means in force with nothing left to build (a process fact, a v0 change); PROVISIONAL
  means decided v1 behaviour not built yet (it becomes BUILT when the task that builds it closes); REJECTED carries
  `reopen_if`; DEFERRED is out of v1.0 but not ruled out; SUPERSEDED links its successor. Every PROVISIONAL decision
  is linked (`tasks:`) to the task that builds it, so `context-engine why OTW-n` lists a task's decisions.
- **Actor:** `owner` for what the plan recorded as the author's decision; `owner + agent` for agent proposals the
  author signed off (proposals 3-11) and for v0 work the agent did at the author's request. Each record's `decided`
  is the original date; its `session` is the import's.
- **Old ids:** Q1-Q16 kept their numbers (DEC-1 to DEC-16) with the aliases `Q-1` to `Q-16`; the importer only takes
  hyphenated ids, so `Q15` itself does not resolve (`decision find Q15` finds it by title). Proposals and plain
  bullets had no ids that could keep their number (they would collide with the Qs), so their old label stays in the
  title. Workstreams keep theirs as task aliases (`WS0` to `WS11`, `WS5b`).
- **Stories** are agent reconstructions (`story_status: unconfirmed`), each quoting its source verbatim; the charter
  is unconfirmed too. The owner confirms both in one review.

## PLAN.md

| Section | Now |
|---|---|
| Preamble, For the reviewer | DEC-17 (v1 first planned on the Logfire SDK, superseded by DEC-15); the reviewer checklist is obsolete |
| Goal | charter G-1, STORY-1; the Python floor is DEC-44 |
| Principles 1-7 | charter G-2 to G-8 and its ranked principles; STORY-2 to STORY-8 |
| Decided: API | DEC-19, DEC-20, DEC-21, DEC-22, DEC-23, DEC-24, DEC-25, DEC-26, DEC-27 (proposal 1), DEC-28 |
| Decided: telemetry content | DEC-29, DEC-30, DEC-31, DEC-32, DEC-33 |
| Decided: output and dependencies | DEC-34, DEC-35, DEC-36 |
| Decided: process | DEC-37, DEC-38, DEC-39, DEC-40, DEC-41, DEC-42, DEC-43; "Packaging is its own workstream" is OTW-13 |
| Non-goals | the charter's anti-goals; DEC-60 (auto-tracing, rejected), DEC-61 (un-instrumentation, deferred); the rest are DEC-23, DEC-26, DEC-32, DEC-36, DEC-41, DEC-42 |
| Proposals | preamble: DEC-14; 1: DEC-27; 2: DEC-25; 3 to 8: DEC-45 to DEC-50; 9: DEC-51 (rejected); 10: DEC-52; 11: DEC-53 |
| Questions for later | Q1 to Q16: DEC-1 to DEC-16; Q16's first answer, the `[re2]` hybrid: DEC-18 (superseded) |
| v0 lessons | `docs/evidence/v0-lessons-2026-10-07.md` |
| Why not logfire | DEC-15's body |
| Evidence | `docs/evidence/v1-design-evidence-2026-10-18.md` |
| Workstreams 0 to 11, 5b | OTW-2 to OTW-14, each body the section verbatim; "Done when" lines: AC-1 to AC-24; "Order": OTW-1 and the tasks' `deps` |
| Workstream 0's dated decisions | DEC-54 (Renovate), DEC-55 (auto-release), DEC-56 (CI); workstream 10's: DEC-57 (strict pins); 5b's: DEC-58 |
| Public API notes | `docs/evidence/v1-design-evidence-2026-10-18.md` |
| `TODO.md` triage | each row below, under `TODO.md` |
| Environment variables | DEC-59 |

## HANDOFF.md

| Section | Now |
|---|---|
| State: branches, docs, v1 status | `HANDOFF.md` facts (branches); the board (OTW-1); the decisions |
| State: decisions not obvious from the docs | DEC-40 (hosting), DEC-41 (`type_checking.py`), DEC-32 (logs are log records), DEC-57 (strict pins) |
| State: next steps | OTW-2 (at NOW) |
| State: v0 fixes of 2026-10-08 | commit `3ca5883`, described in the history doc; the sqlalchemy pin is DEC-62 |
| State: conda env | `CLAUDE.md` § Environment |
| How to verify | `CLAUDE.md` § Gate (the baseline and the manual checks); the suite's design is DEC-63 |
| Watch upstream | DEC-62, OTW-15 |
| TODO: confirmed and suite-found v0 bugs | fixed by v1 by design: the class leak and first-class-only spans (OTW-6, AC-11), the first engine only (OTW-4, AC-9), `CodeInfo` (OTW-5, AC-10), the timezone offset (OTW-11), nested spans through instances (OTW-3, AC-6), base64 padding (OTW-7, AC-12), the missing asyncio extension (OTW-4, AC-9; CI runs with and without the extras, DEC-56) |
| TODO: bugs and risks from reading the code | secrets in the startup log: ASK-17; Prometheus bound to localhost: OTW-12 (AC-19); never-crash holes: OTW-3 (AC-7); silent instrumentor failures: a trap on OTW-3; `x-userinfo` captured by default: DEC-2 |
| TODO: cleanup | OTW-18; `requires-python` and the hardcoded `requests` response headers are redone for v1 in OTW-13 and OTW-7 |
| TODO: bigger picture | OTW-2 (suite and CI), OTW-1 (v1) |

## TODO.md

| Item | Now |
|---|---|
| Testing (flake8, mypy, the example scripts) | `CLAUDE.md` § Gate, outside the gate; the stale `sqlalchemy2-stubs` note: OTW-18 |
| Publishing notes | `CLAUDE.md` § Release |
| Major refactor | OTW-1 |
| CICD the tests | OTW-2, DEC-56 |
| Console printing switch | DEC-34 |
| Multiple OTLP headers, per-signal collectors, `OTEL_COLLECTOR_*`, `OTEL_WRAPPER_*` names | DEC-59, DEC-28 (standard variables instead); gRPC: DEC-36; "multiple urls" is moot (one standard endpoint per signal) |
| `asyncio.iscoroutinefunction` | v0's uses: OTW-18 and a trap on OTW-2 (deprecated in 3.14, which CI runs); v1 uses `inspect` (3.12 floor, DEC-44) |
| Documentation, design decisions, the Prometheus trailing slash, `/metrics` vs `metrics` | OTW-16; the decisions are the records; the trailing slash is moot (OTW-12 uses `add_route`), and the path default is `/metrics` (DEC-59) |
| `__tracebackhide__` | OTW-3 |
| Request vs response header variables | DEC-2, OTW-7; the standard `OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_*` answer is in `README_v1.md` |
| `with` blocks for non-callable code | DEC-19 (`with otel:`), OTW-3 |
| Generators and context managers | DEC-22, OTW-10 |
| `varname` | DEC-64 (rejected) |
| Detect infinite recursion | OTW-17 |
| Won't do: instrument pydantic | DEC-65 |
| Won't do: sanitizer | DEC-66, superseded by DEC-58 (v1 scrubs) |
| Won't do: `tracemalloc` / `sys.settrace` | DEC-67 |
| Won't do: do-not-instrument marks, sampling ratio | DEC-68, relaxed by DEC-53 (`@otel.ignore`); sampling stays at the root, DEC-23 |
| Won't do: RED metrics | DEC-69 |

## Also changed at adoption

- `tests/`: comments and xfail reasons that cited `PLAN.md` or `HANDOFF.md` sections now cite the records, the
  evidence docs or "the v0 bug list" (the old `HANDOFF.md`'s TODO section, in the history doc). One test changed:
  `test_metrics_exclusion_also_hides_other_routes_containing_slash_metrics` is now `v0_specific`, since v1 excludes
  the exact path (AC-19) and AC-8 binds every plain test.
- Criteria AC-25 to AC-27 (exception status, escape hatches and import path, migration warnings) were added from
  their decisions; DEC-6, DEC-7 and DEC-39 are BUILT (nothing to build).
- `CLAUDE.md`: the kit block, the overrides of the global rules, the engine env, the gate (with the old "How to
  verify"), the release notes, and the feedback rule.

## Not migrated

The author's local, untracked notes (the evidence scripts, the Q15 spike, the scrubbing prototype, the full
ergonomics review with findings F1-F12, the v0 talk deck transcript) were never in the repo. The plan already
summarised what the design needs from them; the evidence scripts become canary tests in OTW-2.
