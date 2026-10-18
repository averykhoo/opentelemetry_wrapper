# Charter

LIVING. About a page (FRAMEWORK §3.1): the goals, the ranked principles, what is not in the plan and the mandates. It is
replaced only with the owner's confirmation. A story's `goals:` field names the goal ids below; ids are never
renumbered. The owner's since 2026-10-18 (DEC-72, DEC-73, DEC-76, DEC-77); the source is the owner's v0 talk
(`docs/evidence/v0-talk-deck-2026-10-18.md`).

## Purpose

Standardize telemetry across a team's Python services: the v0 talk's library "is only maintained to standardize our
internal logging, although it's available for anyone to use". It makes manual instrumentation almost effortless.
Manual instrumentation gives more than zero-effort auto-instrumentation: control over what is traced, nested spans
for the calls that matter, and application context such as the calling user. Without a collector, apps write
one-line JSON logs on stderr for a log shipper and serve metrics for Prometheus to scrape.

## Goals

| Id | Goal | How it is measured |
|---|---|---|
| G-1 | v1 builds directly on the OpenTelemetry SDK and the contrib instrumentors, and adds what neither provides: the `otel` decorator and context manager, instrumenting everything at once, and Prometheus scraping | AC-1, AC-2, AC-3, AC-5, AC-9, AC-17, AC-19, AC-20, AC-21, AC-25, AC-26 |
| G-2 | Hard to use incorrectly: idempotent (every public entry point can be called any number of times, from anywhere, and behaves as if called once, including methods reached through instances), and sync and async alike | AC-1, AC-6 |
| G-3 | Never crash the application: the wrapper is never the cause of an instrumented app failing. It fails small: when a failure can be confined to one value or one span, only that is dropped and the rest still goes out; if all else fails, it outputs no spans | AC-4, AC-7, AC-13 |
| G-4 | No telemetry of its own at runtime: warnings only at startup, decoration or instrumentation time, once each; our own entry points emit no spans; at runtime it reports only its own swallowed failures, on stderr (DEC-75) | AC-22 |
| G-5 | Introspection: spans name the right code (`co_qualname`, no `cls` heuristics, stable attributes) | AC-10 |
| G-6 | Class and dataclass support, including library classes (`otel(SortedList)`) | AC-11 |
| G-7 | Kubernetes support, as resource detectors | AC-14, AC-16 |
| G-8 | Machine-readable first: one-line JSON logs, JSON-encode anything. Human-readable second is the SDK's console exporter; no pretty console in 1.0 (DEC-34) | AC-18, AC-31 |
| G-9 | Telemetry carries no secrets by default: no arguments or return values on spans (DEC-26), a claim denylist, scrubbing on every exporter we build | AC-13, AC-15, AC-32, AC-33 |
| G-10 | Upgrades don't break users: v0 users migrate incrementally, and an OTel release reaches users only once our tests pass on it | AC-8, AC-23, AC-24, AC-27 |
| G-11 | Simple, idiomatic, succinct and pretty: far less code than the plain OTel SDK, and no SDK internals in user code | AC-28 |
| G-12 | Reasonable documented defaults: reasonable behaviour with minimal configuration, and every default written down | AC-29 |
| G-13 | Enriches telemetry with the application context available on each request: the calling user (`x-userinfo`, flattened) and upstream latency (`X-Envoy-Upstream-Service-Time` and the like), under OTel semantic-convention names; where the service runs is G-7 | AC-12, AC-30 |

## Ranked principles

When two goals pull apart, the higher one wins (DEC-72). The order follows the v0 talk's tiers, Safe, then
Unsurprising, then Helpful (DEC-77). G-1 is the whole of v1, so it is not ranked.

1. Never crash (G-3); the one sanctioned exception is `PYTHONWARNINGS=error` at startup (DEC-8).
2. Hard to use incorrectly (G-2).
3. No telemetry of its own (G-4).
4. Simple, idiomatic, succinct and pretty (G-11).
5. Reasonable documented defaults (G-12).
6. Application context on each request (G-13).
7. Introspection (G-5).
8. Class and dataclass support (G-6).
9. Kubernetes support (G-7).
10. Machine-readable first (G-8).
11. No secrets by default (G-9).
12. Upgrades don't break users (G-10): releases try to follow semver to signal compatibility.

**Example:** when scrubbing a value fails on export, nothing crashes, the record still goes out, and only that value
is withheld (DEC-74, AC-13).

## Not in the v1.0 plan

Not all of these are ruled out for good; they are not in the current plan (DEC-72).

- gRPC export: OTLP/HTTP only (DEC-36).
- Logs as spans (DEC-32).
- Per-span sampling (DEC-23).
- Global dataclass instrumentation (DEC-42).
- Auto-tracing a user's package (DEC-60).
- Un-instrumentation, except the per-test reset in the pytest plugin (DEC-61).
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
