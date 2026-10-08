# v1 plan: rebuild on the Logfire SDK

Started 2026-10-04, last updated 2026-10-08. This is the design for the next major version ("v1"; the current code is
v0), written to be reviewed cold. The title reflects the starting point; whether to keep logfire at all is now Q15.

## For the reviewer

- **State:** design only; no v1 code exists. Committed 2026-10-08 together with `README_v1.md`, `HANDOFF.md`,
  `CLAUDE.md`, the `tests/v0` suite and the v0 fixes listed in `HANDOFF.md`. Reviewed 2026-10-07 (two independent
  reviews, merged); the author's answers (2026-10-07/08) are folded into "Decided", the proposals and the
  workstreams. What's still undecided is in "Questions for later".
- **Related files:**
  - `README_v1.md`: draft user-facing API. It reflects the **decided** items below (including proposals 3-8, 10, 11),
    not the open questions.
  - `HANDOFF.md`: repo state, v0 bugs, how to verify.
  - `tests/v0/`: v0 characterization suite, `203 passed, 23 xfailed` (~22 s), run with the repo's conda env
    (`CLAUDE.md`). It's the yardstick for the v0 -> v1 swap.
  - The author's local, untracked notes: the evidence scripts, the full ergonomics review and the v0 talk deck
    transcript. Everything needed from them is summarised here, and the evidence scripts are to become canary tests
    (workstream 0) so they stop depending on one machine.
- **Verified vs opinion:** claims marked *verified* were run against logfire 5.1.1, OTel SDK 1.44.0 / contrib
  0.65b0, mypy 2.4, Python 3.12.15 (Windows). Everything else is design opinion.
- **What to check:** (1) the evidence still holds, (2) the decisions are consistent with each other and with
  `README_v1.md`, (3) the proposals, (4) anything missing (compare with `HANDOFF.md` and the v0 deck's to-do list).

## Goal

Use the Logfire SDK (`logfire.configure(send_to_logfire=False, ...)`) for providers, exporters and the stock
instrumentations, and keep only what it lacks or gets wrong. Python floor: **3.12** (logfire itself needs >= 3.10).

## Principles (kept from v0)

1. **Idempotency.** Every public entry point can be called any number of times, from anywhere, and behaves as if it was
   called once. Includes methods reached through instances (v0 gets this wrong, see "v0 lessons").
2. **Never crash** the application.
3. **No telemetry of its own at runtime** (v0 deck: "emits zero logs/spans of its own"). Warnings are allowed only at
   startup / decoration / instrumentation time, once each, never per call. Our own entry points emit no spans (v0's
   do).
4. **Introspection** (`CodeInfo`), rewritten per `HANDOFF.md` (`co_qualname`, no `cls` heuristics, stable attributes).
5. **Class and dataclass support**, including library classes (`otel(SortedList)`).
6. **Kubernetes support**, as resource detectors.
7. **Machine-readable first**: one-line JSON logs, JSON-encode anything.

## Decided (by the author)

API:

- **One `otel` object** that decorates (functions, methods, classes, dataclasses, generators, context managers) and
  opens spans (`with otel:`, `with otel('name'):`). Libraries and apps use **`otel.instrument(x)`**, and
  `otel.instrument()` with no arguments instruments everything global that's installed (v0's `instrument_all()`).
  Bare `otel(app)` was rejected: unreadable in review, and the supported set is undiscoverable.
- **Configured objects (`otel(name=...)`) are immutable and stateless**; per-entry span state lives in a `ContextVar`.
  v0's sketch kept a span stack on the shared object, which breaks under concurrency (see "Public API notes").
- **No "blocked" behaviour.** It existed because code info cached on the object could be reused for the wrong target.
  Instead, code info is looked up at run time from the target: the decorated function's code object at decoration
  time, the caller's frame (`f_code`, `f_lineno`) at `__enter__`, cached by code object + line, never stored on `otel`.
- **Generators and context managers** as in workstream 7 (author approved the prototype).
- **No per-span sampling.** Sampling is decided at the root span; use `OTEL_TRACES_SAMPLER_ARG` (logfire reads it as a
  parent-based trace-id ratio, per its source).
- **`OTEL_WRAPPER_DISABLED`** means no telemetry at all, for test envs with nowhere to export, where only stack traces
  matter: decorators return the target unchanged (no wrapper frames in tracebacks), `otel.instrument` is a no-op, and
  `with otel as span` yields OTel's standard `NonRecordingSpan` (`trace.INVALID_SPAN`). *Verified:* every method
  works and records nothing, and exceptions propagate untouched. It's read at decoration time, so wrappers that
  already exist also check it at call time (e.g. a test that sets it after import).
- **Our spans come from the OTel tracer, not `logfire.span` / `logfire.instrument`.** Logfire is used for
  configuration, exporters, scrubbing and the stock instrumentations; our decorator and `with otel:` call
  `trace.get_tracer(...)`, which goes through logfire's provider and processors anyway. *Verified:* a plain OTel span
  gets only `logfire.span_type` and `logfire.msg` added and none of logfire's deprecated `code.*` keys, while
  `logfire.span` walks the stack per call and adds five `logfire.*` attributes. So the exposed span type is OTel's
  `trace.Span` (was proposal 2), the same in enabled and disabled mode. To check: how `OTEL_WRAPPER_LOG_FORMAT=pretty`
  renders spans without `logfire.msg_template`.
- **No arguments or return values on spans.** *Verified:* `logfire.instrument` records **every argument** by default
  as a top-level attribute named after the parameter (`n = 3`; `password` survives only because the scrubber matches
  its name), and the return value only with `record_return=True`. Ours records neither: PII, payload size, and
  parameter names colliding with real attribute keys. Users add what they need via `attributes={...}` or the span.
- **Configuration: implicit and explicit together** (was proposal 1, with the review's changes).
  1. Decorating never configures anything, so import order doesn't matter. The first span configures from env vars,
     **only if nothing has configured yet** (us, the test plugin, or the app calling `logfire.configure` directly;
     detect via `logfire.DEFAULT_LOGFIRE_INSTANCE.config._initialized`, which is private, so pin and test it).
     `otel.instrument(...)` configures **eagerly**, since nearly every app calls it at startup; that keeps
     configuration (file reads, a possible k8s API call, exporter threads, a port bind) off the first request and out
     of the event loop. A lock makes "configure if not yet configured" atomic across threads.
  2. `otel.configure(...)` takes a typed signature (not "env var names in lowercase"). Explicit > env > default. Same
     arguments again (normalised, env-derived defaults included): no-op. **Configuration is final once the first span
     exists**: a later call with different arguments warns once and is ignored, except for a small allowlist of
     settings that can change safely (see "Questions for later"). *Verified* reasons: logfire's reconfigure shuts the
     old tracer and meter providers down (open spans end into dead processors; the meter shutdown can time out), a
     Prometheus port can't be bound twice, and a second `PrometheusMetricReader` collides in the global registry.
  3. Test capture survives configuration. *Verified* problem: the `capfire` fixture from logfire works, but a later
     `logfire.configure()` (what implicit configuration does) silently drops every subsequent span from the capture.
     Fix: a pytest plugin (`pytest11` entry point, loads before app code) that doesn't call `logfire.configure`
     itself but registers in-memory span and log processors **with us**; every configure we do re-includes them.
     Because a `pytest11` plugin loads in **every** project that installs the package, auto-loading is passive: it
     only registers the `otel_spans` / `otel_logs` fixtures (reset per test). Exporters, Prometheus and console are
     switched off only when a test opts in (see "Questions for later" for the trigger). Document
     `-p no:opentelemetry_wrapper`, use the SDK's `InMemorySpanExporter` (logfire's `TestExporter` also receives
     pending spans), and define what happens next to logfire's own `capfire` plugin.
  4. `otel.config`: a read-only view of the effective configuration, secrets redacted (v0 logged its config and
     leaked the OTLP auth header).
