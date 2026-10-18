# Charter

LIVING. About a page (FRAMEWORK §3.1): the goals, the ranked principles, what is not in the plan and the mandates. It is
replaced only with the owner's confirmation. A story's `goals:` field names the goal ids below; ids are never
renumbered.

Reconstructed by an agent at adoption (2026-10-18, session 2026-10-18a) from the pre-adoption `PLAN.md` (§ Goal,
§ Principles, § Non-goals, now `docs/archive/PLAN.md`), the decisions and `CLAUDE.md`; **reviewed by the owner in
session 2026-10-18e (DEC-72)**, which made the principles a ranking and placed G-9 and G-10 in it; all ten stories
are confirmed. The purpose, G-11 and G-12 come from the owner's v0 talk (27 May 2024; summary in
`docs/evidence/v0-talk-deck-2026-10-18.md`), added in the same review (DEC-73).

## Purpose

Standardize telemetry across a team's Python services: the v0 talk's library "is only maintained to standardize our
internal logging, although it's available for anyone to use". It makes manual instrumentation almost effortless.
Manual instrumentation gives more than zero-effort auto-instrumentation: control over what is traced, nested spans
for the calls that matter, and application context such as the calling user. Here it takes a fraction of the plain
OTel SDK's code. Apps push OTLP to a collector named by one environment variable. Without a collector, they write
one-line JSON logs on stderr for a log shipper and serve metrics for Prometheus to scrape.

## Goals

| Id | Goal | How it is measured |
|---|---|---|
| G-1 | v1 builds directly on the OpenTelemetry SDK and the contrib instrumentors, plus what neither provides: the `otel` decorator / context manager, idempotent never-crash instrumentation, introspection, class support, Kubernetes resource detection, `x-userinfo` flattening, scrubbing, one-line JSON logs and Prometheus | the epic OTW-1 closes: every workstream's criteria pass and `README_v1.md`'s API works as written |
| G-2 | Idempotency: every public entry point can be called any number of times, from anywhere, and behaves as if called once, including methods reached through instances | AC-6; the strict xfails for nested spans through instances pass |
| G-3 | Never crash the application: the wrapper is never the cause of an instrumented app failing; if all else fails, it outputs no spans | AC-7, AC-25; no public entry point raises into the app in any test |
| G-4 | No telemetry of its own at runtime: warnings only at startup, decoration or instrumentation time, once each; our own entry points emit no spans | AC-22 |
| G-5 | Introspection: spans name the right code (`co_qualname`, no `cls` heuristics, stable attributes) | AC-10 |
| G-6 | Class and dataclass support, including library classes (`otel(SortedList)`) | AC-11 |
| G-7 | Kubernetes support, as resource detectors | AC-14, AC-16 |
| G-8 | Machine-readable first: one-line JSON logs, JSON-encode anything | AC-18 |
| G-9 | Telemetry carries no secrets by default: no arguments on spans, a claim denylist, scrubbing on every exporter we build | AC-12, AC-13, AC-15 |
| G-10 | Upgrades don't break users: v0 users migrate incrementally, and an OTel release reaches users only once our tests pass on it | AC-8, AC-23, AC-24, AC-27 |
| G-11 | Simple, idiomatic, succinct and pretty: far less code than the plain OTel SDK, and no SDK internals in user code | AC-28 |
| G-12 | Reasonable documented defaults: reasonable behaviour with minimal configuration, and every default written down | AC-29 |

## Ranked principles

When two goals pull apart, the higher one wins (DEC-72). The order is PLAN.md's, with never crash moved to the top and G-9 and G-10 placed by the owner.
G-11 and G-12 sit in the deck's own tier, "Unsurprising", after G-4 (the agent's placement, DEC-73). G-1 is the
whole of v1, so it is not ranked.

1. Never crash (G-3); the one sanctioned exception is `PYTHONWARNINGS=error` at startup (DEC-8). Whether the wrapper may report its own runtime failure, to be debuggable, is ASK-19.
2. Idempotency (G-2).
3. No telemetry of its own (G-4).
4. Simple, idiomatic, succinct and pretty (G-11).
5. Reasonable documented defaults (G-12).
6. Introspection (G-5).
7. Class and dataclass support (G-6).
8. Kubernetes support (G-7).
9. Machine-readable first (G-8).
10. No secrets by default (G-9).
11. Upgrades don't break users (G-10): versions stay pinned (DEC-57), and releases try to follow semver to signal
    compatibility.

**Example: scrubbing fails on export.** Never crash comes first, then the telemetry still goes out, then
secrets (DEC-72). AC-13 drops just the value that failed to scrub, notes it in `opentelemetry_wrapper.scrubbed` and
exports the rest of the record, so nothing crashes, the record goes out and no unscrubbed value leaves. Whether that
stands is ASK-18.

## Not in the v1.0 plan

Not all of these are ruled out for good; they are not in the current plan (DEC-72).

- gRPC export: OTLP/HTTP only (DEC-36).
- Logs as spans (DEC-32).
- Per-span sampling (DEC-23).
- Global dataclass instrumentation (DEC-42).
- Auto-tracing a user's package (DEC-60).
- Un-instrumentation, except the per-test reset in the pytest plugin (DEC-61).
- Recording function arguments or return values (DEC-26).
- Type-checking helpers in the public API (DEC-41): `type_checking.py` is useful and stays, in v0 for now.
- A dependency on logfire (DEC-15).

## Mandates

- Strict OTel pins, capped at the next minor (DEC-57): OTel has shipped breaking changes without warning.
- Hosting on GitHub and PyPI, CI on GitHub Actions (DEC-40).
- Automation must act by itself: the owner does not read CI results (DEC-54), which is why every push gets a CI
  watcher (DEC-72).
- The repo's working rules (conda env, scratch space, commits, pushes, CI watching): `CLAUDE.md`.

## Humans

One owner, Avery Khoo (`owner` in records), who gives all intent.
