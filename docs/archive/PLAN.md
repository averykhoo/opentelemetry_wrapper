ARCHIVED 2026-10-18 (session 2026-10-18a), from PLAN.md.

# v1 plan: rebuild on the plain OpenTelemetry SDK

Started 2026-10-04, last updated 2026-10-18. This is the design for the next major version ("v1"; the current code is
v0), written to be reviewed cold. It started as a rebuild on the Logfire SDK; the 2026-10-17 spike (Q15) showed v1
used little of it, and logfire was dropped (see "Why not logfire").

## For the reviewer

- **State:** design only; no v1 code exists. Committed 2026-10-08 together with `README_v1.md`, `HANDOFF.md`,
  `CLAUDE.md`, the `tests/v0` suite and the v0 fixes listed in `HANDOFF.md`. Reviewed 2026-10-07 (two independent
  reviews, merged); the author's answers (2026-10-07/08, and 2026-10-17/18 after the Q15 spike) are folded into
  "Decided", the proposals and the workstreams. What's still undecided is in "Questions for later".
- **Related files:**
  - `README_v1.md`: draft user-facing API. It reflects the **decided** items below (including proposals 3-8, 10, 11),
    not the open questions.
  - `HANDOFF.md`: repo state, v0 bugs, how to verify.
  - `tests/v0/`: v0 characterization suite, `203 passed, 23 xfailed` (~22 s), run with the repo's conda env
    (`CLAUDE.md`). It's the yardstick for the v0 -> v1 swap.
  - The author's local, untracked notes: the evidence scripts, the full ergonomics review and the v0 talk deck
    transcript. Everything needed from them is summarised here, and the evidence scripts are to become canary tests
    (workstream 0) so they stop depending on one machine.
- **Verified vs opinion:** claims marked *verified* were run against OTel SDK 1.44.0 / contrib 0.65b0 (and logfire
  5.1.1 where logfire is discussed), mypy 2.4, Python 3.12.15 (Windows). Everything else is design opinion.
