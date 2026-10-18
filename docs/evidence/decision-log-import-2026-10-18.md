# Decision log imported at adoption

FROZEN 2026-10-18. The single-file log `context-engine decision import` read to create DEC-1 to DEC-69 (session 2026-10-18a). It was generated from `PLAN.md`, `HANDOFF.md` and `TODO.md` as committed at `24a0430`: each entry's body is a verbatim copy of the lines named in its last line. Statuses were set after the import (`docs/evidence/adoption-map-2026-10-18.md`). Never edit it: the records are the decisions now.

### Q-1 -- SQLAlchemy: `otel.instrument(sqlalchemy)` is global, `otel.instrument(engine)` is per engine (Q1) *(owner, 2026-10-07)*

- **Q1. SQLAlchemy engines created later.** *Decided 2026-10-07*, see workstream 2: `otel.instrument(sqlalchemy)`
  instruments globally (later engines included, `connect` spans on); `otel.instrument(engine)` instruments that engine
  only, without `connect` spans; the engine docs state this.

Two ways in (Q1, decided 2026-10-07), both idempotent and combinable:

- **`otel.instrument(sqlalchemy)`** (the module): global. Runs `SQLAlchemyInstrumentor().instrument()` once, which
  patches `create_engine` and `connect`, so every engine created **afterwards** is traced, with `connect` spans.
  Engines that already exist at that point aren't reached by upstream's patch (Evidence, e2), and there's no registry
  to find them, so document "instrument sqlalchemy before creating engines, or also pass the existing ones in".
- **`otel.instrument(engine)`**: that engine only, via a per-engine `EngineTracer`, tracked in a `WeakSet` (see
  evidence). Query spans, **no `connect` spans** (those come only from the global patch). Also handles
  `AsyncEngine` via `.sync_engine`. The README's engine section states this constraint.
- Both together: an engine created after the global call and also passed in gets a second `EngineTracer`, which
  doesn't duplicate spans (*verified*), and the `WeakSet` skips it anyway.

*Imported at adoption (2026-10-18) from `PLAN.md` § Questions for later, `PLAN.md` § Workstreams § 2. SQLAlchemy, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### Q-2 -- `x-userinfo`: record every claim except a denylist (Q2) *(owner, 2026-10-07)*

- **Q2. `x-userinfo` by default.** *Decided 2026-10-07*, see workstream 5: capture every claim except a denylist.
  Default denylist confirmed 2026-10-18 (`*token*,at_hash,c_hash,nonce,session_state,sid`; personal data captured
  unless added).

**Which claims (Q2, decided 2026-10-07): everything except a denylist.** Site-specific claims such as an
`employee_id` come through without being named anywhere. The denylist is
`OTEL_WRAPPER_HEADER_ATTRIBUTES_EXCLUDE`: comma-separated glob patterns matched against the flattened claim path
(`realm_access.roles`, `email`). Denied claims are **dropped** before they're recorded, not scrubbed with a marker.
Everything else is recorded as-is, so the scrubber lets all remaining `http.request.header.x-userinfo.*` attributes
through (a generic scrubber would mangle `auth_time`, `session_state` and `iss`; see Evidence). Default (confirmed
2026-10-18): credentials and session handles, `*token*,at_hash,c_hash,nonce,session_state,sid`. Personal data
(`email`, `name`) is captured unless added to the list; README says so.

*Imported at adoption (2026-10-18) from `PLAN.md` § Questions for later, `PLAN.md` § Workstreams § 5. Headers, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### Q-3 -- Exception status: ERROR on the innermost span; cancellation and interrupts stay unset (Q3) *(owner, 2026-10-18)*

- **Q3. Exception status.** *Decided 2026-10-18* as follows:

  | raised through the span | status | recorded |
  |---|---|---|
  | `Exception` subclasses, on the innermost span it passes through | ERROR | `exception` event with stack trace, `error.type` |
  | the same exception on each outer span | ERROR | `error.type` only (the stack trace is already on the inner span) |
  | `StopIteration` / `StopAsyncIteration` | unset | nothing (normal end of iteration) |
  | `GeneratorExit` (generator closed early) | unset | `opentelemetry_wrapper.closed_early = true` (workstream 7) |
  | `asyncio.CancelledError` | unset | `opentelemetry_wrapper.cancelled = true` |
  | `KeyboardInterrupt` | unset | `opentelemetry_wrapper.interrupted = true` |
  | `SystemExit` | ERROR if the code is non-zero, else unset | `process.exit.code` |

  `error.type` (fully qualified class name) is semconv's stable attribute for "this operation failed, and why".
  Cancellation is normal control flow (timeouts, client disconnects), so the inner spans aren't errors. Where a
  timeout causes it, `asyncio.timeout` turns it into `TimeoutError` at the scope that set the timeout, and that span
  is ERROR. "Already recorded" is a marker attribute set on the exception object (*verified*: exceptions accept
  attributes but not weak references; `error.type` and `process.exit.code` are semconv constants). Spans always end in `finally`, and exceptions are re-raised with a bare `raise`.

*Imported at adoption (2026-10-18) from `PLAN.md` § Questions for later, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### Q-4 -- `process.executable.name` is the base name of `sys.executable` (Q4) *(owner, 2026-10-18)*

- **Q4. `process.executable.name`.** *Decided 2026-10-18:* `os.path.basename(sys.executable)` (*verified*:
  `python.exe` on Windows, same as `psutil.Process().name()`), or `python` when that's empty (e.g. Pyodide). The
  fallback `service.name` is therefore `unknown_service:python.exe` on Windows; `README_v1.md` to match.

*Imported at adoption (2026-10-18) from `PLAN.md` § Questions for later, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### Q-5 -- `OTEL_SDK_DISABLED=true` also means `OTEL_WRAPPER_DISABLED` (Q5) *(owner, 2026-10-18)*

- **Q5. `OTEL_SDK_DISABLED=true`** (standard) also means `OTEL_WRAPPER_DISABLED`. *Decided 2026-10-18.*

*Imported at adoption (2026-10-18) from `PLAN.md` § Questions for later, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### Q-6 -- Baggage is never copied onto spans (Q6, obsolete with logfire) *(owner, 2026-10-17)*

