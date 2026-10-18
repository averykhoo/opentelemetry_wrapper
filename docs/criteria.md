# Criteria

LIVING. The definition of correct (FRAMEWORK §3.3). One row per criterion; ids are `AC-n`, never reused
or renumbered. `status` is `planned`, `tested` or `retired`: a criterion moves to `tested` only
when a test claims it and that test has been seen to fail with the behaviour broken.

**How a test claims a criterion.** In a pytest repo, mark the test
`@pytest.mark.criterion("AC-n")` and register the marker in the pytest config
(`markers = ["criterion(id): the AC-n criterion in docs/criteria.md that this test claims"]`).
Elsewhere, put `criterion: AC-n` in a comment on the line above the test. Either way, the trace
check by hand is: every `tested` row has at least one claiming test, and every claimed id has a
row here.

| Id | Criterion | Story | Status | Claimed by |
|---|---|---|---|---|
| AC-1 | A sync or async function decorated with `@otel` (or `@otel()`) produces one span per call, named from module + `co_qualname`, with stable `code.*` attributes; the wrapper keeps the target's kind and signature | STORY-1, DEC-19, DEC-31, DEC-50 | planned | |
| AC-2 | `with otel:` and `with otel('x'):` open a span that is current inside the block; an unnamed block is named after the enclosing function, never a line number | STORY-1, DEC-47 | planned | |
| AC-3 | Configuration is implicit (env vars, at the first span, only if nothing configured yet) and explicit (`otel.configure`); it is final once built: a later different call warns once and is ignored, except the log level; another provider configured first is attached to or left alone, never a crash | STORY-1, DEC-27, DEC-9 | planned | |
| AC-4 | With `OTEL_WRAPPER_DISABLED` or `OTEL_SDK_DISABLED=true`, decorators return the target unchanged, `otel.instrument` is a no-op, and `with otel as span` yields `trace.INVALID_SPAN`; exceptions propagate untouched | STORY-3, DEC-24, DEC-5 | planned | |
| AC-5 | The pytest plugin's `otel_spans` / `otel_logs` fixtures capture exactly what would be exported (scrubbed), reset per test; exporters switch off only on opt-in | STORY-1, DEC-27, DEC-10 | planned | |
| AC-6 | Decorating or instrumenting the same target twice behaves as once: one span per call, including methods reached through instances, `__call__` and `__post_init__` | STORY-2, DEC-19 | planned | |
| AC-7 | An unsupported target is returned unchanged with one `OtelWrapperWarning`; a failure inside the wrapper never raises into the app | STORY-3, DEC-49 | planned | |
| AC-8 | The plain `tests/v0` tests pass under `OTW_IMPL=v1` (the `v0_specific` ones are v0-only) | STORY-10, DEC-38 | planned | |
| AC-9 | Two pre-existing SQLAlchemy engines and one created later and passed in all produce `SELECT` spans; after `otel.instrument(sqlalchemy)`, an engine created later and never passed in produces `connect` and `SELECT` spans; an engine instrumented twice gives one span per query; `AsyncEngine` works; without sqlalchemy: a warning, no crash | STORY-1, DEC-1 | planned | |
| AC-10 | Every row of the introspection evidence table (`docs/evidence/v1-design-evidence-2026-10-18.md`) gives the right name, file and line, including callable instances and `__wrapped__` without `@wraps`; no source file needed; no strong references to user objects | STORY-5, DEC-21, DEC-31 | planned | |
| AC-11 | The plain `tests/v0` class and dataclass tests pass under `OTW_IMPL=v1`, and the class-related strict xfails (first-class-only spans, nested spans through instances, the leak) pass | STORY-6, DEC-53 | planned | |
| AC-12 | A Keycloak-style `x-userinfo` header of every base64 length decodes; a custom claim and the claims a generic scrubber would mangle (`auth_time`, `iss`) are recorded unchanged; denylisted claims are absent; the raw base64 value never appears, even with header capture on | STORY-9, DEC-2 | planned | |
| AC-13 | Every must-redact and must-keep scrubbing example passes, on every exporter we build, the in-memory test exporters and the stderr JSON logs; a value that fails to scrub is dropped and noted | STORY-9, DEC-58, DEC-16 | planned | |
| AC-14 | With faked filesystems, each pod-name shape and each fallback gives the expected attributes; `OTEL_SERVICE_NAME` beats the k8s derivation through `configure`; labels and annotations are read from a faked Downward API volume (escaped values included), and a missing volume is silent | STORY-7, DEC-12, DEC-29, DEC-33 | planned | |
| AC-15 | Secrets in the command line (a secret-named flag, the next argument, a URL password) are redacted in `process.command_args` | STORY-9, DEC-30 | planned | |
| AC-16 | Forked workers get distinct `service.instance.id`s and their own `process.pid` (Linux CI) | STORY-7, DEC-29 | planned | |
| AC-17 | The four generator and context-manager prototype cases pass, plus a FastAPI `yield` dependency and a pytest `yield` fixture decorated with `@otel` | STORY-1, DEC-22 | planned | |
| AC-18 | A log inside a span is exported as a log record with that span's ids and extras; outside spans, with zero ids; the stderr JSON line carries the same ids; instrumenting logging twice leaves two handlers, not four | STORY-8, DEC-32, DEC-34 | planned | |
| AC-19 | The Prometheus server binds `OTEL_EXPORTER_PROMETHEUS_HOST`; `/metrics` on FastAPI returns 200 and makes no request span while `/api/metrics` does; a second worker that cannot bind warns once and carries on | STORY-1, DEC-59 | planned | |
| AC-20 | `pip install opentelemetry_wrapper` without extras imports and runs `@otel`, and each extra enables its integration | STORY-10, DEC-35, DEC-36, DEC-57 | planned | |
| AC-21 | `reveal_type` checks under mypy keep the decorated object's type for `@otel`, `@otel(...)`, `@otel` on a class and `otel.instrument(x)`; `with otel(...) as span` types `span` as `trace.Span` | STORY-1, DEC-25 | planned | |
| AC-22 | Our own entry points emit no spans or logs at runtime; every warning fires at startup, decoration or instrumentation time, once per call site | STORY-4, DEC-49 | planned | |
| AC-23 | A canary test per upstream behaviour or semi-private API we rely on passes on the pinned OTel versions and fails when that behaviour changes | STORY-10, DEC-54, DEC-57 | planned | |
| AC-24 | An OTel bump PR auto-merges only when CI passes, and a dependency-only merge publishes a patch release with no stored token | STORY-10, DEC-54, DEC-55 | planned | |
| AC-25 | An exception raised through spans sets status and attributes per DEC-3's table: ERROR with the stack trace on the innermost span, `error.type` only on outer ones; `StopIteration`, `GeneratorExit`, `CancelledError` and `KeyboardInterrupt` leave the status unset with their marker attributes; `SystemExit` is ERROR only for a non-zero code; the exception re-raises untouched | STORY-3, DEC-3 | planned | |
| AC-26 | `from opentelemetry_wrapper import otel` works; `otel.span` is never `None` (a no-op span outside spans), and `otel.trace_id` / `otel.span_id` are hex strings, all zeros without a span or with telemetry disabled | STORY-1, DEC-45, DEC-46 | planned | |
| AC-27 | v0's environment variable names are read for one release with a startup warning, except `OTEL_LOG_LEVEL`, which only warns; an OTLP endpoint on port 4317 or `grpc://`, `OTEL_EXPORTER_OTLP_PROTOCOL=grpc` and `OTEL_EXPORTER_OTLP_INSECURE` each warn at startup | STORY-10, DEC-52, DEC-59 | planned | |
| AC-28 | Every example in `README_v1.md` runs as written, with `from opentelemetry_wrapper import otel` as its only setup; exporting traces, logs and metrics over OTLP needs no code beyond that and `OTEL_EXPORTER_OTLP_ENDPOINT`; no example imports `opentelemetry.sdk` or anything private (`_logs` and the like) | STORY-11, DEC-73 | planned | |
| AC-29 | With no environment variables and no `otel.configure` call, an app using `otel` runs, writes one-line JSON logs to stderr and exports nothing; every environment variable and `configure` option the wrapper reads has its default in `README_v1.md`'s configuration tables, and a test compares the two | STORY-12, DEC-73 | planned | |

Every row was drafted at adoption (2026-10-18), most from a workstream's "Done when" in the pre-adoption
`PLAN.md`; AC-22 comes from principle 3, AC-24 and AC-25 to AC-27 from the decisions they cite. AC-28 and AC-29 were drafted in session 2026-10-18e for the goals the
owner added from the v0 talk (DEC-73). The task that
delivers each is in the epic OTW-1.