- **Logfire options set explicitly:** `send_to_logfire=False`, `console=False`, `distributed_tracing=True`
  (if proposal 9 is signed off), `add_baggage_to_attributes` per Q6, `emit_configuration_span=False` (otherwise the `LOGFIRE_EMIT_CONFIGURATION_SPAN` env var could make us
  emit a span of our own), `inspect_arguments=False`.

Telemetry content:

- **`service.name` follows semconv** (the workload name); breaking existing dashboards is accepted. v0's readable
  `ns/workload/pod` or `user@host:main.py` string moves to `opentelemetry_wrapper.instance.label`, and
  `service.instance.id` stays a per-process UUID (workstream 6, "Service identity").
- **Full command line** recorded as `process.command_args` (from `sys.orig_argv`, sanitized), plus our
  `opentelemetry_wrapper.python.environment` (conda / venv / system / pyodide / frozen), so it's clear which
  interpreter ran the process.
- **Stable semconv `code.*` keys** everywhere (workstream 3). Logfire's deprecated keys don't appear, because we
  don't use the logfire APIs that write them (see Evidence).
- **Logs are real OTel log records**, via the SDK's `LoggingHandler`, never spans. Use the logs, traces and metrics
  signals as OTel intends. (An earlier draft kept logfire's logs-as-spans model; that was never the intent.) *Verified:*
  logfire installs a global `LoggerProvider` whenever an OTLP endpoint is set, so `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT`
  works. A record logged inside a span carries that span's `trace_id` / `span_id` (that's how backends show it on
  the span: it's correlated, not a child in the span tree), `extra={...}` becomes attributes, and the code location
  uses the stable keys. Logs are **not** affected by head sampling: at a 0% ratio the spans are dropped but every log
  record is still exported (with `trace_flags=0`), and a log outside any span has no trace ids. `LogfireLoggingHandler`
  is not used. Both span and log capture are tested through the same pytest plugin.
- **Resource precedence is resolved by us.** `OTEL_SERVICE_NAME` / `OTEL_RESOURCE_ATTRIBUTES` must beat our detectors,
  but *verified*: logfire merges `AdvancedOptions.resource_detectors` **after** the env vars
  (`_internal/config.py`, `Resource.create()` first, detectors on top), so registering our detectors there would
  let a k8s guess override `OTEL_SERVICE_NAME`. Instead, run our detectors, merge the env vars on top ourselves, and
  pass the result as `resource_attributes`. Test: `OTEL_SERVICE_NAME` wins in k8s. Side effect to know about: with no
  `service_version`, logfire runs `git rev-parse` at configure time and uses the hash as `service.version` (locally,
  possibly the wrong repo).

Output and dependencies:

- **Console:** ours (one-line JSON) replaces logfire's; logfire's pretty console only on request
  (`OTEL_WRAPPER_LOG_FORMAT=pretty`).
- **Pydantic 2 only, optional, detected at startup.** `try: import pydantic` once at startup; if it's v2, register
  encoders for its real types (`isinstance` / type lookup, no duck typing), e.g. `BaseModel` ->
  `model_dump(mode="json")`. Pydantic 1 counts as absent (warn once at startup); `pydantic.v1` models get the generic
  encoder. This is what logfire's own `_internal/json_encoder.py` does, and it costs nothing extra: *verified*,
  `import logfire` already imports pydantic when installed (~120 ms), although pydantic isn't a logfire requirement.
  FastAPI 0.142 requires `pydantic>=2.9` anyway. v0 keeps supporting both.
- **gRPC export dropped** for now (logfire is HTTP-only; collectors listen on 4318 by default).

Process:

- **Rollout: side by side.** v1 ships next to v0 in the same package until it's proven safe against `tests/v0`, then
  becomes the default and v0 is deleted. For one release after that, v0's entry points (`instrument_decorate`,
  `instrument_all`, `instrument_fastapi_app`, `instrument_sqlalchemy_engine`, ...) stay as thin deprecated aliases
  over v1, so users can migrate incrementally.
- **"Proven safe" is one command.** The v0 tests call v0 names directly, so the harness gets a small adapter
  (`decorate` / `instrument_app` / `instrument_engine` / `setup`) selected by `OTW_IMPL=v0|v1`; plain tests must pass
  under both, `v0_specific` tests are v0-only. Commit the suite first so the baseline is pinned.
- **Tests:** settle the shape of v1 before writing its tests. The v0 characterization suite exists now.
- **Packaging** is its own workstream (10).
- **Hosting stays on GitHub** (+ PyPI). The v0 deck's move to GitLab + Artifactory is not happening. CI is GitHub
  Actions.
- **`type_checking.py` stays in the repo, unchanged** (it works), but v1 doesn't import or export it, as v0 already
  doesn't.
- **Global dataclass instrumentation is dropped** (v0's `instrument_dataclasses()`): patching `dataclasses.dataclass`
  depends on import order, contradicting configuration rule 1, and its `__getattribute__` patching is behind several
  v0 bugs. `@otel` on the dataclass covers the real use.
- **Logging options** come from env vars and `otel.configure(...)` only, not `otel.instrument(logging, level=...)`:
  per-call options would make "instrument twice = once" ambiguous.

## Non-goals (for v1.0)

- gRPC export (logfire is HTTP-only).
- Logs as spans.
- Per-span sampling.
- Global dataclass instrumentation.
- Auto-tracing a user's package (`otel.instrument(my_package)`, i.e. logfire's `install_auto_tracing`): it has to run
  before the package is imported, against "import order doesn't matter". A module that isn't a known integration is
  an unsupported target: returned unchanged, one warning.
- Un-instrumentation, except the per-test reset in the pytest plugin. Keep the registry shape that would allow it.
- Recording function arguments or return values.
- Type-checking helpers in the public API.

## Proposals (signed off 2026-10-08, except 9)

From the planning session and from an ergonomics review of `README_v1.md` (findings F1-F12; F1, the disabled-mode
part of F2, and F11 are already decided above). Items 1 and 2 have moved to "Decided"; the numbering is kept because
workstreams refer to it. Amendments from the 2026-10-07 review are marked *(review)*. The author signed off 3-8, 10
and 11 as written here, so they count as decided. 9 waits on Q15: it's a logfire option and goes away if logfire does.

1. *Decided* ("Configuration").
2. *Decided* ("Our spans come from the OTel tracer"): the exposed span type is OTel's `trace.Span`. Background,
   *verified*: `logfire.span()` returns a `LogfireSpan`, which is *not* an OTel `Span`; it wraps logfire's
   `_LogfireWrappedSpan` (an OTel `Span` subclass, the same object `trace.get_current_span()` returns), which wraps
   the SDK's `_Span`.
3. **Escape hatches** (F4): `otel.span` (current span; a no-op span when there is none, never `None`), `otel.trace_id`
   / `otel.span_id` (hex strings, e.g. to return in an HTTP 500 body; all zeros when there's no span or telemetry is
   disabled). Document `record_exception`, `add_event`, marking a span failed without raising, and stdlib `logging`
   `extra={...}` (*verified*: becomes attributes on the log record).