- **What to check:** (1) the evidence still holds, (2) the decisions are consistent with each other and with
  `README_v1.md`, (3) the proposals, (4) anything missing (compare with `HANDOFF.md` and the v0 deck's to-do list).

## Goal

Build directly on the OpenTelemetry SDK (providers, OTLP/HTTP exporters, samplers, resources) and the contrib
instrumentors, plus what neither provides: the `otel` decorator / context manager, idempotent never-crash
instrumentation, introspection, class support, Kubernetes resource detection, `x-userinfo` flattening, scrubbing,
one-line JSON logs and Prometheus. Python floor: **3.12** (the SDK itself needs >= 3.10).

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
- **No per-span sampling.** Sampling is decided at the root span, via the standard `OTEL_TRACES_SAMPLER` /
  `OTEL_TRACES_SAMPLER_ARG`, which the SDK reads itself (all standard samplers; *verified*: `always_off` exports 0,
  `always_on` with an ARG exports everything).
- **`OTEL_WRAPPER_DISABLED`** means no telemetry at all, for test envs with nowhere to export, where only stack traces
  matter: decorators return the target unchanged (no wrapper frames in tracebacks), `otel.instrument` is a no-op, and
  `with otel as span` yields OTel's standard `NonRecordingSpan` (`trace.INVALID_SPAN`). *Verified:* every method
  works and records nothing, and exceptions propagate untouched. It's read at decoration time, so wrappers that
  already exist also check it at call time (e.g. a test that sets it after import).
- **Our spans come from the OTel tracer** (`trace.get_tracer(...)`), and the exposed span type is OTel's `trace.Span`
  (was proposal 2), the same in enabled and disabled mode.
- **No arguments or return values on spans.** PII, payload size, and parameter names colliding with real attribute
  keys. (*Verified* counter-example: `logfire.instrument` records every argument by default as a top-level attribute
  named after the parameter.) Users add what they need via `attributes={...}` or the span.
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
- **Exporters from the standard env vars:** `OTEL_EXPORTER_OTLP_{,TRACES_,METRICS_,LOGS_}ENDPOINT`, `..._HEADERS`,
  `..._TIMEOUT`, and `OTEL_{TRACES,METRICS,LOGS}_EXPORTER` (`otlp`, `console`, `none`). The OTLP exporters read most of
  these themselves; we only decide which exporters to build.

Telemetry content:

- **`service.name` follows semconv** (the workload name); breaking existing dashboards is accepted. v0's readable
  `ns/workload/pod` or `user@host:main.py` string moves to `opentelemetry_wrapper.instance.label`, and
  `service.instance.id` stays a per-process UUID (workstream 6, "Service identity").
- **Full command line** recorded as `process.command_args` (from `sys.orig_argv`, sanitized), plus our
  `opentelemetry_wrapper.python.environment` (conda / venv / system / pyodide / frozen), so it's clear which
  interpreter ran the process.
- **Stable semconv `code.*` keys** everywhere (workstream 3).
- **Logs are real OTel log records**, never spans: a handler on the root logger feeding a `LoggerProvider` we always
  install (exporter only when an endpoint is set). The handler is the one from `opentelemetry-instrumentation-logging`
  (decided 2026-10-17): *verified*, the SDK's own `LoggingHandler` emits a `DeprecationWarning` at construction in
  1.44 pointing there. A record logged inside a span carries that span's `trace_id` / `span_id` (that's how backends
  show it on the span: it's correlated, not a child in the span tree), `extra={...}` becomes attributes, and the code
  location uses the stable keys (*verified* with the SDK handler; re-check with the contrib one). Logs are **not**
  affected by head sampling: at a 0% ratio the spans are dropped but every log record is still exported (with
  `trace_flags=0`), and a log outside any span has no trace ids. Both span and log capture are tested through the same
  pytest plugin.
- **Resource precedence:** our detectors (guesses) < `OTEL_SERVICE_NAME` / `OTEL_RESOURCE_ATTRIBUTES` < explicit
  `otel.configure(...)` arguments. *Verified* in the spike (`Resource.create()`, then our detectors, then
  `OTELResourceDetector().detect()`, then the explicit attributes): `OTEL_SERVICE_NAME` beats a k8s guess, and an
  explicit `service_name` beats `OTEL_SERVICE_NAME`. Test: `OTEL_SERVICE_NAME` wins in k8s.

Output and dependencies:

- **Console:** one-line JSON logs on stderr (`OTEL_WRAPPER_LOG_FORMAT=json|off`). No pretty console in 1.0 (decided
  2026-10-17; it was logfire's); for local debugging of spans, `OTEL_TRACES_EXPORTER=console` gives the SDK's
  `ConsoleSpanExporter`.
- **Pydantic 2 only, optional, never imported by us.** Pydantic models can only exist if the app imported pydantic, so
  the encoder checks `sys.modules.get('pydantic')` when it meets an unknown object instead of importing it (~120 ms)
  at startup. If it's v2, use encoders for its real types (`isinstance` / type lookup, no duck typing), e.g.
  `BaseModel` -> `model_dump(mode="json")`. Pydantic 1 counts as absent (warn once); `pydantic.v1` models get the
  generic encoder. FastAPI 0.142 requires `pydantic>=2.9` anyway. v0 keeps supporting both.
- **gRPC export dropped** for now: OTLP/HTTP only (collectors listen on 4318 by default), which avoids `grpcio`. A
  `[grpc]` extra can come later if someone needs it.

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

- gRPC export (OTLP/HTTP only, see "Decided").
- Logs as spans.
- Per-span sampling.
- Global dataclass instrumentation.
- Auto-tracing a user's package (`otel.instrument(my_package)`, i.e. logfire's `install_auto_tracing`): it has to run
  before the package is imported, against "import order doesn't matter". A module that isn't a known integration is
  an unsupported target: returned unchanged, one warning.
- Un-instrumentation, except the per-test reset in the pytest plugin. Keep the registry shape that would allow it.
- Recording function arguments or return values.
- Type-checking helpers in the public API.

## Proposals (signed off 2026-10-08; 9 withdrawn 2026-10-17)

From the planning session and from an ergonomics review of `README_v1.md` (findings F1-F12; F1, the disabled-mode
part of F2, and F11 are already decided above). Items 1 and 2 have moved to "Decided"; the numbering is kept because
workstreams refer to it. Amendments from the 2026-10-07 review are marked *(review)*. The author signed off 3-8, 10
and 11 as written here, so they count as decided. 9 was a logfire option and went with logfire.

1. *Decided* ("Configuration").
2. *Decided* ("Our spans come from the OTel tracer"): the exposed span type is OTel's `trace.Span`.
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
   The default filter shows each message once per call site, and an error filter in CI turns misuse into a test
   failure without ever crashing production. The CI recipe is pytest's `filterwarnings =
   error::opentelemetry_wrapper.OtelWrapperWarning` (ini) or `pytest -W error::...`, **not** `python -W
   error::opentelemetry_wrapper.OtelWrapperWarning` / `PYTHONWARNINGS=...`: *verified* (2026-10-18), the interpreter
   parses `-W` before `site` adds site-packages, so a category from an installed package prints `Invalid -W option
   ignored` and the run exits 0. *(review)* Call `warnings.warn` outside our own `try`/`except` blocks so an
   error-filtered warning isn't swallowed, and only once state is consistent (collect warnings during `configure` /
   decoration and emit them at the end), so an error filter can't leave configuration half-built. Whether
   `PYTHONWARNINGS=error` in production may crash at startup is Q8.
8. **`@otel()` and `with otel():`** (F10) mean the same as `@otel` / `with otel:`, silently (v0's sketch warned).
9. *Withdrawn with logfire.* It was logfire's `distributed_tracing=True`. On the plain SDK an incoming `traceparent`
   is simply continued (the default W3C propagator), *verified*: same trace id, no warning. (Logfire without the option
   also exported a log span of its own, "Found propagated trace context".)
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

## Questions for later (need the author's input)

The earlier open questions are settled: type-checking, global dataclass instrumentation, logging options and repo
hosting under "Decided"; auto-tracing and un-instrumentation under "Non-goals"; response headers in workstream 5.
Each question below has a suggested default, used if nobody decides otherwise.

- **Q1. SQLAlchemy engines created later.** *Decided 2026-10-07*, see workstream 2: `otel.instrument(sqlalchemy)`
  instruments globally (later engines included, `connect` spans on); `otel.instrument(engine)` instruments that engine
  only, without `connect` spans; the engine docs state this.
- **Q2. `x-userinfo` by default.** *Decided 2026-10-07*, see workstream 5: capture every claim except a denylist.
  Default denylist confirmed 2026-10-18 (`*token*,at_hash,c_hash,nonce,session_state,sid`; personal data captured
  unless added).
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
- **Q4. `process.executable.name`.** *Decided 2026-10-18:* `os.path.basename(sys.executable)` (*verified*:
  `python.exe` on Windows, same as `psutil.Process().name()`), or `python` when that's empty (e.g. Pyodide). The
  fallback `service.name` is therefore `unknown_service:python.exe` on Windows; `README_v1.md` to match.
- **Q5. `OTEL_SDK_DISABLED=true`** (standard) also means `OTEL_WRAPPER_DISABLED`. *Decided 2026-10-18.*
- **Q6, Q7.** *Obsolete* (logfire's `add_baggage_to_attributes` and `LOGFIRE_*` env vars). Baggage is never copied
  onto spans.
- **Q8. `PYTHONWARNINGS=error` in production** turns our startup warnings into exceptions. Accept that as the one
  sanctioned exception to "never crash" (the user asked for it), or catch it? *Suggested:* accept and document. The
  author finds it defensible; the second opinion (2026-10-18) agrees, with high confidence: a startup crash is
  deterministic and happens before readiness, so a rollout halts without dropping traffic (true only because our
  warnings never fire lazily on a request); catching or downgrading would second-guess an explicit operator request,
  and `warnings.catch_warnings` isn't thread-safe. Mainstream libraries (requests, urllib3, SQLAlchemy, pydantic) use
  plain `warnings.warn`; the OTel SDK mostly uses `logging`, so proposal 7 is a deliberate departure. *Decided
  2026-10-18:* accepted, with proposal 7's amendments (emit after state is consistent; the pytest CI recipe).
- **Q9. Settings that may change after configuration is built:** the log level only. *Decided 2026-10-18.*
- **Q10. Pytest plugin opt-in trigger:** requesting the `otel_spans` / `otel_logs` fixture, plus an ini option for
  whole-suite use. *Decided 2026-10-18.*
- **Q11. `otel.instrument()` with no arguments:** logging, requests, system metrics (the `[system-metrics]` extra);
  never apps, engines or SQLAlchemy. That's v0's `instrument_all()` set minus global dataclass instrumentation
  (dropped). *Decided 2026-10-18.*
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
- **Q13. Function name on log records:** accept the bare `record.funcName` the handler writes (`load_config`); a log
  record doesn't carry the qualified name, and rebuilding it means a stack walk per log call. *Decided 2026-10-18.*
- **Q14. Sign-off on proposals 3-11.** *Decided 2026-10-08:* 3-8, 10 and 11 signed off as amended; 9 withdrawn with
  logfire.
- **Q15. Is logfire still worth depending on?** *Decided 2026-10-17: no*, see "Why not logfire".
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

## Why not logfire (Q15, decided 2026-10-17)

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

## Evidence (OTel SDK 1.44.0 / contrib 0.65b0, logfire 5.1.1, Python 3.12.15)

All reproduced by running small scripts; results recorded here because the scripts were throwaway (kept locally,
untracked). Workstream 0 turns the ones about upstream behaviour into canary tests. The logfire comparisons predate the
Q15 decision and are kept as background: v1 doesn't use logfire.

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
`code.line.number`, `code.column.number`, `code.stacktrace`. The SDK's `LoggingHandler` writes the stable keys.

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
- **Canary tests** (`tests/upstream/`): one test per upstream behaviour or semi-private API we rely on, so an OTel
  upgrade fails a test instead of production: the `EngineTracer` import path and signature; the `contextmanager`
  shared-`__code__` trick; `ReadableSpan(...)` constructor kwargs and the `opentelemetry.sdk._logs` names the
  scrubbing wrappers use; the SDK's post-fork resource update (`_handle_fork`, Linux CI only); `ProxyTracer` picking up
  a later provider; resource precedence; `FastAPIInstrumentor.instrument_app` idempotency and `exclude_spans`. These
  replace the local evidence scripts.
- **Upstream bumps without anyone watching CI** (the author doesn't check CI results; decided 2026-10-18): automation
  is only worth having if it updates the repo by itself. Use **Renovate** (GitHub app) rather than a home-grown job:
  it opens a PR that raises the OTel caps, the PR's CI runs the suite and the canaries, and Renovate **auto-merges
  only if everything passes**; a failing PR just sits there and the old pins keep protecting users. OTel has shipped
  breaking changes without warning (twice during v0), which is why the pins stay strict (workstream 10). Config to
  get right (not verified yet): group all `opentelemetry-*` packages into one PR (SDK and contrib release in
  lockstep); a range strategy that moves the upper cap (`<1.45` -> `<1.46`); contrib versions like `0.66b0` are PEP
  440 pre-releases, so Renovate must not ignore them as unstable.
- **Auto-release of dependency-only bumps** (decided 2026-10-18): when such a PR merges, a release workflow bumps the
  patch version and publishes to PyPI (trusted publishing, no stored token). Only for merges that change nothing but
  dependency specifiers; anything else is released by hand. A patch release (not `.postN`) is the conventional
  signal, and both are picked up by default. If a bump should ever be opt-in, publish it as a pre-release (`rcN` /
  `.devN`), which pip skips unless asked (`--pre` or an explicit pre-release specifier); *verified* with `packaging`'s
  filtering. Local versions (`+tag`) can't be uploaded to PyPI.
- Without Renovate, the same check runs locally as `pytest -m upstream` whenever someone works on the repo.
- In-process fixtures strip `OTEL_*` (`tests/conftest.py` already does).
- Tests for the two-tasks-plus-a-thread interleaving from "Public API notes".
- A micro-benchmark of per-call overhead (v0 vs v1, with and without an exporter), so a regression is visible.
- **CI:** GitHub Actions on push and on pull requests (none yet; `.github/workflows/` doesn't exist). Kept
  (decided 2026-10-18): Renovate's auto-merge depends on it, and whoever pushes watches the run. Matrix: Python 3.12 / 3.13 / 3.14 × with and
  without the optional extras, so "optional at call time" is actually exercised. Keep the steps in a script so the
  workflow file stays thin.

**Order:** 0 -> 1 (configure, decorator, `with otel:`) -> 3 -> 7 -> 4 -> 5 -> 2 -> 8 -> 9, with 6 in parallel (pure
OTel, testable alone) and 10-11 alongside 1. Each workstream ends with a one-line **Done when**, given below.

**Done when:** the suite is committed, `OTW_IMPL=v1` runs (failures expected until v1 exists), canaries pass, CI runs
on push.

### 1. Configure, and idempotent, never-crash wrappers over the SDK and contrib

- `configure`: providers for all three signals, OTLP/HTTP exporters per the standard env vars (only when an endpoint
  is set), the SDK's own sampler handling, resources per "Resource precedence", the scrubbing exporter wrappers
  (workstream 5b), swappable span and log sinks for the pytest plugin, the "someone else configured first" policy,
  a bounded shutdown (workstream 9), and an at-exit flush for forked `multiprocessing` children
  (`multiprocessing.util.Finalize`). Global providers are set once, under the configuration lock. Expect ~450 lines.
- One function per integration (`fastapi`, `requests`, `sqlalchemy`, `logging`, system metrics) that records what it
  already instrumented (weakref where the target is an object) and swallows/warns-once on failure, at instrumentation
  time only. Also warn once when an instrumentor hits a `DependencyConflict`: upstream only logs it and produces no
  spans (`HANDOFF.md`, the sqlalchemy and requests cases), which isn't an exception we'd catch.
- FastAPI: `FastAPIInstrumentor.instrument_app(app, exclude_spans=['send', 'receive'], ...)` (*verified*: only the
  server span remains, and a second call neither raises nor duplicates spans).
- `otel.instrument(app)` after the app has started can't add middleware (Starlette raises): warn once, return the app.
- Our own decorator creates spans with the OTel tracer and `CodeInfo` attributes (see "Decided"), and keeps the
  "already instrumented, return the cached wrapper" logic, keyed on the underlying function (see "v0 lessons").
- Wrappers keep the target's kind: `inspect.iscoroutinefunction`, `isgeneratorfunction`, `isasyncgenfunction` and the
  signature (via `__wrapped__`) must be the same as the original's. FastAPI uses them to pick threadpool vs `await`
  and to treat `yield` dependencies as context managers; pytest does the same for fixtures.
- `with otel:` keeps its state in a `ContextVar` holding an immutable value: `set()` on enter, `reset(token)` on
  exit. Never a list that gets mutated: `copy_context()` copies the mapping, not the values, so a mutated list leaks
  between tasks.
- Exception handling per Q3; re-raise with a bare `raise` so tracebacks are untouched, and set `__tracebackhide__`
  (pytest) / `__traceback_hide__` (Sentry and others) in wrapper frames.

**Done when:** functions (sync, async), `with otel:` / `with otel('x'):`, configure (implicit, explicit, final once
built, someone-else-configured-first), disabled mode and the pytest plugin pass their tests; the plain `tests/v0` decorator tests pass under
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
`is_class`, end line) under our own prefix, e.g. `opentelemetry_wrapper.code.*`. Auto-name `with otel:` blocks from
the call site (see proposal 5 for the naming).

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
Everything else is recorded as-is, so the scrubber lets all remaining `http.request.header.x-userinfo.*` attributes
through (a generic scrubber would mangle `auth_time`, `session_state` and `iss`; see Evidence). Default (confirmed
2026-10-18): credentials and session handles, `*token*,at_hash,c_hash,nonce,session_state,sid`. Personal data
(`email`, `name`) is captured unless added to the list; README says so.

Response headers: `OTEL_WRAPPER_RESPONSE_HEADER_ATTRIBUTES`, symmetric with the request-header variable, defaulting to
v0's hardcoded Kong / Envoy list (`instrument_requests.py`, including `X-Envoy-Upstream-Service-Time` as upstream
latency), via `RequestsInstrumentor().instrument(response_hook=...)`.

**Done when:** a Keycloak-style header of every base64 length decodes; a custom claim (`employee_id`) and the
claims a generic scrubber would mangle (`auth_time`, `iss`) are recorded unchanged; denylisted claims are absent; the
raw base64 value never appears, including with header capture on.

### 5b. Scrubbing

Our own rules, designed from examples (2026-10-18), not copied from logfire's list. Applied in wrappers around every
exporter we build (spans: attributes, event and link attributes; logs: attributes and body; the in-memory test
exporters too), on the exporter thread, so the cost stays off the caller's path; also to the stderr JSON logs
(decided 2026-10-17) and, via `scrub_argv`, to `process.command_args`. Defence in depth: the primary controls remain
"no arguments on spans" and the header denylist. Anything not behind our wrappers (a user's own processors) is
unscrubbed; README says so.

- **Two kinds of rules.** Key rules: the key's last word names a secret (`password`, `client_secret`,
  `authorization`, `cookie`, ...) -> the whole value is redacted. Value rules: the value *looks like* a secret by
  format, whatever its key (Vault `hvs.`/`hvb.`/`hvr.`, GitHub / GitLab / Slack / Stripe / AWS / Google keys, JWTs,
  `Bearer` / `Basic` credentials, PEM private keys, passwords in URL userinfo, secret-named URL query parameters,
  inline `key=value`) -> only the secret part is redacted (`Bearer [REDACTED]`, `postgresql://user:[REDACTED]@db`,
  `password=[REDACTED]`), so messages stay readable. Rules may have a post-match check (e.g. `Basic` must decode to
  `user:pass`), which keeps false positives like "Basic configuration" out.
