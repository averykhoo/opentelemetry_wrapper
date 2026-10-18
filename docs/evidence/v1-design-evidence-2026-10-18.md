# v1 design evidence (OTel SDK 1.44.0 / contrib 0.65b0, logfire 5.1.1, Python 3.12.15)

FROZEN 2026-10-18. `PLAN.md` § "Evidence" and § "Public API notes", verbatim as committed at `24a0430`. The
decisions cite it (DEC-1, DEC-2, DEC-15, DEC-20, DEC-31 among them), and workstream 0 (OTW-2) turns the claims
about upstream behaviour into canary tests. "`HANDOFF.md`" below means the old note, now in
`docs/evidence/history-to-2026-10-18.md`; "workstream n" means the task whose alias is `WSn` (OTW-1 lists them).

## Evidence

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
