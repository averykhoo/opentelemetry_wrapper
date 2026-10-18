---
type: Decision
id: DEC-15
title: 'Logfire is not a dependency: v1 builds on the plain OTel SDK (Q15)'
actor: owner
decided: 2026-10-17
session: 2026-10-18a
decision_status: BUILT
supersedes: [DEC-17]
imported_from: docs/evidence/decision-log-import-2026-10-18.md
aliases: [Q-15]
body_sha: sha256:852a648d8102397e5e40fbebd5f477a5cd1d5aa4895fea0e36375ffbdafdc9ec
tags: [architecture]
---

- **Q15. Is logfire still worth depending on?** *Decided 2026-10-17: no*, see "Why not logfire".

A spike built `configure` on the plain SDK (~300 lines, scrubbing included) and ran the same scenarios against it and
against `logfire.configure(send_to_logfire=False, console=False, ...)`, each in a fresh subprocess (logfire 5.1.1, SDK
1.44.0 / contrib 0.65b0). A second, independent review agreed (dropping it, ~80% confidence). All *verified* unless
noted.

What logfire did for v1, and the replacement:

- **Exporters:** for a generic collector logfire builds exactly `BatchSpanProcessor(OTLPSpanExporter())` and the log /
  metric equivalents; its retrying, disk-buffering exporters are only for Logfire's own backend. Replacement: the same
  three lines per signal.
- **Scrubbing:** the only real feature. Replacement: our own rules (workstream 5b), applied in an exporter wrapper (public
  API, off the caller thread).
- **Reconfigure before the first span** (its proxy providers): replaced by "configuration is final once built"
  (configuration rule 2).
- **Post-fork resource fix:** the SDK (1.44) does it itself. Its providers register `os.register_at_fork` hooks that
  re-run the process-dependent detectors (by default `service.instance.id`) and update existing tracers. Not run (no
  fork on Windows): our own detector's `process.pid` is not among the re-run detectors unless registered through the
  SDK's mechanism (workstream 6).
- **Flushing forked children:** logfire **replaces `os._exit` process-wide at `import logfire`** (atexit doesn't run
  in a forked `multiprocessing` child, which ends with `os._exit`). Replacement: a `multiprocessing.util.Finalize` with
  an exit priority, which `_bootstrap` runs before `os._exit` (read in CPython's source; covers `multiprocessing` only,
  not run).
- **Pretty console:** dropped for 1.0.

What it cost:

- **Per-span overhead** (BatchSpanProcessor + no-op exporter, 3 attributes): caller thread ~45 µs bare SDK, ~70 µs
  with our scrubbing wrapper, ~120 µs logfire without scrubbing, ~200-250 µs logfire default; total CPU ~2.8x ours.
  Logfire rebuilds every span as a dict, runs ~10 rewrite passes and scrubs, synchronously in `on_end`. (Windows; the
  ratios matter, not the absolute numbers.)
- **Import:** ~1 s / 546 modules vs ~0.5 s / 371 for the SDK + OTLP exporters (pydantic, rich, pygments, executing
  among them). Two `pytest11` plugins auto-loading in every project that installs us. Extra dependencies: logfire,
  executing, rich, pygments, markdown-it-py, mdurl.
- **Sampler semantics:** with `OTEL_TRACES_SAMPLER_ARG` < 1, logfire forces a parent-based ratio and ignores
  `OTEL_TRACES_SAMPLER` (`always_off` + `ARG=0.5` exported 95/200 spans); without ARG the SDK reads the sampler itself.
- **Telemetry changes:** `logfire.span_type` / `logfire.msg` / `logfire.level_num` / `logfire.json_schema` on stock
  spans (`logfire.msg` repeats the query string, unscrubbed), renamed HTTP spans, `service.version` from `git
  rev-parse` of the cwd, `instrument_fastapi` recording endpoint arguments **including dependency results**, and a log
  span of its own for an incoming `traceparent` unless `distributed_tracing=True`.
- **Maintenance:** ~200 releases, a 4 -> 5 major in Sept 2026 and 6.0 betas splitting the distribution
  (`logfire-sdk` + `logfire-cli`); upper caps on the OTel packages that lifted 18 days after SDK 1.45, so our users
  couldn't take a newer OTel release until logfire did; private attributes we'd have had to canary (`_initialized`).

What we now own instead: configure, the scrubber, swappable span and log sinks, the at-exit flush for forked children
and our own OTel pins (workstream 10), all on the SDK's public API (`opentelemetry.sdk._logs` is private-named, but
unavoidable either way).

*Imported at adoption (2026-10-18) from `PLAN.md` § Questions for later, `PLAN.md` § Why not logfire, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