- **Not redacted:** `input_tokens`, `tokenizer`, `token_count`, `password_policy`, `passwordless`, trace ids, UUIDs,
  digests. SQL keeps its statement with literals redacted. Exception messages and stack traces get value rules only.
  Command line: `--token abc` redacts the next argument (2+ character flags only; `-p hunter2` is ambiguous).
- **Known false positives** (accepted for now; all verified on the prototype):
  - keys: pagination cursors (`next_token`, `page_token`, `continuation_token`), `cancellation_token`, boolean flags
    (`is_secret`, `has_password`), `access_key` (often a key *id*);
  - inline text: bare `token:` (`token: 7`, `Token: Expired`), prose after a secret name (`password: The password
    must...` redacts "The"), `pwd: /home/bob`, `private_key: /path/to/key.pem`;
  - URL query parameters: `?key=`, `?auth=`, `?page_token=`;
  - value formats: `sk-` slugs (`sk-blue-widget-2024-edition-pro`), 20-character all-caps words starting `ASIA`
    (`ASIAPACIFICREGION123`).
- AWS (`AKIA`/`ASIA`) and Google (`AIza`) keys must end at a word boundary, so a longer run isn't truncated and
  partly redacted.
- **Engine:** rules live in a registry and compile into one matcher behind a small engine interface, so the engine can
  change without touching the rules or callers. Rules stay in a regex subset an automaton library can handle (no
  backreferences, no lookarounds), enforced by a test; which rule fired is found by re-testing the rules on the matched
  text only. Benchmark (2026-10-18, µs per call; 10 attributes / 2 KB body containing "password" / 2 KB body with a
  secret):

  | engine | attrs | "password" body | secret body |
  |---|--:|--:|--:|
  | one `re` per rule | 137 | 1075 | 991 |
  | `re` alternation, named groups | 191 | 1890 | 2070 |
  | `re` alternation, factored, no groups, 32-char prefilter (stdlib default) | 99 | 480 | 480 |
  | greenery automaton union, run on `re` | 94 | 382 | 402 |
  | `re2`, factored, named groups | 151 | 20 | 94 |
  | hybrid: `re` below 256 chars, `re2` above | 78 | 17 | 103 |

  Findings: under `re`, named groups cost ~2x on bodies and ~40% on attributes, and a plain alternation is *slower*
  than one regex per rule (factoring the shared boundaries and dropping groups is what wins). Under `re2`, groups cost
  nothing. The `regex` module is 1.5-2x slower than `re` everywhere. A greenery union only gains ~25% over the
  factored `re` alternation, takes ~3 s to build and can't express `\A`/`\Z`, lazy quantifiers or named groups:
  keep it out of the runtime. `interegular` is useful as a **test-time lint** for overlapping rules (it found one
  overlap, resolved by rule order). `re2` has ~4 µs fixed overhead per call, hence the hybrid. Prefilter at 32
  characters costs nothing measurable on short strings and is 15x faster on trigger-free bodies. Possessive
  quantifiers / atomic groups and Hyperscan were measured too; engine choice and numbers: Q16.