- **Q6, Q7.** *Obsolete* (logfire's `add_baggage_to_attributes` and `LOGFIRE_*` env vars). Baggage is never copied
  onto spans.

*Imported at adoption (2026-10-18) from `PLAN.md` § Questions for later, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### Q-7 -- No `LOGFIRE_*` environment variables (Q7, obsolete with logfire) *(owner, 2026-10-17)*

- **Q6, Q7.** *Obsolete* (logfire's `add_baggage_to_attributes` and `LOGFIRE_*` env vars). Baggage is never copied
  onto spans.

*Imported at adoption (2026-10-18) from `PLAN.md` § Questions for later, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### Q-8 -- `PYTHONWARNINGS=error` may crash startup: accepted and documented (Q8) *(owner, 2026-10-18)*

- **Q8. `PYTHONWARNINGS=error` in production** turns our startup warnings into exceptions. Accept that as the one
  sanctioned exception to "never crash" (the user asked for it), or catch it? *Suggested:* accept and document. The
  author finds it defensible; the second opinion (2026-10-18) agrees, with high confidence: a startup crash is
  deterministic and happens before readiness, so a rollout halts without dropping traffic (true only because our
  warnings never fire lazily on a request); catching or downgrading would second-guess an explicit operator request,
  and `warnings.catch_warnings` isn't thread-safe. Mainstream libraries (requests, urllib3, SQLAlchemy, pydantic) use
  plain `warnings.warn`; the OTel SDK mostly uses `logging`, so proposal 7 is a deliberate departure. *Decided
  2026-10-18:* accepted, with proposal 7's amendments (emit after state is consistent; the pytest CI recipe).

*Imported at adoption (2026-10-18) from `PLAN.md` § Questions for later, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### Q-9 -- Only the log level may change after configuration is built (Q9) *(owner, 2026-10-18)*

- **Q9. Settings that may change after configuration is built:** the log level only. *Decided 2026-10-18.*

*Imported at adoption (2026-10-18) from `PLAN.md` § Questions for later, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### Q-10 -- Pytest plugin opt-in: requesting `otel_spans` / `otel_logs`, or an ini option (Q10) *(owner, 2026-10-18)*

- **Q10. Pytest plugin opt-in trigger:** requesting the `otel_spans` / `otel_logs` fixture, plus an ini option for
  whole-suite use. *Decided 2026-10-18.*

*Imported at adoption (2026-10-18) from `PLAN.md` § Questions for later, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### Q-11 -- `otel.instrument()` with no arguments: logging, requests, system metrics (Q11) *(owner, 2026-10-18)*

- **Q11. `otel.instrument()` with no arguments:** logging, requests, system metrics (the `[system-metrics]` extra);
  never apps, engines or SQLAlchemy. That's v0's `instrument_all()` set minus global dataclass instrumentation
  (dropped). *Decided 2026-10-18.*

*Imported at adoption (2026-10-18) from `PLAN.md` § Questions for later, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### Q-12 -- No Kubernetes API calls: labels and annotations from the Downward API (Q12) *(owner, 2026-10-18)*

- **Q12. The k8s API lookup** (pod labels/annotations, one HTTPS call at startup). *Verified 2026-10-18:* Falco's
  default stable ruleset has "Contact K8S API Server From Container" (any container connecting to the API server,
  minus a short image allowlist), and Elastic Security ships "Kubernetes Denied Service Account Request" (medium) for
  exactly the usual 403. CIS 5.1.5/5.1.6 recommend `automountServiceAccountToken: false`, so in hardened clusters
  there's no token at all. Nobody comparable reads the API from inside the application: the OTel Operator computes
  `service.*` in its admission webhook and injects Downward API env vars, `k8sattributes` runs in the Collector, and
  Datadog uses `fieldRef` labels or its admission controller (second review, from their docs and source). AWS's EKS
  detectors do call the API, but only when configured to. The alternative needs no API: a **Downward API volume**
  exposes the full `metadata.labels` / `metadata.annotations` maps as files (one `key="Go-quoted value"` per line,
  sorted, updated atomically), and single labels can be `fieldRef` env vars. *Suggested* (second review,
  medium-high confidence): **no API calls at all**, read labels/annotations from the volume (e.g.
  `OTEL_WRAPPER_PODINFO_DIR`, default `/etc/podinfo`) and ship the snippet in the README; an opt-in API lookup needs
  a Role + RoleBinding, the same manifest edit as adding the volume, for more risk. *Decided 2026-10-18:* no
  Kubernetes API calls; labels and annotations from the Downward API volume or `fieldRef` env vars (workstream 6).
  May be revisited as an explicit opt-in if a user asks.

*Imported at adoption (2026-10-18) from `PLAN.md` § Questions for later, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### Q-13 -- Log records keep the bare `record.funcName` (Q13) *(owner, 2026-10-18)*

- **Q13. Function name on log records:** accept the bare `record.funcName` the handler writes (`load_config`); a log
  record doesn't carry the qualified name, and rebuilding it means a stack walk per log call. *Decided 2026-10-18.*

*Imported at adoption (2026-10-18) from `PLAN.md` § Questions for later, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### Q-14 -- Proposals 3-8, 10 and 11 signed off as amended; 9 withdrawn (Q14) *(owner, 2026-10-08)*

- **Q14. Sign-off on proposals 3-11.** *Decided 2026-10-08:* 3-8, 10 and 11 signed off as amended; 9 withdrawn with
  logfire.

From the planning session and from an ergonomics review of `README_v1.md` (findings F1-F12; F1, the disabled-mode
part of F2, and F11 are already decided above). Items 1 and 2 have moved to "Decided"; the numbering is kept because
workstreams refer to it. Amendments from the 2026-10-07 review are marked *(review)*. The author signed off 3-8, 10
and 11 as written here, so they count as decided. 9 was a logfire option and went with logfire.

*Imported at adoption (2026-10-18) from `PLAN.md` § Proposals, `PLAN.md` § Questions for later, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### Q-15 -- Logfire is not a dependency: v1 builds on the plain OTel SDK (Q15) *(owner, 2026-10-17)*

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

### Q-16 -- Scrubbing engine: stdlib `re` by default, `[hyperscan]` as the optional fast engine (Q16) *(owner, 2026-10-18)*

- **Q16. Scrubbing engine** (benchmark in workstream 5b). *Decided 2026-10-18:* stdlib `re` by default (factored
  alternation, no groups, 32-character prefilter), plus an optional fast engine. First decided as an `[re2]` hybrid
  (`re` for short strings, `re2` for long ones: same speed on attributes, 10-20x faster on log bodies), then replaced
  by `[hyperscan]` (below). Greenery not at runtime; `interegular` as a test-time lint (dev dependency).
  Follow-ups measured the same day (µs per call; 10 attributes / 2 KB "password" body / 2 KB secret body / argv /
  2 KB adversarial body):

  | engine | attrs | "password" | secret | argv | adversarial |
  |---|--:|--:|--:|--:|--:|
  | `re` default | 88 | 421 | 388 | 47 | 257 |
  | `re2` hybrid | 100 | 17 | 108 | 69 | 169 |
  | Hyperscan alone | 81 | 14 | 40 | 74 | 137 |

  - **Possessive quantifiers / atomic groups** (an `re`-engine rewrite, no change in any match): 30-45% *slower*
    under `re`, even on the adversarial input, because CPython compiles a plain character-class run to a
    specialised opcode and the possessive form goes through a generic loop; neutral under `regex`. Not used.
  - **Hyperscan** (`hyperscan` 0.9.1 on PyPI, MIT, statically links Vectorscan, the open-source fork; wheels for
    Linux, macOS and Windows): every rule expressible, output identical to `re` on every test including non-ASCII.
    Its fixed cost per call is the lowest (2.5 µs vs `re` 4.0, `re2` 6.8), so it needs no hybrid. Engine notes: it
    reports every end offset and only the leftmost start, so the engine takes the leftmost start, lets `re` decide
    the exact span, rule and post-match check, and rescans from there; ASCII `\w`/`\s` are widened so it can only
    over-report; database compile ~0.8 s, once; one scratch space per thread.
  - *Decided 2026-10-18:* `[hyperscan]` is the optional fast engine, **replacing `[re2]`** (faster everywhere except
    argv-sized strings, one engine fewer to maintain); the engine is picked once at configure time from what's
    installed, falling back to stdlib `re`. There's no official Vectorscan package on PyPI; `hyperscan`
    (darvid/python-hyperscan) is the de facto binding, maintained by one person, which is acceptable for an optional
    extra with a fallback. Keeping `[re2]` as well adds little: *verified* (PyPI, cp312), `hyperscan` has wheels for
    Linux x86_64/aarch64 on both glibc (manylinux2014) and musl (Alpine), macOS and Windows amd64, while `google-re2`
    has no musl wheels and only adds win32 / win_arm64.

*Imported at adoption (2026-10-18) from `PLAN.md` § Questions for later, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-17 -- v1 rebuilds on the Logfire SDK *(owner, 2026-10-04)* -- **SUPERSEDED by Q-15**

Started 2026-10-04, last updated 2026-10-18. This is the design for the next major version ("v1"; the current code is
v0), written to be reviewed cold. It started as a rebuild on the Logfire SDK; the 2026-10-17 spike (Q15) showed v1
used little of it, and logfire was dropped (see "Why not logfire").

- [ ] v1 rebuild: **design in `PLAN.md`**. Originally planned on the Logfire SDK; since 2026-10-17 on the plain OTel
  SDK + contrib instrumentors (`PLAN.md` "Why not logfire").

*Imported at adoption (2026-10-18) from `HANDOFF.md` § TODO § Bigger picture, `PLAN.md` § the preamble, as committed at `24a0430`; now at `docs/archive/PLAN.md`, `docs/evidence/history-to-2026-10-18.md`.*

### DEC-18 -- Scrubbing's optional fast engine is an `[re2]` hybrid *(owner, 2026-10-18)* -- **SUPERSEDED by Q-16**

- **Q16. Scrubbing engine** (benchmark in workstream 5b). *Decided 2026-10-18:* stdlib `re` by default (factored
  alternation, no groups, 32-character prefilter), plus an optional fast engine. First decided as an `[re2]` hybrid
  (`re` for short strings, `re2` for long ones: same speed on attributes, 10-20x faster on log bodies), then replaced
  by `[hyperscan]` (below). Greenery not at runtime; `interegular` as a test-time lint (dev dependency).

*Imported at adoption (2026-10-18) from `PLAN.md` § Questions for later, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-19 -- One `otel` object decorates and opens spans; integrations use `otel.instrument(x)` *(owner, 2026-10-08)*

- **One `otel` object** that decorates (functions, methods, classes, dataclasses, generators, context managers) and
  opens spans (`with otel:`, `with otel('name'):`). Libraries and apps use **`otel.instrument(x)`**, and
  `otel.instrument()` with no arguments instruments everything global that's installed (v0's `instrument_all()`).
  Bare `otel(app)` was rejected: unreadable in review, and the supported set is undiscoverable.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-20 -- Configured `otel(...)` objects are immutable and stateless; span state lives in a `ContextVar` *(owner, 2026-10-08)*

- **Configured objects (`otel(name=...)`) are immutable and stateless**; per-entry span state lives in a `ContextVar`.
  v0's sketch kept a span stack on the shared object, which breaks under concurrency (see "Public API notes").

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-21 -- No "blocked" behaviour: code info is looked up at run time from the target *(owner, 2026-10-08)*

- **No "blocked" behaviour.** It existed because code info cached on the object could be reused for the wrong target.
  Instead, code info is looked up at run time from the target: the decorated function's code object at decoration
  time, the caller's frame (`f_code`, `f_lineno`) at `__enter__`, cached by code object + line, never stored on `otel`.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-22 -- Generators and context managers: one span each, as prototyped *(owner, 2026-10-08)*

- **Generators and context managers** as in workstream 7 (author approved the prototype).

Design (prototyped locally with the plain OTel tracer; all four cases behaved as described):

- **Generators**: one span from the first `next()` until exhausted, closed or garbage-collected, parented to the context
  where the generator was *created*. It is current only while the generator body runs: attach before each
  `send`/`throw`, detach before handing the value back. Forward `send`/`throw`/`close`; `GeneratorExit` ->
  `closed_early`; exceptions -> ERROR. Wall-clock duration includes time suspended, so also record yield count and
  active time (prototype: 468 ms wall, 159 ms active, 3 yields). Same for async generators with `asend`/`athrow`/`aclose`.
- **`@contextmanager` / `@asynccontextmanager` functions**: detect them regardless of decorator order. Every
  `contextmanager`-decorated function shares one `__code__` object (the `helper` closure) and exposes the generator
  function as `__wrapped__`, so `f.__code__ is contextmanager(lambda: (yield)).__code__` is a reliable check. Re-wrap as
  `contextmanager(spanned(f.__wrapped__))`: the span covers enter -> body -> exit and **stays current across the
  single yield**, so the `with` body is a child. If `@otel` sits underneath, we only see a generator function and
  apply generator semantics (correct duration, body not a child). Document "put `@otel` on top".
- **Class-based context managers** (class instrumentation): one span per `__enter__` -> `__exit__` instead of two
  method spans, current in between. Keep a per-instance stack of (span, token) (weakref-keyed, for re-entrant objects).
  If `__exit__` runs in a different context, OTel's `detach` logs instead of raising, so it never crashes.
- Caveat: abandoned generators are closed (span ended) promptly on CPython by refcounting, but only at GC on PyPy.
- The wrapper of a generator function must itself be a generator function (and of an async generator function, an
  async generator function), not a function returning a proxy object. Otherwise `inspect.isgeneratorfunction` is
  false and FastAPI injects the generator object instead of treating a `yield` dependency as a context manager;
  pytest `yield` fixtures break the same way.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, `PLAN.md` § Workstreams § 7. Generators and context managers, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-23 -- No per-span sampling: sampling is decided at the root span through the standard env vars *(owner, 2026-10-08)*

- **No per-span sampling.** Sampling is decided at the root span, via the standard `OTEL_TRACES_SAMPLER` /
  `OTEL_TRACES_SAMPLER_ARG`, which the SDK reads itself (all standard samplers; *verified*: `always_off` exports 0,
  `always_on` with an ARG exports everything).

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-24 -- `OTEL_WRAPPER_DISABLED` means no telemetry at all *(owner, 2026-10-08)*

- **`OTEL_WRAPPER_DISABLED`** means no telemetry at all, for test envs with nowhere to export, where only stack traces
  matter: decorators return the target unchanged (no wrapper frames in tracebacks), `otel.instrument` is a no-op, and
  `with otel as span` yields OTel's standard `NonRecordingSpan` (`trace.INVALID_SPAN`). *Verified:* every method
  works and records nothing, and exceptions propagate untouched. It's read at decoration time, so wrappers that
  already exist also check it at call time (e.g. a test that sets it after import).

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-25 -- Our spans come from the OTel tracer; the exposed span type is OTel's `trace.Span` (proposal 2) *(owner, 2026-10-08)*

- **Our spans come from the OTel tracer** (`trace.get_tracer(...)`), and the exposed span type is OTel's `trace.Span`
  (was proposal 2), the same in enabled and disabled mode.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-26 -- No arguments or return values on spans *(owner, 2026-10-08)*

- **No arguments or return values on spans.** PII, payload size, and parameter names colliding with real attribute
  keys. (*Verified* counter-example: `logfire.instrument` records every argument by default as a top-level attribute
  named after the parameter.) Users add what they need via `attributes={...}` or the span.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-27 -- Configuration: implicit and explicit together, final once built (proposal 1) *(owner, 2026-10-08)*

- **Configuration: implicit and explicit together** (was proposal 1, with the review's changes; rule 2 changed
  2026-10-17 with the move to the plain SDK).
  1. Decorating never configures anything, so import order doesn't matter. The first span configures from env vars,
     **only if nothing has configured yet** (tracked in our own state, under a lock so "configure if not yet
     configured" is atomic across threads). `otel.instrument(...)` configures **eagerly**, since nearly every app
     calls it at startup; that keeps configuration (file reads, exporter threads, a port bind) off the first request
     and out of the event loop.
  2. `otel.configure(...)` takes a typed signature (not "env var names in lowercase"). Explicit > env > default. Same
     arguments again (normalised, env-derived defaults included): no-op. **Configuration is final once built** (by
     `otel.configure`, `otel.instrument` or the first span): a later call with different arguments warns once and is
     ignored, except for the log level (Q9). So `otel.configure(...)` goes before `otel.instrument(...)`, or
     configuration comes from env vars alone; the README says so. Reasons: the SDK's global providers can be set only
     once (replacing them means proxy providers for all three signals, ~800 lines in logfire), a Prometheus port can't
     be bound twice, and a second `PrometheusMetricReader` collides in the global registry. Instrumenting before
     configuring loses nothing: *verified*, contrib instrumentors created before any provider get the API's
     `ProxyTracer`, which picks up the provider set later.
  3. Test capture survives configuration: a pytest plugin (`pytest11` entry point, loads before app code) registers
     in-memory span and log processors **with us** (the SDK's `InMemorySpanExporter` / `InMemoryLogRecordExporter`,
     behind the same scrubbing wrapper as the real exporters, so tests see what would be exported). Because a
     `pytest11` plugin loads in **every** project that installs the package, auto-loading is passive: it only
     registers the `otel_spans` / `otel_logs` fixtures (reset per test). Exporters and Prometheus are switched off
     only when a test opts in (Q10), by swapping the sinks of our own span and log processors (public SDK API; works
     after configuration). Document `-p no:opentelemetry_wrapper`.
  4. `otel.config`: a read-only view of the effective configuration, secrets redacted (v0 logged its config and
     leaked the OTLP auth header).
  5. **Someone else configured first** (the app called `logfire.configure()`, or set its own provider): *verified*
     (second review, 2026-10-17), the SDK refuses a second `set_tracer_provider` with a log line, so either order gives two
     pipelines, never a crash. Policy: warn once; if the existing provider is an SDK `TracerProvider` /
     `LoggerProvider`, attach our processors to it, otherwise leave it alone.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-28 -- Exporters are chosen from the standard `OTEL_*` env vars *(owner, 2026-10-08)*

- **Exporters from the standard env vars:** `OTEL_EXPORTER_OTLP_{,TRACES_,METRICS_,LOGS_}ENDPOINT`, `..._HEADERS`,
  `..._TIMEOUT`, and `OTEL_{TRACES,METRICS,LOGS}_EXPORTER` (`otlp`, `console`, `none`). The OTLP exporters read most of
  these themselves; we only decide which exporters to build.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-29 -- `service.name` follows semconv; v0's readable name moves to `opentelemetry_wrapper.instance.label` *(owner, 2026-10-08)*

- **`service.name` follows semconv** (the workload name); breaking existing dashboards is accepted. v0's readable
  `ns/workload/pod` or `user@host:main.py` string moves to `opentelemetry_wrapper.instance.label`, and
  `service.instance.id` stays a per-process UUID (workstream 6, "Service identity").

**Service identity: strict semconv names, v0's readable label kept separately.**

- `service.name`: `OTEL_SERVICE_NAME` (or `service.name` in `OTEL_RESOURCE_ATTRIBUTES`) if set; otherwise the
  semconv k8s derivation (annotation, `app.kubernetes.io/*` labels, workload name from an unambiguous pod-name
  shape); otherwise `unknown_service:<process.executable.name>`.
- `service.namespace`: the k8s namespace.
- `service.instance.id`: keep the SDK's random UUID per process. Stable semconv recommends UUIDs, treats pod/namespace
  as data to expose in other attributes, and wants one id per worker process. The k8s-derived
  `<ns>.<pod>.<container>` is the same for every uvicorn/gunicorn worker in a container, so it breaks uniqueness. Use
  it only if the annotation sets it explicitly.
- **`opentelemetry_wrapper.instance.label`** (resource attribute, ours): v0's string, `<namespace>/<workload>/<pod>` in
  k8s, `<user>@<host.domain>:<main.py>` elsewhere. Every part is *also* in its own semconv attribute (`k8s.*`,
  `process.owner`, `host.name`, `process.command_args`); the label is the readable one-glance version.
- It shows up as a resource attribute on every span and log (searchable in Tempo/Grafana etc.) and in Prometheus as a
  `target_info` label (verified with the pull exporter). With OTLP push, Prometheus derives `job` from
  `service.namespace/service.name` and `instance` from `service.instance.id`, per the OTel spec (not verified here).

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, `PLAN.md` § Workstreams § 6. Resource detectors, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-30 -- Record the full command line as `process.command_args`, plus the Python environment *(owner, 2026-10-08)*

- **Full command line** recorded as `process.command_args` (from `sys.orig_argv`, sanitized), plus our
  `opentelemetry_wrapper.python.environment` (conda / venv / system / pyodide / frozen), so it's clear which
  interpreter ran the process.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-31 -- Stable semconv `code.*` keys everywhere *(owner, 2026-10-08)*

- **Stable semconv `code.*` keys** everywhere (workstream 3).

The `CodeInfo` rewrite in `HANDOFF.md`. Emit stable `code.*` keys, using the constants in
`opentelemetry.semconv.attributes.code_attributes` rather than string literals; put extras (wrapper chain,
`is_class`, end line) under our own prefix, e.g. `opentelemetry_wrapper.code.*`. Auto-name `with otel:` blocks from
the call site (see proposal 5 for the naming).

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, `PLAN.md` § Workstreams § 3. Introspection, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-32 -- Logs are real OTel log records, never spans *(owner, 2026-10-08)*

- **Logs are real OTel log records**, never spans: a handler on the root logger feeding a `LoggerProvider` we always
  install (exporter only when an endpoint is set). The handler is the one from `opentelemetry-instrumentation-logging`
  (decided 2026-10-17): *verified*, the SDK's own `LoggingHandler` emits a `DeprecationWarning` at construction in
  1.44 pointing there. A record logged inside a span carries that span's `trace_id` / `span_id` (that's how backends
  show it on the span: it's correlated, not a child in the span tree), `extra={...}` becomes attributes, and the code
  location uses the stable keys (*verified* with the SDK handler; re-check with the contrib one). Logs are **not**
  affected by head sampling: at a 0% ratio the spans are dropped but every log record is still exported (with
  `trace_flags=0`), and a log outside any span has no trace ids. Both span and log capture are tested through the same
  pytest plugin.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-33 -- Resource precedence: our detectors < `OTEL_SERVICE_NAME` / `OTEL_RESOURCE_ATTRIBUTES` < explicit arguments *(owner, 2026-10-17)*

- **Resource precedence:** our detectors (guesses) < `OTEL_SERVICE_NAME` / `OTEL_RESOURCE_ATTRIBUTES` < explicit
  `otel.configure(...)` arguments. *Verified* in the spike (`Resource.create()`, then our detectors, then
  `OTELResourceDetector().detect()`, then the explicit attributes): `OTEL_SERVICE_NAME` beats a k8s guess, and an
  explicit `service_name` beats `OTEL_SERVICE_NAME`. Test: `OTEL_SERVICE_NAME` wins in k8s.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-34 -- Console: one-line JSON logs on stderr; no pretty console in 1.0 *(owner, 2026-10-17)*

- **Console:** one-line JSON logs on stderr (`OTEL_WRAPPER_LOG_FORMAT=json|off`). No pretty console in 1.0 (decided
  2026-10-17; it was logfire's); for local debugging of spans, `OTEL_TRACES_EXPORTER=console` gives the SDK's
  `ConsoleSpanExporter`.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-35 -- Pydantic 2 only, optional, never imported by us *(owner, 2026-10-08)*

- **Pydantic 2 only, optional, never imported by us.** Pydantic models can only exist if the app imported pydantic, so
  the encoder checks `sys.modules.get('pydantic')` when it meets an unknown object instead of importing it (~120 ms)
  at startup. If it's v2, use encoders for its real types (`isinstance` / type lookup, no duck typing), e.g.
  `BaseModel` -> `model_dump(mode="json")`. Pydantic 1 counts as absent (warn once); `pydantic.v1` models get the
  generic encoder. FastAPI 0.142 requires `pydantic>=2.9` anyway. v0 keeps supporting both.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-36 -- OTLP/HTTP only: gRPC export dropped *(owner, 2026-10-08)*

- **gRPC export dropped** for now: OTLP/HTTP only (collectors listen on 4318 by default), which avoids `grpcio`. A
  `[grpc]` extra can come later if someone needs it.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-37 -- Rollout: v1 ships beside v0, becomes the default, then v0 is deleted after one release of aliases *(owner, 2026-10-08)*

- **Rollout: side by side.** v1 ships next to v0 in the same package until it's proven safe against `tests/v0`, then
  becomes the default and v0 is deleted. For one release after that, v0's entry points (`instrument_decorate`,
  `instrument_all`, `instrument_fastapi_app`, `instrument_sqlalchemy_engine`, ...) stay as thin deprecated aliases
  over v1, so users can migrate incrementally.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-38 -- "Proven safe" is one command: `tests/v0` under `OTW_IMPL=v0|v1` *(owner, 2026-10-08)*

- **"Proven safe" is one command.** The v0 tests call v0 names directly, so the harness gets a small adapter
  (`decorate` / `instrument_app` / `instrument_engine` / `setup`) selected by `OTW_IMPL=v0|v1`; plain tests must pass
  under both, `v0_specific` tests are v0-only. Commit the suite first so the baseline is pinned.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-39 -- Settle the shape of v1 before writing its tests *(owner, 2026-10-08)*

- **Tests:** settle the shape of v1 before writing its tests. The v0 characterization suite exists now.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-40 -- Hosting stays on GitHub and PyPI; CI is GitHub Actions *(owner, 2026-10-08)*

- **Hosting stays on GitHub** (+ PyPI). The v0 deck's move to GitLab + Artifactory is not happening. CI is GitHub
  Actions.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-41 -- `type_checking.py` stays in the repo, unchanged, outside v1's API *(owner, 2026-10-08)*

- **`type_checking.py` stays in the repo, unchanged** (it works), but v1 doesn't import or export it, as v0 already
  doesn't.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-42 -- Global dataclass instrumentation is dropped *(owner, 2026-10-08)*

- **Global dataclass instrumentation is dropped** (v0's `instrument_dataclasses()`): patching `dataclasses.dataclass`
  depends on import order, contradicting configuration rule 1, and its `__getattribute__` patching is behind several
  v0 bugs. `@otel` on the dataclass covers the real use.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-43 -- Logging options come from env vars and `otel.configure(...)` only *(owner, 2026-10-08)*

- **Logging options** come from env vars and `otel.configure(...)` only, not `otel.instrument(logging, level=...)`:
  per-call options would make "instrument twice = once" ambiguous.

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-44 -- v1 requires Python 3.12 or later *(owner, 2026-10-08)*

one-line JSON logs and Prometheus. Python floor: **3.12** (the SDK itself needs >= 3.10).

- `requires-python = ">=3.12"` (v0's `">3.8.0"` also excluded 3.8.0 by accident). Side-by-side means v0 users get the
  3.12 floor in that release: make it a minor-version bump with a clear note, and the v0 deletion 1.0.0.

*Imported at adoption (2026-10-18) from `PLAN.md` § Goal, `PLAN.md` § Workstreams § 10. Packaging, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-45 -- Escape hatches: `otel.span`, `otel.trace_id`, `otel.span_id` (proposal 3) *(owner + agent, 2026-10-08)*

3. **Escape hatches** (F4): `otel.span` (current span; a no-op span when there is none, never `None`), `otel.trace_id`
   / `otel.span_id` (hex strings, e.g. to return in an HTTP 500 body; all zeros when there's no span or telemetry is
   disabled). Document `record_exception`, `add_event`, marking a span failed without raising, and stdlib `logging`
   `extra={...}` (*verified*: becomes attributes on the log record).

*Imported at adoption (2026-10-18) from `PLAN.md` § Proposals, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-46 -- Import path: `from opentelemetry_wrapper import otel` (proposal 4) *(owner + agent, 2026-10-08)*

4. **Import path** (F5): `from opentelemetry_wrapper import otel`, so users change imports once, not twice. *Verified:*
   nothing in v0's `__all__` is called `otel`. `opentelemetry_wrapper.v1` stays the implementation module.

*Imported at adoption (2026-10-18) from `PLAN.md` § Proposals, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-47 -- Unnamed `with otel:` blocks are named after the enclosing function (proposal 5) *(owner + agent, 2026-10-08)*

5. **Unnamed `with otel:` blocks** (F6): name them after the enclosing function, not `load_config:42`. A span name
   containing a line number changes whenever the file is edited, breaking dashboards and alerts. The line stays in
   `code.line.number`. Nudge users toward `with otel('name'):`. *(review)* Use module + `co_qualname`
   (`app.config.load_config`, `app.config.<module>`), the same shape as decorated functions, so same-named functions
   in different modules don't collide. The name cache is keyed by (code object, line), so when a second unnamed block
   shows up in the same function, warn once ("two unnamed blocks in X; name them").

*Imported at adoption (2026-10-18) from `PLAN.md` § Proposals, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-48 -- `@property` on top, `@otel` underneath (proposal 6) *(owner + agent, 2026-10-08)*

6. **Decorator order with `@property`** (F7): document `@property` on top, `@otel` underneath. *Verified:* mypy
   rejects *any* decorator above `@property` (`[prop-decorator]`). This is a mypy limitation; Python accepts both
   orders, and v1 handles both at runtime.

*Imported at adoption (2026-10-18) from `PLAN.md` § Proposals, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-49 -- One `OtelWrapperWarning` through `warnings.warn`, on startup paths only (proposal 7) *(owner + agent, 2026-10-08)*

7. **Warning channel** (F8): one `OtelWrapperWarning(UserWarning)` via `warnings.warn(..., stacklevel=2)`, only on
   startup paths (decoration, `instrument`, `configure`, env var parsing), never through `logging` and never per call.
   The default filter shows each message once per call site, and an error filter in CI turns misuse into a test
   failure without ever crashing production. The CI recipe is pytest's `filterwarnings =
   error::opentelemetry_wrapper.OtelWrapperWarning` (ini) or `pytest -W error::...`, **not** `python -W
   error::opentelemetry_wrapper.OtelWrapperWarning` / `PYTHONWARNINGS=...`: *verified* (2026-10-18), the interpreter
   parses `-W` before `site` adds site-packages, so a category from an installed package prints `Invalid -W option
   ignored` and the run exits 0. *(review)* Call `warnings.warn` outside our own `try`/`except` blocks so an
   error-filtered warning isn't swallowed, and only once state is consistent (collect warnings during `configure` /
   decoration and emit them at the end), so an error filter can't leave configuration half-built. Whether
   `PYTHONWARNINGS=error` in production may crash at startup is Q8.

*Imported at adoption (2026-10-18) from `PLAN.md` § Proposals, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-50 -- `@otel()` and `with otel():` mean the same as `@otel` and `with otel:` (proposal 8) *(owner + agent, 2026-10-08)*

8. **`@otel()` and `with otel():`** (F10) mean the same as `@otel` / `with otel:`, silently (v0's sketch warned).

*Imported at adoption (2026-10-18) from `PLAN.md` § Proposals, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-51 -- Logfire's `distributed_tracing=True` option (proposal 9) *(owner, 2026-10-17)*

9. *Withdrawn with logfire.* It was logfire's `distributed_tracing=True`. On the plain SDK an incoming `traceparent`
   is simply continued (the default W3C propagator), *verified*: same trace id, no warning. (Logfire without the option
   also exported a log span of its own, "Found propagated trace context".)

*Imported at adoption (2026-10-18) from `PLAN.md` § Proposals, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-52 -- Migration from v0: old env var names for one release, a port-4317 warning, Upgrading notes (proposal 10) *(owner + agent, 2026-10-08)*

10. **Migration** (F9):
    - old env var names read for one release, with a startup warning. *(review)* Except `OTEL_LOG_LEVEL`: it's the
      SDK's own variable, so honouring it would keep the collision alive. Warn when it's set and
      `OTEL_WRAPPER_LOG_LEVEL` isn't, but don't use it;
    - warn at startup when the OTLP endpoint uses port `4317` or `grpc://` (v0's README example was `:4317`; an HTTP
      exporter posting to a gRPC port fails on every batch, visible only in the SDK's internal logger). *(review)*
      Same warning for `OTEL_EXPORTER_OTLP_PROTOCOL=grpc` and `OTEL_EXPORTER_OTLP_INSECURE`, both of which v0 users
      may have set;
    - *(review)* `OTEL_EXPORTER_OTLP_HEADERS` values are URL-decoded (*verified*, `opentelemetry/util/re.py`), so
      v0's `Authorization: Basic abc==` becomes `Authorization=Basic%20abc==` (the `=` padding is fine: it splits on
      the first `=`). Say so in "Upgrading";
    - keep v0's Downward API recipe for pods without a service account, rewritten for
      `OTEL_RESOURCE_ATTRIBUTES=service.namespace=$(POD_NAMESPACE)`;
    - list the dropped `async ` span-name prefix under "Upgrading".

*Imported at adoption (2026-10-18) from `PLAN.md` § Proposals, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-53 -- Classes span methods and constructors, selected dunders, `@otel.ignore`; `attributes` as a dict (proposal 11) *(owner + agent, 2026-10-08)*

11. **Smaller points** (F12):
    - instrumenting a class spans methods and constructors by default, properties opt-in
      (`@otel(properties=True)`), since a property read in a loop is the noisiest thing in the library;
    - *(review)* dunders: only `__new__`, `__init__`, `__post_init__`, `__call__`, `__enter__`/`__exit__` (and async
      versions). Never `__repr__`, `__eq__`, `__hash__` etc.: they're noisy and can recurse (a span attribute that
      calls `repr(self)`);
    - *(review)* a per-method opt-out for hot methods inside an instrumented class, e.g. `@otel.ignore`;
    - document the standard sampler variables (`OTEL_TRACES_SAMPLER=parentbased_traceidratio` +
      `OTEL_TRACES_SAMPLER_ARG=0.1` for 10%);
    - `attributes={...}` as a dict (not `**kwargs`), so it can't collide with options.

*Imported at adoption (2026-10-18) from `PLAN.md` § Proposals, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-54 -- Upstream OTel bumps: Renovate PRs that auto-merge only when CI passes *(owner, 2026-10-18)*

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

### DEC-55 -- Dependency-only merges are released automatically as a patch release to PyPI *(owner, 2026-10-18)*

- **Auto-release of dependency-only bumps** (decided 2026-10-18): when such a PR merges, a release workflow bumps the
  patch version and publishes to PyPI (trusted publishing, no stored token). Only for merges that change nothing but
  dependency specifiers; anything else is released by hand. A patch release (not `.postN`) is the conventional
  signal, and both are picked up by default. If a bump should ever be opt-in, publish it as a pre-release (`rcN` /
  `.devN`), which pip skips unless asked (`--pre` or an explicit pre-release specifier); *verified* with `packaging`'s
  filtering. Local versions (`+tag`) can't be uploaded to PyPI.

*Imported at adoption (2026-10-18) from `PLAN.md` § Workstreams § 0. Tests, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-56 -- CI: GitHub Actions on push and pull requests, Python 3.12-3.14, with and without extras *(owner, 2026-10-18)*

- **CI:** GitHub Actions on push and on pull requests (none yet; `.github/workflows/` doesn't exist). Kept
  (decided 2026-10-18): Renovate's auto-merge depends on it, and whoever pushes watches the run. Matrix: Python 3.12 / 3.13 / 3.14 × with and
  without the optional extras, so "optional at call time" is actually exercised. Keep the steps in a script so the
  workflow file stays thin.

*Imported at adoption (2026-10-18) from `PLAN.md` § Workstreams § 0. Tests, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-57 -- Strict OTel pins, capped at the next minor *(owner, 2026-10-18)*

- **Strict OTel pins, as in v0** (decided 2026-10-18): OTel has shipped breaking changes without warning, twice
  during v0's development. Cap the SDK family at the next minor (e.g. `opentelemetry-sdk>=1.44,<1.45`) and pin the
  contrib packages to the matching `0.XbY` window (they release in lockstep). Renovate's auto-merged bump PRs
  (workstream 0) and the canaries decide when a cap moves; the difference from logfire's caps is that we set the
  pace.

*Imported at adoption (2026-10-18) from `PLAN.md` § Workstreams § 10. Packaging, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-58 -- v1 scrubs exported telemetry with its own rules *(owner, 2026-10-18)*

Our own rules, designed from examples (2026-10-18), not copied from logfire's list. Applied in wrappers around every
exporter we build (spans: attributes, event and link attributes; logs: attributes and body; the in-memory test
exporters too), on the exporter thread, so the cost stays off the caller's path; also to the stderr JSON logs
(decided 2026-10-17) and, via `scrub_argv`, to `process.command_args`. Defence in depth: the primary controls remain
"no arguments on spans" and the header denylist. Anything not behind our wrappers (a user's own processors) is
unscrubbed; README says so.

| won't do: sanitizer, sampling | sampling: the SDK's standard samplers. Sanitizer: now done after all (workstream 5b), because spans and logs from instrumentors carry headers, URLs and extras we don't control |

*Imported at adoption (2026-10-18) from `PLAN.md` § Workstreams § 5b. Scrubbing, `PLAN.md` § `TODO.md` triage against the rebuild, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-59 -- Environment variables: standard names where they exist, `OTEL_WRAPPER_*` for ours *(owner, 2026-10-08)*

| rename env vars to `OTEL_WRAPPER_*` | yes, for the non-standard ones only (table below) |

| v0 | v1 | notes |
|---|---|---|
| `OTEL_SERVICE_NAME` | same | standard |
| `OTEL_SERVICE_NAMESPACE` | `OTEL_RESOURCE_ATTRIBUTES=service.namespace=...` | not a standard variable |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | same, plus per-signal `..._{TRACES,METRICS,LOGS}_ENDPOINT` | standard; HTTP only |
| `OTEL_EXPORTER_OTLP_HEADER` + `_HEADER_SEPARATOR` | `OTEL_EXPORTER_OTLP_HEADERS` | standard |
| `OTEL_EXPORTER_OTLP_INSECURE` | removed | only meaningful for gRPC; use an `http://` / `https://` endpoint |
| `OTEL_EXPORTER_PROMETHEUS_PORT` | same | standard |
| (not read) | `OTEL_EXPORTER_PROMETHEUS_HOST` | standard; fixes the localhost-bind bug |
| `OTEL_EXPORTER_PROMETHEUS_ENDPOINT` | `OTEL_WRAPPER_PROMETHEUS_PATH` | ours, named like a standard variable in v0 |
| `OTEL_LOG_LEVEL` | `OTEL_WRAPPER_LOG_LEVEL` | v0's name **collides** with the standard SDK-internal log level, so the old name is only warned about, not read |
| `OTEL_HEADER_ATTRIBUTES` | `OTEL_WRAPPER_HEADER_ATTRIBUTES` | ours |
| (new) | `OTEL_WRAPPER_HEADER_ATTRIBUTES_EXCLUDE` | ours; claim denylist, workstream 5 |
| (hardcoded in v0) | `OTEL_WRAPPER_RESPONSE_HEADER_ATTRIBUTES` | ours; `requests` response headers, default v0's Kong / Envoy list |
| `OTEL_WRAPPER_DISABLED` | same | ours |
| (new) | `OTEL_WRAPPER_LOG_FORMAT` | `json` / `off` |
| (new) | `OTEL_WRAPPER_CAPTURE_COMMAND_ARGS` | default `true` |
| (new) | `OTEL_WRAPPER_PODINFO_DIR` | ours; Downward API volume with `labels` / `annotations`, default `/etc/podinfo` |
| (new) | `OTEL_TRACES_SAMPLER` / `OTEL_TRACES_SAMPLER_ARG` | standard; read by the SDK |
| (new) | `OTEL_{TRACES,METRICS,LOGS}_EXPORTER` | standard; `otlp` (default when an endpoint is set), `console`, `none` |

Old names are read for one release with a deprecation warning at startup (except `OTEL_LOG_LEVEL`, see above).
`OTEL_SDK_DISABLED=true` (standard) also means `OTEL_WRAPPER_DISABLED` (Q5).

*Imported at adoption (2026-10-18) from `PLAN.md` § Environment variables, `PLAN.md` § `TODO.md` triage against the rebuild, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-60 -- Auto-tracing a user's package (`otel.instrument(my_package)`) *(owner, 2026-10-08)*

- Auto-tracing a user's package (`otel.instrument(my_package)`, i.e. logfire's `install_auto_tracing`): it has to run
  before the package is imported, against "import order doesn't matter". A module that isn't a known integration is
  an unsupported target: returned unchanged, one warning.

*Imported at adoption (2026-10-18) from `PLAN.md` § Non-goals, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-61 -- Un-instrumentation, beyond the pytest plugin's per-test reset *(owner, 2026-10-08)*

- Un-instrumentation, except the per-test reset in the pytest plugin. Keep the registry shape that would allow it.

*Imported at adoption (2026-10-18) from `PLAN.md` § Non-goals, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

### DEC-62 -- v0 pins `sqlalchemy[asyncio]<2.1` until the contrib instrumentor supports 2.1 *(owner + agent, 2026-10-08)*

  - `requirements.txt` / `pyproject.toml`: `sqlalchemy` -> `sqlalchemy[asyncio]<2.1` (temporary pin, see below)

- **Unpin sqlalchemy.** `opentelemetry-instrumentation-sqlalchemy` (<= 0.66b0) declares `sqlalchemy < 2.1.0`, so on
  2.1 it logs a `DependencyConflict` and silently produces no spans. The hooks themselves work on 2.1 (verified with
  `skip_dep_check=True`); only the declared range is stale. Track
  [issue #5118](https://github.com/open-telemetry/opentelemetry-python-contrib/issues/5118) / PR #5120. Once a
  release supports 2.1: remove `<2.1` from both dependency files, set that release as the minimum for
  `opentelemetry-instrumentation-sqlalchemy`, and check `sqlalchemy_example.py` prints a `SELECT` span.

*Imported at adoption (2026-10-18) from `HANDOFF.md` § State § v0 fixes, `HANDOFF.md` § Watch upstream, as committed at `24a0430`; now at `docs/evidence/history-to-2026-10-18.md`.*

### DEC-63 -- v0 is pinned by a characterization suite: plain tests, strict xfails for bugs, `v0_specific` for intended changes *(owner + agent, 2026-10-07)*

**Test suite (added 2026-10-07, committed 2026-10-08):** `python -m pytest -q tests/v0` -> `203 passed, 23 xfailed` (~22 s).
It characterizes v0 so v1 can be checked against it. Plain tests pin behaviour v1 should keep. Known bugs are
`xfail(strict=True)` tests asserting the *correct* behaviour, so they error once fixed. `@pytest.mark.v0_specific`
(79 tests) marks v0 details PLAN.md intends to change (name formats, deprecated `code.*` keys, env var parsing,
`user@host` service name). Global OTel state is handled by running scenarios in subprocesses (`tests/v0/_harness.py`).

*Imported at adoption (2026-10-18) from `HANDOFF.md` § How to verify, as committed at `24a0430`; now at `docs/evidence/history-to-2026-10-18.md`.*

### DEC-64 -- Magic variable names through `varname` *(owner + agent, 2026-10-07)*

* [pip install varname](https://github.com/pwwang/python-varname) for magic varname extraction

| `varname` | drop; `co_qualname` covers most of the value |

*Imported at adoption (2026-10-18) from `PLAN.md` § `TODO.md` triage against the rebuild, `TODO.md` § todo, as committed at `24a0430`; now at `docs/archive/PLAN.md`, `docs/archive/TODO.md`.*

### DEC-65 -- Instrument pydantic *(owner, 2022-06-30)*

* ~~instrument pydantic?~~ (too noisy)

*Imported at adoption (2026-10-18) from `TODO.md` § won't do, as committed at `24a0430`; now at `docs/archive/TODO.md`.*

### DEC-66 -- No sanitizer: just don't log secrets *(owner, 2023-06-05)* -- **SUPERSEDED by DEC-58**

* ~~add a (regex-based?) sanitizer to erase strings/patterns from log output~~ (just don't log secrets)

*Imported at adoption (2026-10-18) from `TODO.md` § won't do, as committed at `24a0430`; now at `docs/archive/TODO.md`.*

### DEC-67 -- Locate source with `tracemalloc` or `sys.settrace` *(owner, 2022-09-27)*

* ~~builtin `tracemalloc` can be used locate the source file and line number of a function, if started early enough~~
    * ~~check for the `PYTHONTRACEMALLOC`var?~~
    * ~~there's also `sys.setttrace`, see also PEP 626~~

*Imported at adoption (2026-10-18) from `TODO.md` § won't do, as committed at `24a0430`; now at `docs/archive/TODO.md`.*

### DEC-68 -- Mark functions as do-not-instrument, or give them a sampling ratio *(owner, 2022-09-27)* -- **relaxed by DEC-53**

* ~~somehow mark functions/endpoints as do-not-instrument, for extremely spammy functions? specify a sampling ratio?~~
    * ~~the nearest sampling ratio should overwrite, but idk how to do that~~
    * ~~how to integrate with the instrumentors? seems impossible?~~

*Imported at adoption (2026-10-18) from `TODO.md` § won't do, as committed at `24a0430`; now at `docs/archive/TODO.md`.*

### DEC-69 -- RED metrics computed in the library *(owner, 2024-04-09)*

* ~~add RED metrics, e.g. whatever `prometheus-fastapi-instrumentator` is doing~~
    * this should be automatically done in the backend otel collector

*Imported at adoption (2026-10-18) from `TODO.md` § won't do, as committed at `24a0430`; now at `docs/archive/TODO.md`.*