4. **Import path** (F5): `from opentelemetry_wrapper import otel`, so users change imports once, not twice. *Verified:*
   nothing in v0's `__all__` is called `otel`. `opentelemetry_wrapper.v1` stays the implementation module.
5. **Unnamed `with otel:` blocks** (F6): name them after the enclosing function, not `load_config:42`. A span name
   containing a line number changes whenever the file is edited, breaking dashboards and alerts. The line stays in
   `code.line.number`. Nudge users toward `with otel('name'):`. *(review)* Use module + `co_qualname`
   (`app.config.load_config`, `app.config.<module>`), the same shape as decorated functions, so same-named functions
   in different modules don't collide. The name cache is keyed by (code object, line), so when a second unnamed block
   shows up in the same function, warn once ("two unnamed blocks in X; name them").
6. **Decorator order with `@property`** (F7): document `@property` on top, `@otel` underneath. *Verified:* mypy
   rejects *any* decorator above `@property` (`[prop-decorator]`). This is a mypy limitation; Python accepts both
   orders, and v1 handles both at runtime.
7. **Warning channel** (F8): one `OtelWrapperWarning(UserWarning)` via `warnings.warn(..., stacklevel=2)`, only on
   startup paths (decoration, `instrument`, `configure`, env var parsing), never through `logging` and never per call.
   The default filter shows each message once per call site, and `-W error::...OtelWrapperWarning` in CI turns misuse
   into a test failure without ever crashing production. *(review)* Call `warnings.warn` outside our own
   `try`/`except` blocks so an error-filtered warning isn't swallowed; whether `PYTHONWARNINGS=error` in production
   may crash at startup is in "Questions for later".
8. **`@otel()` and `with otel():`** (F10) mean the same as `@otel` / `with otel:`, silently (v0's sketch warned).
9. *(Pending Q15.)* **Distributed tracing on** (`distributed_tracing=True`). *Verified:* by default logfire continues an incoming
   `traceparent` but emits `RuntimeWarning: Found propagated trace context`; with it on, same trace, no warning.
10. **Migration** (F9):
    - old env var names read for one release, with a startup warning. *(review)* Except `OTEL_LOG_LEVEL`: it's the
      SDK's own variable, so honouring it would keep the collision alive. Warn when it's set and
      `OTEL_WRAPPER_LOG_LEVEL` isn't, but don't use it;
    - warn at startup when the OTLP endpoint uses port `4317` or `grpc://` (v0's README example was `:4317`; an HTTP
      exporter posting to a gRPC port fails on every batch, visible only in the SDK's internal logger). *(review)*
      Same warning for `OTEL_EXPORTER_OTLP_PROTOCOL=grpc` and `OTEL_EXPORTER_OTLP_INSECURE`, both of which v0 users
      may have set;
    - *(review)* warn when `OTEL_TRACES_SAMPLER` is set: logfire reads only `OTEL_TRACES_SAMPLER_ARG` (*verified*), so
      e.g. `always_off` would be silently ignored;
    - *(review)* `OTEL_EXPORTER_OTLP_HEADERS` values are URL-decoded (*verified*, `opentelemetry/util/re.py`), so
      v0's `Authorization: Basic abc==` becomes `Authorization=Basic%20abc==` (the `=` padding is fine: it splits on
      the first `=`). Say so in "Upgrading";
    - keep v0's Downward API recipe for pods without a service account, rewritten for
      `OTEL_RESOURCE_ATTRIBUTES=service.namespace=$(POD_NAMESPACE)`;
    - list the dropped `async ` span-name prefix under "Upgrading".
11. **Smaller points** (F12):
    - instrumenting a class spans methods and constructors by default, properties opt-in
      (`@otel(properties=True)`), since a property read in a loop is the noisiest thing in the library;
    - *(review)* dunders: only `__new__`, `__init__`, `__post_init__`, `__call__`, `__enter__`/`__exit__` (and async
      versions). Never `__repr__`, `__eq__`, `__hash__` etc.: they're noisy and can recurse (a span attribute that
      calls `repr(self)`);
    - *(review)* a per-method opt-out for hot methods inside an instrumented class, e.g. `@otel.ignore`;
    - say `OTEL_TRACES_SAMPLER_ARG` means `parentbased_traceidratio`;
    - `attributes={...}` as a dict (not `**kwargs`), so it can't collide with options.

## Questions for later (need the author's input)

The earlier open questions are settled: type-checking, global dataclass instrumentation, logging options and repo
hosting under "Decided"; auto-tracing and un-instrumentation under "Non-goals"; response headers in workstream 5.
Each question below has a suggested default, used if nobody decides otherwise.

- **Q1. SQLAlchemy engines created later.** *Decided 2026-10-07*, see workstream 2: `otel.instrument(sqlalchemy)`
  instruments globally (later engines included, `connect` spans on); `otel.instrument(engine)` instruments that engine
  only, without `connect` spans; the engine docs state this.
- **Q2. `x-userinfo` by default.** *Decided 2026-10-07*, see workstream 5: capture every claim except a denylist.
  Still to confirm: the default denylist given there.