- Never crash: if scrubbing a value fails, drop it (fail closed) and note it. Redactions are listed in an
  `opentelemetry_wrapper.scrubbed` attribute (paths and rule names, never the values).

**Done when:** every must-redact and must-keep example passes; the stderr JSON logs, the in-memory test exporters and
`process.command_args` go through the same scrubber; the per-span overhead benchmark (workstream 0) includes it.

### 6. Resource detectors

Everything that describes *the process* (computed once at startup, attached to every export) becomes a
`ResourceDetector` registered under the `opentelemetry_resource_detector` entry-point group, so it also works in plain
OTel without our `configure` (`OTEL_EXPERIMENTAL_RESOURCE_DETECTORS=...`). Our `configure` runs them itself and merges
per "Decided", resource precedence. Per-call things (code info, headers, log format, Prometheus, class
instrumentation) are not resources.

Constraints: `OTEL_SERVICE_NAME` / `OTEL_RESOURCE_ATTRIBUTES` must override our guesses (*verified* in the Q15 spike);
`detect()` must finish well inside `get_aggregated_resources`' 5 s timeout; resource attributes reach Prometheus only
as `target_info`, not as labels on each series.

**Fork:** if configuration runs before a fork (gunicorn `--preload`, or a module-level `otel.instrument(app)` in the
master), the workers inherit the master's resource. The SDK (1.44) handles most of it: its providers register
`os.register_at_fork` hooks that re-run the *process-dependent* detectors it builds from env vars (by default the
`service.instance.id` one) and update existing tracers (*read in source*, not run: no fork on Windows). Our own
detectors' process-dependent values (`process.pid`) aren't re-run that way. Check on Linux CI; if they're stale,
correct the resource in our exporter wrappers (public API) rather than writing to providers' private attributes.
Batch processors restart their threads after a fork themselves. The at-exit flush for forked children is in
workstream 1.

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
| labels, annotations | a Downward API volume (`OTEL_WRAPPER_PODINFO_DIR`, default `/etc/podinfo`, files `labels` / `annotations`), or single-key `fieldRef` env vars. Never the Kubernetes API (Q12) |
| `k8s.container.name` | not available (Downward API env var only) |
| `container.id` | cgroup / mountinfo (contrib `containerid` detector) |

We don't control the collector, and nothing stops it from also running `k8sattributes`. We never call the Kubernetes
API ourselves (Q12: security tooling flags both the connection and the usual 403).

Downward API volume files: one `key="value"` per line, keys sorted, values quoted with Go's `strconv.Quote`, the
directory updated atomically through a `..data` symlink (*verified* in the Kubernetes docs and
`pkg/fieldpath/fieldpath.go`, second review). Parse each value with `ast.literal_eval` (Go quoting is compatible with
Python string escapes for valid UTF-8, *not run*), falling back to the raw text. A missing directory is normal and
silent.

The token payload has `kubernetes.io.pod.name` / `uid` only in bound (projected) tokens, the default since k8s 1.21;
legacy secret-based tokens don't. With `automountServiceAccountToken: false` the whole directory is missing,
namespace file included, hence the Downward API and hostname fallbacks. Detecting "in k8s" at all:
`KUBERNETES_SERVICE_HOST` is set.

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
| `process.executable.path` / `.name` | `sys.executable` / its base name (Q4: `python.exe` on Windows, `python3.12`, `pypy3`, ...; `python` when empty, e.g. Pyodide) | |
| `process.runtime.name` / `.version` / `.description` | from the SDK detector (*verified* it sets them): `cpython`/`pypy`, version, `sys.version` (includes e.g. "packaged by Anaconda") | |
| `process.owner`, `process.working_directory`, `host.name` | | |