- **Q3. Exception status.** *Suggested* policy (needs the author's OK):

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
- **Q4. `process.executable.name` on Windows:** `python.exe` (what the file is called) or `python`? It also decides
  the fallback `service.name` (`unknown_service:python.exe` vs `unknown_service:python`; `README_v1.md` says the
  latter).
- **Q5. `OTEL_SDK_DISABLED=true`** (standard; the SDK already honours it with a no-op tracer): should it also mean
  `OTEL_WRAPPER_DISABLED` (no wrapper frames at all)? *Suggested:* yes.
- **Q6. Logfire's `add_baggage_to_attributes`** (default on) copies W3C baggage onto every span: a possible leak of
  whatever upstream services put in baggage. Keep or switch off? *Suggested:* off.
- **Q7. `LOGFIRE_*` env vars** still influence `logfire.configure` (e.g. `LOGFIRE_TRACE_SAMPLE_RATE` is read before
  `OTEL_TRACES_SAMPLER_ARG`). Document them as honoured, or warn and ignore? *Suggested:* warn at startup when any is
  set.
- **Q8. `PYTHONWARNINGS=error` in production** turns our startup warnings into exceptions. Accept that as the one
  sanctioned exception to "never crash" (the user asked for it), or catch it? *Suggested:* accept and document.
- **Q9. Which settings may change after the first span** (configuration rule 2)? *Suggested:* the log level only.
- **Q10. Pytest plugin opt-in trigger** for switching exporters/console/Prometheus off: requesting the `otel_spans` /
  `otel_logs` fixture, an ini option, or both? *Suggested:* the fixture, plus an ini option for whole-suite use.
- **Q11. `otel.instrument()` with no arguments**: confirm the set: logging, requests, system metrics (needs
  `logfire[system-metrics]`); never apps, engines or SQLAlchemy globally.
- **Q12. The k8s API lookup** (pod labels/annotations, one HTTPS call at startup): on by default with a ~1 s cap and
  `OTEL_WRAPPER_K8S_API=false` to switch it off, or off by default? Some clusters flag pods that call the API server.
- **Q13. Function name on log records**: the SDK's `LoggingHandler` writes `code.function.name` as the bare
  `record.funcName` (`<module>`, `load_config`), while semconv wants it fully qualified. Accept, or rewrite it in a
  log processor?
- **Q14. Sign-off on proposals 3-11.** *Decided 2026-10-08:* 3-8, 10 and 11 signed off as amended; 9 waits on Q15.
- **Q15. Is logfire still worth depending on?** After the review, v1 uses none of logfire's span, instrument, log
  handler or console APIs (console only for `pretty`), works around its resource precedence, idempotency, `LOGFIRE_*`
  env vars and `x-userinfo` scrubbing, bypasses its SQLAlchemy integration, and its `instrument_requests` is a plain
  pass-through to `RequestsInstrumentor` (*verified* in source). Its `instrument_fastapi` records the endpoint's
  resolved arguments by default, including the parsed request body and dependency results (read in source, not run),
  which conflicts with "no arguments on spans". What it still provides: provider/exporter/sampler setup (which the SDK
  mostly does from env vars on its own, and v0 already has), **scrubbing** of span attributes and log records (no SDK
  equivalent), the `pretty` console, and post-fork `process.pid` fixing. Costs: it pins `opentelemetry-sdk<1.45`,
  adds `logfire.span_type` / `logfire.msg` to every span, pulls in `rich` and `executing`, auto-loads two pytest
  plugins, runs `git rev-parse`, and needs the `_initialized` private attribute. The alternative is the plain OTel SDK
  + contrib instrumentors + our own small scrubbing exporter wrapper (we'd construct the exporters, so wrapping them
  is public API). *Suggested:* a short spike: `configure` on the plain SDK, scrubbing included, then decide. Many
  items above (Q6, Q7, proposal 9, the logfire options, the `_initialized` canary) disappear if logfire goes.

## v0 lessons (from `tests/v0`, 2026-10-07)

Bugs and surprises in v0 that v1's design must avoid; details in `HANDOFF.md`.

- **Idempotency must survive indirection.** v0 gives two nested spans when an already-instrumented method is reached
  through an instance (decorated method inside an instrumented class, explicit `x.__call__()`, `__post_init__` via
  `__init__`). Track "already instrumented" on the underlying function, not on the wrapper object.
- **Never key caches on shared objects.** v0 keys its `__getattribute__` cache on the class's original
  `__getattribute__`, which is `object.__getattribute__` for every ordinary class, so only the first instrumented class
  gets method spans. Key per class (weakly).
- **No strong caches of user objects** (bound methods, `CodeInfo` `lru_cache`): both leak instances.
- **base64 header decoding:** pad with `-len % 4` `=`; v0's unconditional `==` fails 2 of 3 lengths on 3.12, and the
  undecoded header (PII) is then recorded raw.
- **Exact path match** for the Prometheus route exclusion; v0's regex search also drops spans for `/api/metrics`.
- **Unsupported targets return unchanged** (v0 raises `TypeError` / `AssertionError` for `partial`, callable instances,
  `42`).
- **No source needed:** v0 calls `inspect.getsourcelines` on every property access and raises `OSError` without source.
- **Optional dependencies stay optional at call time**, not just import time (v0's `instrument_sqlalchemy_engine`
  crashes without sqlalchemy's asyncio extension).
- **Never log secrets** (v0's `instrument_all()` logs the OTLP auth header).

## Evidence (logfire 5.1.1, OTel SDK 1.44.0 / contrib 0.65b0, Python 3.12.15)

All reproduced by running small scripts; results recorded here because the scripts were throwaway (kept locally,
untracked). Workstream 0 turns the ones about upstream behaviour into canary tests.

### Idempotency: logfire's isn't

| Done twice | logfire | v0 |
|---|---|---|
| decorate the same function | `logfire.instrument()(logfire.instrument()(f))` -> **2 nested spans per call** | 1 span, also for a later `instrument_decorate(f)` |
| instrument the same FastAPI app | **`ValueError: This app has already been instrumented.`** | no-op, same 3 spans |
| add the logging handler | 2 `LogfireLoggingHandler`s (plain `addHandler`, no idempotent setup function) | `instrument_logging()` x2 -> 1 handler |

### SQLAlchemy: both logfire and v0 only trace engines created after the first call

`SQLAlchemyInstrumentor` is a singleton, and its first `instrument()` also patches `create_engine`, so engines created
**later** are traced automatically and engines that **already exist** are not:

```
logfire.instrument_sqlalchemy(engine=e1); logfire.instrument_sqlalchemy(engine=e2)   # e1, e2 both pre-existing
e1 (created before, instrumented)    ['connect', 'select']
e2 (created before, instrumented)    ['connect']              <- no query spans
e3 (created after, never passed in)  ['connect', 'select']
```

Fix, verified: attach `opentelemetry.instrumentation.sqlalchemy.engine.EngineTracer(tracer, engine, connections_usage)`
per engine (`connections_usage` is the `db.client.connections.usage` up-down counter upstream creates in
`_instrument`). Both pre-existing engines then get `select` spans, and attaching a second `EngineTracer` to the same
engine does not duplicate them. `connect` spans come from upstream's global `connect` patch, not from `EngineTracer`.
`EngineTracer` lives in a non-`__init__` module, so pin/watch it; still track engines in a `WeakSet` so we never rely
on that dedup.

### Introspection: logfire covers plain functions only

`logfire.instrument` (`_internal/instrument.py:get_attributes`) does `inspect.unwrap`, then `__qualname__`,
`__code__.co_firstlineno` and `inspect.getsourcefile`; anything that isn't `inspect.isfunction` falls back to
`.__call__`. Spans/logs created with `logfire.span`/`logfire.info` instead walk the stack to the first frame outside
stdlib/site-packages/logfire (`_internal/stack_info.py`) and record the **call site** line.

| case | logfire | `CodeInfo` |
|---|---|---|
| plain / async function, closure, lambda, staticmethod, `@wraps`, `lru_cache`, singledispatch | ok | ok (the wrapper-labelling code never triggers for `@wraps`; found by the test suite) |
| bound method, classmethod | `method.__call__`, no file/line | ok |
| `cached_property` | `<functools.cached_property object at 0x...>` (high cardinality) | ok |
| builtin `len` | `builtin_function_or_method.__call__` | `<builtins>.len` |
| `functools.partial` | `partial.__call__`, no file/line | ok |
| class | no spans, no error | spans for methods/properties/constructors |
| callable instance | `Outer.__call__` with file/line | **broken** (see `HANDOFF.md`) |

Logfire writes the **deprecated** keys `code.filepath` (relative to cwd) / `code.lineno` / `code.function` (qualname,
no module). Stable semconv is `code.function.name` (fully qualified), `code.file.path` (absolute preferred),
`code.line.number`, `code.column.number`, `code.stacktrace`.

Where they come from, and whether they can be removed (*verified* 2026-10-07):

- Only logfire's own APIs write them: `logfire.span` / `logfire.info` etc., `logfire.instrument`,
  `LogfireLoggingHandler`, and the opt-in slow-async-callback detector. A span from the plain OTel tracer has none,
  and the SDK's `LoggingHandler` writes the stable keys (`code.file.path`, `code.function.name`, `code.line.number`).
  Since v1 uses neither `logfire.span` nor `LogfireLoggingHandler`, there's nothing to remove.
- `span.set_attribute('code.filepath', None)` in a processor's `on_start` does **not** remove it: `None` is an invalid
  attribute value, so the SDK logs a warning and keeps the old value.
- A resource detector can't help: resource attributes are a separate level from span attributes, and `None` values
  are dropped there too (same warning).
- `span._attributes.pop('code.filepath', None)` in `on_start` **does** remove it (private API; only needed if a
  logfire API that writes them is ever used).

### Arguments and return values: logfire records arguments by default

`@logfire.instrument()` on `def secret(password, n)` called as `secret('hunter2', 3)` gives the attributes
`password = "[Scrubbed due to 'password']"` and `n = 3`: every argument, by default (`extract_args=True`), as a
top-level attribute named after the parameter. A parameter called `token`, `user` or `body` would go out as-is. The
return value is recorded (`return = ...`) only with `record_return=True` (default `False`). Our decorator records
neither (see "Decided").

### Generators and context managers: logfire gets both wrong

- `@logfire.instrument` on a generator warns, and with `allow_generator=True` keeps its span current across `yield`:
  the **consumer's** logs between iterations end up as children of the generator's span.
- `@logfire.instrument` *above* `@contextmanager` gives a ~0 ms span and the `with` body is not inside it (it only warns
  "should be underneath"). Underneath works, but still warns unless `allow_generator=True`.

### Headers and scrubbing

`logfire.instrument_fastapi(app, capture_headers=True)` stores the raw value:
`http.request.header.x_userinfo = ('eyJzdWIi...',)`. No base64/JSON decoding or flattening, so keep
`extract_json_header` + the request hook. Verified with a raw ASGI request carrying a Keycloak-style userinfo and v0's
`request_hook`:

- `server_request_hook=` **is** forwarded (via `**opentelemetry_kwargs`); the flattened attributes appear on the root
  span.
- Logfire doesn't parse the header. Its scrubber checks each flattened attribute separately, by key **and by value**:
  `x-userinfo.auth_time` (key, `auth`), `x-userinfo.session_state` (key, `session`) and `x-userinfo.iss` (value
  `https://auth.example.com/...`) become `[Scrubbed due to '...']`. `sid`, `author`, `email`, roles etc. survive.
  `authorization` is scrubbed, as it should be.
- `ScrubbingOptions(callback=...)` returning `match.value` for paths `("attributes", "http.request.header.x-userinfo.*")`
  keeps those fields and still scrubs everything else.
- **Leak:** `capture_headers=True` also records the raw base64 `x_userinfo`, which scrubbing can't see into, so
  `session_state` etc. go out anyway.

### Logs: logfire's handler makes spans; the SDK's handler makes real log records

- With logfire's `LogfireLoggingHandler`, a stdlib `logging.warning('hello %s', 'world', extra={'order_id': 7})` and a
  `logfire.info(...)` both become zero-duration spans with `logfire.span_type = log`, and a log record processor
  (`AdvancedOptions(log_record_processors=[...])`) receives **0** records. The handler has no option to do otherwise
  (it always calls `logfire.log()`). By reasoning (not run), those log spans are also subject to head sampling: a log
  outside any span becomes a root span, so at a 10% ratio about 90% of standalone warnings would be dropped.
- With the SDK's `opentelemetry.sdk._logs.LoggingHandler` on the root logger (what v0 does), using logfire's global
  `LoggerProvider`, the same log is a real OTel log record: `trace_id` / `span_id` of the current span (zeros outside
  a span), extras as attributes, stable `code.*` keys. At a 0% head-sampling ratio the spans are dropped and the log
  records are all still exported (`trace_flags=0`). Logfire builds that `LoggerProvider` with an OTLP log exporter
  whenever `OTEL_EXPORTER_OTLP_ENDPOINT` or `..._LOGS_ENDPOINT` is set, behind its scrubbing wrapper (the scrubbing
  of log records was read in the source, not run).

### Resources: OTel SDK and logfire defaults

- Default `service.name` is `unknown_service`; the stable service conventions say SDKs **MUST** use
  `unknown_service:<process.executable.name>`.
- `ProcessResourceDetector` sets `process.executable.name` to the full path of `python.exe`, `process.executable.path`
  to its directory (semconv: base name and full path), and `process.command` to the interpreter path; it never records
  the script or its arguments.
- Logfire's resource has **no** `process.executable.*`, `process.command*` or `process.owner` (only `process.pid` and
  `process.runtime.*`).
- `sys.orig_argv` has the real command line: `python.exe -X utf8 -m cmdline_check --db-password=hunter2 --token abc`
  came back complete (`sys.argv` drops the interpreter, its flags and `-m`). Logfire's default scrub patterns catch
  `--db-password=hunter2` but not `--token abc`.
- `CONDA_DEFAULT_ENV` names the shell's active env (`base`), not the interpreter's (`opentelemetry_wrapper`).
- No Kubernetes resource detector exists for Python (SDK ships `otel`, `process`, `os`, `host`, `service_instance`;
  contrib has `azure`, `containerid`, `gcp`). The k8s derivation rules are only implemented by the Collector's
  `k8sattributes` processor and the Operator.
- The SDK generates a random `service.instance.id` by default. The Prometheus pull exporter puts resource attributes in
  `target_info` only (verified, including a custom `opentelemetry_wrapper.instance.label`), and sets no `job`/`instance`.

## Workstreams

### 0. Tests

v0 characterization suite: done (`tests/v0`, committed 2026-10-08). Plain tests are behaviour v1 must keep; `v0_specific`
tests (79) mark intended changes; strict xfails are v0 bugs. v1 tests come after the API is settled, reusing the same
scenarios (and the subprocess harness in `tests/v0/_harness.py`).

- Add the `OTW_IMPL=v0|v1` adapter (see "Decided", Process).
- **Canary tests** (`tests/upstream/`): one test per upstream behaviour or private API we rely on, so a logfire or
  OTel upgrade fails a test instead of production: `config._initialized`; the `EngineTracer` import path and
  signature; `span._attributes` if it's ever used; the `contextmanager` shared-`__code__` trick; resource precedence
  in `logfire.configure`; logfire's non-idempotent `instrument*` (if logfire fixes it, we can simplify). These
  replace the local evidence scripts.
- In-process fixtures must strip `LOGFIRE_*` as well as `OTEL_*` (`tests/conftest.py` strips only `OTEL_*`; the
  subprocess harness already does both).
- Tests for the two-tasks-plus-a-thread interleaving from "Public API notes".
- A micro-benchmark of per-call overhead (v0 vs v1, with and without an exporter), so a regression is visible.
- **CI:** GitHub Actions (none yet; `.github/workflows/` doesn't exist). Matrix: Python 3.12 / 3.13 / 3.14 × with and
  without the optional extras, so "optional at call time" is actually exercised. Keep the steps in a script so the
  workflow file stays thin.

**Order:** 0 -> 1 (configure, decorator, `with otel:`) -> 3 -> 7 -> 4 -> 5 -> 2 -> 8 -> 9, with 6 in parallel (pure
OTel, testable alone) and 10-11 alongside 1. Each workstream ends with a one-line **Done when**, given below.

**Done when:** the suite is committed, `OTW_IMPL=v1` runs (failures expected until v1 exists), canaries pass, CI runs
on push.

### 1. Idempotent, never-crash wrappers over logfire

- One function per integration (`fastapi`, `requests`, `sqlalchemy`, `logging`, system metrics) that records what it
  already instrumented (weakref where the target is an object) and swallows/warns-once on failure, at instrumentation
  time only. Also warn once when an instrumentor hits a `DependencyConflict`: upstream only logs it and produces no
  spans (`HANDOFF.md`, the sqlalchemy and requests cases), which isn't an exception we'd catch.
- `otel.instrument(app)` after the app has started can't add middleware (Starlette raises): warn once, return the app.
- Our own decorator creates spans with the OTel tracer and `CodeInfo` attributes (see "Decided"), and keeps the
  "already instrumented, return the cached wrapper" logic, keyed on the underlying function (see "v0 lessons").
- Wrappers keep the target's kind: `inspect.iscoroutinefunction`, `isgeneratorfunction`, `isasyncgenfunction` and the
  signature (via `__wrapped__`) must be the same as the original's. FastAPI uses them to pick threadpool vs `await`
  and to treat `yield` dependencies as context managers; pytest does the same for fixtures.
- `with otel:` keeps its state in a `ContextVar` holding an immutable value: `set()` on enter, `reset(token)` on
  exit. Never a list that gets mutated: `copy_context()` copies the mapping, not the values, so a mutated list leaks
  between tasks.
- Call `logfire.add_non_user_code_prefix()` on our package path so our frames are not reported as user code (only
  matters when it isn't installed in site-packages, e.g. local dev).
- `logfire.configure(...)` with the options under "Decided", run under the configuration lock.
- Exception handling per Q3; re-raise with a bare `raise` so tracebacks are untouched, and set `__tracebackhide__`
  (pytest) / `__traceback_hide__` (Sentry and others) in wrapper frames.

**Done when:** functions (sync, async), `with otel:` / `with otel('x'):`, configure (implicit, explicit, final after
the first span), disabled mode and the pytest plugin pass their tests; the plain `tests/v0` decorator tests pass under
`OTW_IMPL=v1`.

### 2. SQLAlchemy

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
- `otel.instrument()` with no arguments doesn't include sqlalchemy (v0's default too: query spans are noisy); Q11.

- `connections_usage` is a local inside upstream's `_instrument`, not something to fetch: create our own
  `db.client.connections.usage` up-down counter from the same meter.
- `EngineTracer` also takes `enable_commenter` / `commenter_options` / `enable_attribute_commenter`, which v0 exposes
  (`instrument_sqlalchemy.py`). Keep them, as `otel.instrument(engine, commenter=...)` or an env var.
- Attaching `EngineTracer` directly skips upstream's dependency check, which may let v1 drop the `sqlalchemy<2.1` pin
  (`HANDOFF.md`, "Watch upstream"); the hooks work on 2.1.

**Done when:** two pre-existing engines and one created later (and passed in) all produce `SELECT` spans;
after `otel.instrument(sqlalchemy)`, an engine created later and never passed in produces `connect` and `SELECT`
spans; instrumenting an engine twice gives one span per query; `AsyncEngine` works; no sqlalchemy installed ->
warning, no crash.

### 3. Introspection

The `CodeInfo` rewrite in `HANDOFF.md`. Emit stable `code.*` keys, using the constants in
`opentelemetry.semconv.attributes.code_attributes` rather than string literals; put extras (wrapper chain,
`is_class`, end line) under our own prefix, e.g. `opentelemetry_wrapper.code.*`. Logfire's deprecated keys need no
handling: v1 never calls the logfire APIs that write them (Evidence, "Introspection"). Auto-name `with otel:` blocks
from the call site (see proposal 5 for the naming), which logfire can't do.

**Done when:** every row of the Evidence introspection table gives the right name, file and line (including callable
instances and decorators that set `__wrapped__` without `@wraps`); no source needed; no strong references to user
objects.

### 4. Classes and dataclasses

Port `_instrument_class` onto the new decorator, avoiding v0's cache-keying bug, the bound-method leak and the
per-property-access `inspect.getsourcelines` (use `fget.__code__.co_firstlineno`). Class-based context managers get
one `__enter__` -> `__exit__` span (workstream 7).

- Wrap the functions in `cls.__dict__` (plain functions and the `staticmethod` / `classmethod` / `property`
  descriptors) at decoration time instead of patching `__getattribute__`, which is the root of v0's cache-keying bug,
  the leak and the per-access cost. Inherited methods: wrap the base's function into the subclass's `__dict__`.
- Which dunders, the properties opt-in and the per-method opt-out: proposal 11.
- `otel(LibraryClass)` modifies that class for the whole process (say so in the README). C types and classes that
  can't be modified are unsupported targets: returned unchanged, one warning.

**Done when:** the plain `tests/v0` class and dataclass tests pass under `OTW_IMPL=v1`, and the class-related strict
xfails (first-class-only spans, nested spans through instances, the leak) pass.

### 5. Headers

Keep `x-userinfo` flattening (with the base64 padding fix), passed as `server_request_hook`, and keep the raw header
out of `capture_headers` (e.g. by adding it to the sanitize-fields list).

**Which claims (Q2, decided 2026-10-07): everything except a denylist.** Site-specific claims such as an
`employee_id` come through without being named anywhere. The denylist is
`OTEL_WRAPPER_HEADER_ATTRIBUTES_EXCLUDE`: comma-separated glob patterns matched against the flattened claim path
(`realm_access.roles`, `email`). Denied claims are **dropped** before they're recorded, not scrubbed with a marker.
Everything else is recorded as-is, so the scrubber has to let all remaining `x-userinfo.*` attributes through:
logfire's would otherwise mangle `auth_time`, `session_state` and `iss` (Evidence). Suggested default, to confirm:
credentials and session handles, `*token*,at_hash,c_hash,nonce,session_state,sid`. Personal data (`email`, `name`)
is captured unless added to the list; README says so.

Response headers: `OTEL_WRAPPER_RESPONSE_HEADER_ATTRIBUTES`, symmetric with the request-header variable, defaulting to
v0's hardcoded Kong / Envoy list (`instrument_requests.py`, including `X-Envoy-Upstream-Service-Time` as upstream
latency), via `logfire.instrument_requests(response_hook=...)`.

**Done when:** a Keycloak-style header of every base64 length decodes; a custom claim (`employee_id`) and the
claims logfire would scrub (`auth_time`, `iss`) are recorded unchanged; denylisted claims are absent; the raw base64
value never appears, including with `capture_headers=True`.

### 6. Resource detectors

Everything that describes *the process* (computed once at startup, attached to every export) becomes a
`ResourceDetector` registered under the `opentelemetry_resource_detector` entry-point group, so it works in plain OTel
(`OTEL_EXPERIMENTAL_RESOURCE_DETECTORS=...`) and in logfire. Here we don't register them through logfire: we run them
ourselves and pass the merged result as `resource_attributes` (see "Decided", resource precedence).
Per-call things (code info, headers, log format, Prometheus, class instrumentation) are not resources.

Constraints: `OTEL_SERVICE_NAME` / `OTEL_RESOURCE_ATTRIBUTES` must override our guesses (merge them on top ourselves;
in plain OTel the SDK already merges its `otel` detector last, *verified*); `detect()` must finish well inside
`get_aggregated_resources`' 5 s timeout; resource attributes reach Prometheus only as `target_info`, not as labels on
each series.

**Fork:** if configuration runs before a fork (gunicorn `--preload`, or a module-level `otel.instrument(app)` in the
master), every worker would share one `service.instance.id`. Logfire already patches `process.pid` into the
providers' resources after a fork and reseeds its id generator (*verified* in its source); register an
`os.register_at_fork(after_in_child=...)` hook that does the same for `service.instance.id`.

**Testability:** the detectors take an injectable filesystem root and environment mapping, so tests can fake
`/var/run/secrets/...`, `/etc/hostname` and the cgroup files. The pod-name table is a pure function with
parametrised tests.

**Kubernetes detector.** Semconv's (recommended) derivation, first value found wins:

- `service.name`: annotation `resource.opentelemetry.io/service.name`, label `app.kubernetes.io/instance`, label
  `app.kubernetes.io/name`, then deployment, replicaset, statefulset, daemonset, cronjob, job, pod, container name
- `service.namespace`: the annotation, then `k8s.namespace.name`
- `service.version`: the annotation, label `app.kubernetes.io/version`, then image `<tag>@<digest>` / `<digest>` /
  `<tag>`
- `service.instance.id`: the annotation, then `<k8s.namespace.name>.<k8s.pod.name>.<k8s.container.name>` (we use only
  the annotation; see "Service identity")

What a pod can see without the collector:

| attribute | source |
|---|---|
| `k8s.namespace.name` | Downward API env var if set, else the service-account namespace file, or the projected token payload |
| `k8s.pod.name` | Downward API env var if set, else the token payload (reliable), else `HOSTNAME` / `/etc/hostname` (wrong under `hostNetwork` or `spec.hostname`) |
| `k8s.pod.uid` | token payload |
| workload name | guessed from the pod name (below) |
| labels, annotations | only if the service account may `get pods`: one `GET /api/v1/namespaces/{ns}/pods/{name}` with the token, short timeout, startup only, silent on failure (usually 403) |
| `k8s.container.name` | not available (Downward API env var only) |
| `container.id` | cgroup / mountinfo (contrib `containerid` detector) |

We don't control the collector, but nothing stops it from also running `k8sattributes`; trying here is harmless.

The token payload has `kubernetes.io.pod.name` / `uid` only in bound (projected) tokens, the default since k8s 1.21;
legacy secret-based tokens don't. With `automountServiceAccountToken: false` the whole directory is missing,
namespace file included, hence the Downward API and hostname fallbacks. The API lookup is capped at about 1 s
including connect, and may be switched off (Q12). Detecting "in k8s" at all: `KUBERNETES_SERVICE_HOST` is set.

Pod-name parsing (generated parts use the alphabet `bcdfghjklmnpqrstvwxz2456789`); **never strip to empty**:

| shape | meaning |
|---|---|
| `<name>-<5-10 safe>-<5 safe>` | Deployment + ReplicaSet (unambiguous) |
| `<name>-<8+ digits>-<5 safe>` | CronJob + Job |
| `<name>-<digits>` | StatefulSet |
| `<name>-<5 safe>` | DaemonSet **or** Job: ambiguous, use as `service.name` candidate only |
| anything else | the whole pod name |

Only set `k8s.deployment.name` etc. when the shape is unambiguous.

Long workload names: Kubernetes truncates generated names (a pod's `generateName` prefix is cut to 58 characters
before the 5-character suffix), so a long Deployment name can lose part of its ReplicaSet hash and no longer match
the Deployment shape. Falling back to "the whole pod name" as `service.name` would then create a new service on every
rollout. So the whole pod name may go into `opentelemetry_wrapper.instance.label`, but **never into `service.name`**;
an unrecognised shape leaves `service.name` to the next rule.

**Process detector.** Wraps the SDK's `ProcessResourceDetector(include_command_args=True)` (SDK 1.44 has the opt-in)
and corrects what it gets wrong, rather than reimplementing it. The result, all semconv:

| attribute | value | example |
|---|---|---|
| `process.command_args` | `sys.orig_argv` (3.10+): the real argv, **including the interpreter, its flags and `-m`** | `[...\python.exe, -X, utf8, -m, pytest, -q]` |
| `process.command` | `sys.orig_argv[0]` | |
| `process.args_count` | `len(sys.orig_argv)` | |
| `process.executable.path` / `.name` | `sys.executable` / its base name (`python`, `pypy3`, ...; `sys.implementation.name` when empty, e.g. Pyodide) | |
| `process.runtime.name` / `.version` / `.description` | already set by logfire: `cpython`/`pypy`, version, `sys.version` (includes e.g. "packaged by Anaconda") | |
| `process.owner`, `process.working_directory`, `host.name` | | |

`process.command_line` is left unset (semconv: don't assemble it, use `command_args`). Semconv says args SHOULD NOT be
collected without sanitization, and logfire's scrubbing doesn't touch resources, so sanitize ourselves: logfire's
default patterns **plus `token`**, and also redact the *next* arg when a matching flag has no `=`. Also redact the
password in any URL-shaped argument (`--db-url postgresql://user:pass@host/db` -> `postgresql://user:REDACTED@...`),
which flag-name patterns can't see. `OTEL_WRAPPER_CAPTURE_COMMAND_ARGS=false` drops args entirely.

`process.owner`: `getpass.getuser()` raises when the UID has no passwd entry (arbitrary UIDs, e.g. OpenShift); fall
back to the numeric UID. `process.executable.name` on Windows: Q4.

No semconv attribute says which Python environment it is, so add ours:
`opentelemetry_wrapper.python.environment` = `pyodide` (`sys.platform == 'emscripten'`) | `frozen` (`sys.frozen`) |
`conda` (`<sys.prefix>/conda-meta` exists) | `venv` (`sys.prefix != sys.base_prefix`) | `system`, plus
`...environment.name` (prefix base name) and `...environment.path` (`sys.prefix`). Not `CONDA_DEFAULT_ENV` (see
evidence). PyPy shows up as `process.runtime.name = pypy`; free-threaded builds as
`opentelemetry_wrapper.python.gil = false` (`sys._is_gil_enabled`, 3.13+ only, so `getattr` it).

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

**Done when:** with faked filesystems, each row of the pod-name table and each fallback gives the expected
attributes; `OTEL_SERVICE_NAME` beats the k8s derivation through `logfire.configure`; no k8s API access -> no delay
beyond the cap and no warning; argv secrets (flag, next-arg, URL password) are redacted; forked workers get distinct
`service.instance.id`s.

### 7. Generators and context managers

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

**Done when:** the four prototype cases pass as tests, plus a FastAPI `yield` dependency and a pytest `yield` fixture
decorated with `@otel`.

### 8. Logging

Two handlers on the root logger, nothing else:

- **OTLP:** the SDK's `LoggingHandler`, using logfire's global `LoggerProvider` (see "Decided" and Evidence). Not
  `LogfireLoggingHandler`.
- **stderr:** one-line JSON logs with `otelTraceID` / `otelSpanID` (for log pipelines that aren't OTLP, e.g.
  fluentd/Loki), plus v0's `otelTraceSampled`, `tz_name`, `tz_utc_offset_seconds` and local ISO `asctime`. The ids
  come from a `logging.Filter` on this handler that reads `trace.get_current_span().get_span_context()`: no global
  log record factory (v0's needs an `update_wrapper` workaround) and no `opentelemetry-instrumentation-logging`.

Keep v0's "JSON-encode anything" (NaN/inf, complex, Decimal, modules, functions, classes, extra args; pydantic per the
decision) and long-string truncation. Fix the negative-UTC-offset bug (and recompute the offset per record, for DST).
Logfire's console off unless `OTEL_WRAPPER_LOG_FORMAT=pretty`. v0's `clobber_other_log_handlers` has no equivalent
yet; if needed, `otel.configure(replace_log_handlers=True)`.

`uvicorn.access` logs duplicate the request spans: leave them on stderr but don't send them over OTLP by default.

**Done when:** a log inside a span is exported as a log record with that span's ids and extras; a log outside spans
is exported with zero ids; the JSON line on stderr carries the same ids; instrumenting logging twice leaves two
handlers, not four; `tests/v0` logging tests pass under `OTW_IMPL=v1`.

### 9. Metrics: support both push and scrape

We don't control the platform, so support both and let it choose:

- **Push (OTLP)**: logfire already does this when `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT` (or the generic endpoint) is
  set. Works with a collector or Prometheus 3's OTLP receiver (`/api/v1/otlp/v1/metrics`).
- **Scrape (Prometheus pull)**: keep both v0 modes:
  - standalone server on `OTEL_EXPORTER_PROMETHEUS_PORT` (standard, default 9464), **bound to
    `OTEL_EXPORTER_PROMETHEUS_HOST`** (standard, default `localhost`) instead of v0's hardcoded `localhost`. In k8s it
    must be `0.0.0.0`, because Prometheus scrapes the pod IP from outside.
  - FastAPI route at `OTEL_WRAPPER_PROMETHEUS_PATH` (default `/metrics`), for setups that only expose the app's
    port; excluded from request spans by exact path. Use `app.add_route(path, ...)`, not `app.mount`: a mount also
    serves everything under `/metrics/` and redirects `/metrics` there, which an exact-path exclusion would miss
    (the v0 `TODO.md` notes the trailing-slash behaviour).
- Our reader goes in via `logfire.configure(metrics=MetricsOptions(additional_readers=[PrometheusMetricReader()]))`.
- **Several workers per container** (uvicorn/gunicorn `--workers N`): each worker has its own metrics, but only one
  can bind the Prometheus port (the others get "address in use": warn once, carry on), and the FastAPI route answers
  from whichever worker took the request. That's the `prometheus_client` multiprocess problem. Document: in
  multi-worker deployments use push, or one worker per container.
- **Shutdown:** an unreachable collector can delay process exit while exports retry. Bound the flush at exit (e.g.
  via `OTEL_EXPORTER_OTLP_TIMEOUT`), so a missing collector never holds up a pod's termination or a CLI's exit.

Background, verified:

- Prometheus pulls: it finds targets (host:port) via its own service discovery and requests `metrics_path` (default
  `/metrics`) from its scrape config. Neither HOST nor PORT is a remote address; both describe the app's listening
  socket.
- `prometheus_client.start_http_server` serves metrics on **every** path (`/metrics`, `/`, `/anything/at/all` all
  return 200), which is why the spec defines no path variable. Our FastAPI mount does need a path because it shares
  the app's port.
- The SDK marks both variables experimental, and the exporter only reads them itself when created via
  `OTEL_METRICS_EXPORTER=prometheus` (`_AutoPrometheusMetricReader`). When we build `PrometheusMetricReader` ourselves
  we call `start_http_server` ourselves, so we must read HOST ourselves.
- Trade-off: scrape needs every pod reachable from Prometheus plus discovery config (annotations / ServiceMonitor) but
  gives a free `up` health signal; push only needs outbound access to one known address, but a silent pod looks the
  same as an idle one.
- Logfire's delta temporality preference applies only to its own exporter when sending to Logfire; the exporter built
  from `OTEL_EXPORTER_OTLP_*` uses the SDK default (cumulative), which Prometheus' OTLP receiver expects (*verified*
  in logfire's `config.py`).

**Done when:** standalone server binds `OTEL_EXPORTER_PROMETHEUS_HOST`; `/metrics` on FastAPI returns 200 and makes
no request span, while `/api/metrics` does; with two workers, the second warns once and doesn't crash.

### 10. Packaging

- `requires-python = ">=3.12"` (v0's `">3.8.0"` also excluded 3.8.0 by accident). Side-by-side means v0 users get the
  3.12 floor and logfire in the same release: make that a minor-version bump with a clear note, and the v0 deletion
  1.0.0.
- Core dependencies: `logfire` and the OTel pieces it doesn't bring. Integrations become extras (`[fastapi]`,
  `[sqlalchemy]`, `[requests]`, `[system-metrics]`, mapping onto logfire's own extras) instead of hard dependencies on
  fastapi, uvicorn, sqlalchemy, requests and pydantic. Drop `opentelemetry-exporter-otlp` (it pulls in gRPC).
- Pin `logfire>=5.1,<6`: v1 relies on a few private logfire details, guarded by the canary tests. Logfire itself pins
  `opentelemetry-sdk<1.45`, so our OTel pins follow its.
- `py.typed`.

**Done when:** `pip install opentelemetry_wrapper` without extras imports and runs `@otel`, and each extra enables
its integration; CI covers both.

### 11. Typing

`@otel`, `@otel(...)`, `@otel` on a class and `otel.instrument(x)` keep the decorated object's type: `ParamSpec` /
overloads, so mypy and pyright see the original signature (and the original class). `with otel(...) as span` types
`span` as `trace.Span`. Proposal 6 covers `@property`.

**Done when:** `reveal_type` tests under mypy (and pyright, if available) for each form pass in CI.

## Public API notes

`README_v1.md` is the draft. Background from reviewing the original sketch (`next_version_intended_usage.py`):

- **The one-object shape fits logfire well.** Type dispatch puts the idempotency registry and the never-crash handling
  in one place: function/class -> our decorator over the OTel tracer; app/module/engine -> the idempotent wrappers;
  `with otel:` -> the OTel tracer; integrations go through `otel.instrument`. Unsupported targets are returned
  unchanged with one warning at decoration time.
- **The sketch's shared span stack breaks under concurrency (verified).** `otel` is one module-level object and
  `__enter__`/`__exit__` push/pop `self.spans`. Two asyncio tasks, A entering first and finishing first:
  ```
  (span start) ee96424f      <- A
  (span start) 51e63baa      <- B
  task A entered span ee96424f, exiting...
  (span end) 51e63baa        <- A closes B's span
  task B entered span 51e63baa, exiting...
  (span end) ee96424f
  ```
  Threads have the same problem; hence the `ContextVar` decision (holding an immutable value, workstream 1).
- **`with otel:` has no span name**, and every span needs one; hence call-site auto-naming (workstream 3).

## `TODO.md` triage against the rebuild

| item | status |
|---|---|
| multiple OTLP headers, escaping | use standard `OTEL_EXPORTER_OTLP_HEADERS` (logfire reads it); drop custom `OTEL_EXPORTER_OTLP_HEADER` |
| separate endpoints per signal, rename to `OTEL_COLLECTOR_*` | standard `OTEL_EXPORTER_OTLP_{TRACES,METRICS,LOGS}_ENDPOINT` exist and logfire reads them; gRPC dropped |
| rename env vars to `OTEL_WRAPPER_*` | yes, for the non-standard ones only (table below) |
| env var for console printing | `OTEL_WRAPPER_LOG_FORMAT=json|pretty|off` for logs. The v0 deck also wants local printing of traces and metrics: `pretty` (logfire's console) shows spans; metrics have no local printing yet |
| request headers vs `requests` response headers | standard `OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_{SERVER,CLIENT}_{REQUEST,RESPONSE}` + `..._SANITIZE_FIELDS`; only the JSON flattening stays ours |
| `asyncio.iscoroutinefunction` -> `inspect` | trivial with a 3.12 floor |
| generators and context managers | decided, workstream 7 |
| `with` blocks, `__tracebackhide__`, CI, docs | still ours |
| `varname` | drop; `co_qualname` covers most of the value |
| detect infinite recursion | low priority |
| won't do: sanitizer, sampling | both now come with logfire (scrubbing, `SamplingOptions`); scrubbing does mangle `x-userinfo`, fix in workstream 5 |

## Environment variables

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
| (new) | `OTEL_WRAPPER_LOG_FORMAT` | `json` / `pretty` / `off` |
| (new) | `OTEL_WRAPPER_CAPTURE_COMMAND_ARGS` | default `true` |
| (new) | `OTEL_TRACES_SAMPLER_ARG` | standard; head sampling ratio |

Old names are read for one release with a deprecation warning at startup (except `OTEL_LOG_LEVEL`, see above).
`OTEL_SDK_DISABLED` (standard) is honoured by the SDK; whether it also implies `OTEL_WRAPPER_DISABLED` is Q5.