`process.command_line` is left unset (semconv: don't assemble it, use `command_args`). Semconv says args SHOULD NOT be
collected without sanitization, and exporter-side scrubbing doesn't see resources, so the detector runs the scrubber's
`scrub_argv` (workstream 5b): secret-named flags, the *next* arg when such a flag has no `=`, and the password in any
URL-shaped argument (`--db-url postgresql://user:pass@host/db` -> `postgresql://user:[REDACTED]@...`).
`OTEL_WRAPPER_CAPTURE_COMMAND_ARGS=false` drops args entirely.

`process.owner`: `getpass.getuser()` raises when the UID has no passwd entry (arbitrary UIDs, e.g. OpenShift); fall
back to the numeric UID.

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
attributes; `OTEL_SERVICE_NAME` beats the k8s derivation through `configure`; labels and annotations are read from a
faked Downward API volume (including escaped values), and a missing volume is silent; argv secrets (flag, next-arg, URL password) are redacted; forked workers get distinct
`service.instance.id`s and their own `process.pid` (Linux CI).

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

- **OTLP:** the `LoggingHandler` from `opentelemetry-instrumentation-logging` (the SDK's own is deprecated in 1.44,
  see "Decided"), on our `LoggerProvider`. Use only its handler, not `LoggingInstrumentor`'s record-factory
  injection. Re-check with this handler what PLAN verified with the SDK one (ids, extras, stable `code.*` keys).
- **stderr:** one-line JSON logs with `otelTraceID` / `otelSpanID` (for log pipelines that aren't OTLP, e.g.
  fluentd/Loki), plus v0's `otelTraceSampled`, `tz_name`, `tz_utc_offset_seconds` and local ISO `asctime`. The ids
  come from a `logging.Filter` on this handler that reads `trace.get_current_span().get_span_context()`: no global
  log record factory (v0's needs an `update_wrapper` workaround). The line goes through the scrubber (workstream 5b)
  before it's written.

Keep v0's "JSON-encode anything" (NaN/inf, complex, Decimal, modules, functions, classes, extra args; pydantic per the
decision) and long-string truncation. Fix the negative-UTC-offset bug (and recompute the offset per record, for DST).
`OTEL_WRAPPER_LOG_FORMAT=off` turns the stderr handler off. v0's `clobber_other_log_handlers` has no equivalent yet;
if needed, `otel.configure(replace_log_handlers=True)`.

`uvicorn.access` logs duplicate the request spans: leave them on stderr but don't send them over OTLP by default.

**Done when:** a log inside a span is exported as a log record with that span's ids and extras; a log outside spans
is exported with zero ids; the JSON line on stderr carries the same ids; instrumenting logging twice leaves two
handlers, not four; `tests/v0` logging tests pass under `OTW_IMPL=v1`.

### 9. Metrics: support both push and scrape

We don't control the platform, so support both and let it choose:

- **Push (OTLP)**: a `PeriodicExportingMetricReader(OTLPMetricExporter())` when `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT`
  (or the generic endpoint) is set. Works with a collector or Prometheus 3's OTLP receiver (`/api/v1/otlp/v1/metrics`).
  The SDK default temporality (cumulative) is what Prometheus' OTLP receiver expects.
- **Scrape (Prometheus pull)**: keep both v0 modes:
  - standalone server on `OTEL_EXPORTER_PROMETHEUS_PORT` (standard, default 9464), **bound to
    `OTEL_EXPORTER_PROMETHEUS_HOST`** (standard, default `localhost`) instead of v0's hardcoded `localhost`. In k8s it
    must be `0.0.0.0`, because Prometheus scrapes the pod IP from outside.
  - FastAPI route at `OTEL_WRAPPER_PROMETHEUS_PATH` (default `/metrics`), for setups that only expose the app's
    port; excluded from request spans by exact path. Use `app.add_route(path, ...)`, not `app.mount`: a mount also
    serves everything under `/metrics/` and redirects `/metrics` there, which an exact-path exclusion would miss
    (the v0 `TODO.md` notes the trailing-slash behaviour).
- Our `PrometheusMetricReader` goes into the `MeterProvider`'s readers at configure time (readers can't be added
  later, one more reason configuration is final once built). *Verified* in the spike: `target_info` is served.
- **Several workers per container** (uvicorn/gunicorn `--workers N`): each worker has its own metrics, but only one
  can bind the Prometheus port (the others get "address in use": warn once, carry on), and the FastAPI route answers
  from whichever worker took the request. That's the `prometheus_client` multiprocess problem. Document: in
  multi-worker deployments use push, or one worker per container.
- **Shutdown:** an unreachable collector can delay process exit while exports retry. Bound the flush at exit (e.g.
  via `OTEL_EXPORTER_OTLP_TIMEOUT`), so a missing collector never holds up a pod's termination or a CLI's exit.
  (*Verified* in the spike: with a dead collector and a 1 s timeout, shutdown took ~2 s.)

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

**Done when:** standalone server binds `OTEL_EXPORTER_PROMETHEUS_HOST`; `/metrics` on FastAPI returns 200 and makes
no request span, while `/api/metrics` does; with two workers, the second warns once and doesn't crash.

### 10. Packaging

- `requires-python = ">=3.12"` (v0's `">3.8.0"` also excluded 3.8.0 by accident). Side-by-side means v0 users get the
  3.12 floor in that release: make it a minor-version bump with a clear note, and the v0 deletion 1.0.0.
- Core dependencies: `opentelemetry-api`, `-sdk`, `-exporter-otlp-proto-http`, `-semantic-conventions`,
  `-instrumentation-logging` (its handler, see workstream 8) and `-exporter-prometheus`. Integrations become extras
  (`[fastapi]`, `[sqlalchemy]`, `[requests]`, `[system-metrics]`, each pulling the matching contrib instrumentor),
  plus `[hyperscan]` (the faster scrubbing engine, Q16), instead of hard dependencies on
  fastapi, uvicorn, sqlalchemy, requests and pydantic. Dev dependencies add `interegular` (rule-overlap lint). Drop
  `opentelemetry-exporter-otlp` (it pulls in gRPC).
- **Strict OTel pins, as in v0** (decided 2026-10-18): OTel has shipped breaking changes without warning, twice
  during v0's development. Cap the SDK family at the next minor (e.g. `opentelemetry-sdk>=1.44,<1.45`) and pin the
  contrib packages to the matching `0.XbY` window (they release in lockstep). Renovate's auto-merged bump PRs
  (workstream 0) and the canaries decide when a cap moves; the difference from logfire's caps is that we set the
  pace.
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

- **The one-object shape fits.** Type dispatch puts the idempotency registry and the never-crash handling
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
| multiple OTLP headers, escaping | use standard `OTEL_EXPORTER_OTLP_HEADERS` (the OTLP exporters read it); drop custom `OTEL_EXPORTER_OTLP_HEADER` |
| separate endpoints per signal, rename to `OTEL_COLLECTOR_*` | standard `OTEL_EXPORTER_OTLP_{TRACES,METRICS,LOGS}_ENDPOINT` exist and the exporters read them; gRPC dropped |
| rename env vars to `OTEL_WRAPPER_*` | yes, for the non-standard ones only (table below) |
| env var for console printing | `OTEL_WRAPPER_LOG_FORMAT=json|off` for logs. The v0 deck also wants local printing of traces and metrics: the standard `OTEL_TRACES_EXPORTER=console` / `OTEL_METRICS_EXPORTER=console` (SDK console exporters) |
| request headers vs `requests` response headers | standard `OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_{SERVER,CLIENT}_{REQUEST,RESPONSE}` + `..._SANITIZE_FIELDS`; only the JSON flattening stays ours |
| `asyncio.iscoroutinefunction` -> `inspect` | trivial with a 3.12 floor |
| generators and context managers | decided, workstream 7 |
| `with` blocks, `__tracebackhide__`, CI, docs | still ours |
| `varname` | drop; `co_qualname` covers most of the value |
| detect infinite recursion | low priority |
| won't do: sanitizer, sampling | sampling: the SDK's standard samplers. Sanitizer: now done after all (workstream 5b), because spans and logs from instrumentors carry headers, URLs and extras we don't control |

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
| (new) | `OTEL_WRAPPER_LOG_FORMAT` | `json` / `off` |
| (new) | `OTEL_WRAPPER_CAPTURE_COMMAND_ARGS` | default `true` |
| (new) | `OTEL_WRAPPER_PODINFO_DIR` | ours; Downward API volume with `labels` / `annotations`, default `/etc/podinfo` |
| (new) | `OTEL_TRACES_SAMPLER` / `OTEL_TRACES_SAMPLER_ARG` | standard; read by the SDK |
| (new) | `OTEL_{TRACES,METRICS,LOGS}_EXPORTER` | standard; `otlp` (default when an endpoint is set), `console`, `none` |

Old names are read for one release with a deprecation warning at startup (except `OTEL_LOG_LEVEL`, see above).
`OTEL_SDK_DISABLED=true` (standard) also means `OTEL_WRAPPER_DISABLED` (Q5).
