# Decision id map: docs/evidence/decision-log-import-2026-10-18.md into docs/decisions

FROZEN. Printed by `context-engine decision import --dry-run` on 2026-10-18, session 2026-10-18a; the import gives each record below its id, and the old id, where there was one, stays in its `aliases` (FRAMEWORK §11.4).

| id in the log | record | status | title |
|---|---|---|---|
| Q-1 | DEC-1 | BUILT | SQLAlchemy: `otel.instrument(sqlalchemy)` is global, `otel.instrument(engine)` is per engine (Q1) |
| Q-2 | DEC-2 | BUILT | `x-userinfo`: record every claim except a denylist (Q2) |
| Q-3 | DEC-3 | BUILT | Exception status: ERROR on the innermost span; cancellation and interrupts stay unset (Q3) |
| Q-4 | DEC-4 | BUILT | `process.executable.name` is the base name of `sys.executable` (Q4) |
| Q-5 | DEC-5 | BUILT | `OTEL_SDK_DISABLED=true` also means `OTEL_WRAPPER_DISABLED` (Q5) |
| Q-6 | DEC-6 | BUILT | Baggage is never copied onto spans (Q6, obsolete with logfire) |
| Q-7 | DEC-7 | BUILT | No `LOGFIRE_*` environment variables (Q7, obsolete with logfire) |
| Q-8 | DEC-8 | BUILT | `PYTHONWARNINGS=error` may crash startup: accepted and documented (Q8) |
| Q-9 | DEC-9 | BUILT | Only the log level may change after configuration is built (Q9) |
| Q-10 | DEC-10 | BUILT | Pytest plugin opt-in: requesting `otel_spans` / `otel_logs`, or an ini option (Q10) |
| Q-11 | DEC-11 | BUILT | `otel.instrument()` with no arguments: logging, requests, system metrics (Q11) |
| Q-12 | DEC-12 | BUILT | No Kubernetes API calls: labels and annotations from the Downward API (Q12) |
| Q-13 | DEC-13 | BUILT | Log records keep the bare `record.funcName` (Q13) |
| Q-14 | DEC-14 | BUILT | Proposals 3-8, 10 and 11 signed off as amended; 9 withdrawn (Q14) |
| Q-15 | DEC-15 | BUILT | Logfire is not a dependency: v1 builds on the plain OTel SDK (Q15) |
| Q-16 | DEC-16 | BUILT | Scrubbing engine: stdlib `re` by default, `[hyperscan]` as the optional fast engine (Q16) |
| DEC-17 | DEC-17 | SUPERSEDED | v1 rebuilds on the Logfire SDK |
| DEC-18 | DEC-18 | SUPERSEDED | Scrubbing's optional fast engine is an `[re2]` hybrid |
| DEC-19 | DEC-19 | BUILT | One `otel` object decorates and opens spans; integrations use `otel.instrument(x)` |
| DEC-20 | DEC-20 | BUILT | Configured `otel(...)` objects are immutable and stateless; span state lives in a `ContextVar` |
| DEC-21 | DEC-21 | BUILT | No "blocked" behaviour: code info is looked up at run time from the target |
| DEC-22 | DEC-22 | BUILT | Generators and context managers: one span each, as prototyped |
| DEC-23 | DEC-23 | BUILT | No per-span sampling: sampling is decided at the root span through the standard env vars |
| DEC-24 | DEC-24 | BUILT | `OTEL_WRAPPER_DISABLED` means no telemetry at all |
| DEC-25 | DEC-25 | BUILT | Our spans come from the OTel tracer; the exposed span type is OTel's `trace.Span` (proposal 2) |
| DEC-26 | DEC-26 | BUILT | No arguments or return values on spans |
| DEC-27 | DEC-27 | BUILT | Configuration: implicit and explicit together, final once built (proposal 1) |
| DEC-28 | DEC-28 | BUILT | Exporters are chosen from the standard `OTEL_*` env vars |
| DEC-29 | DEC-29 | BUILT | `service.name` follows semconv; v0's readable name moves to `opentelemetry_wrapper.instance.label` |
| DEC-30 | DEC-30 | BUILT | Record the full command line as `process.command_args`, plus the Python environment |
| DEC-31 | DEC-31 | BUILT | Stable semconv `code.*` keys everywhere |
| DEC-32 | DEC-32 | BUILT | Logs are real OTel log records, never spans |
| DEC-33 | DEC-33 | BUILT | Resource precedence: our detectors < `OTEL_SERVICE_NAME` / `OTEL_RESOURCE_ATTRIBUTES` < explicit arguments |
| DEC-34 | DEC-34 | BUILT | Console: one-line JSON logs on stderr; no pretty console in 1.0 |
| DEC-35 | DEC-35 | BUILT | Pydantic 2 only, optional, never imported by us |
| DEC-36 | DEC-36 | BUILT | OTLP/HTTP only: gRPC export dropped |
| DEC-37 | DEC-37 | BUILT | Rollout: v1 ships beside v0, becomes the default, then v0 is deleted after one release of aliases |
| DEC-38 | DEC-38 | BUILT | "Proven safe" is one command: `tests/v0` under `OTW_IMPL=v0\|v1` |
| DEC-39 | DEC-39 | BUILT | Settle the shape of v1 before writing its tests |
| DEC-40 | DEC-40 | BUILT | Hosting stays on GitHub and PyPI; CI is GitHub Actions |
| DEC-41 | DEC-41 | BUILT | `type_checking.py` stays in the repo, unchanged, outside v1's API |
| DEC-42 | DEC-42 | BUILT | Global dataclass instrumentation is dropped |
| DEC-43 | DEC-43 | BUILT | Logging options come from env vars and `otel.configure(...)` only |
| DEC-44 | DEC-44 | BUILT | v1 requires Python 3.12 or later |
| DEC-45 | DEC-45 | BUILT | Escape hatches: `otel.span`, `otel.trace_id`, `otel.span_id` (proposal 3) |
| DEC-46 | DEC-46 | BUILT | Import path: `from opentelemetry_wrapper import otel` (proposal 4) |
| DEC-47 | DEC-47 | BUILT | Unnamed `with otel:` blocks are named after the enclosing function (proposal 5) |
| DEC-48 | DEC-48 | BUILT | `@property` on top, `@otel` underneath (proposal 6) |
| DEC-49 | DEC-49 | BUILT | One `OtelWrapperWarning` through `warnings.warn`, on startup paths only (proposal 7) |
| DEC-50 | DEC-50 | BUILT | `@otel()` and `with otel():` mean the same as `@otel` and `with otel:` (proposal 8) |
| DEC-51 | DEC-51 | BUILT | Logfire's `distributed_tracing=True` option (proposal 9) |
| DEC-52 | DEC-52 | BUILT | Migration from v0: old env var names for one release, a port-4317 warning, Upgrading notes (proposal 10) |
| DEC-53 | DEC-53 | BUILT | Classes span methods and constructors, selected dunders, `@otel.ignore`; `attributes` as a dict (proposal 11) |
| DEC-54 | DEC-54 | BUILT | Upstream OTel bumps: Renovate PRs that auto-merge only when CI passes |
| DEC-55 | DEC-55 | BUILT | Dependency-only merges are released automatically as a patch release to PyPI |
| DEC-56 | DEC-56 | BUILT | CI: GitHub Actions on push and pull requests, Python 3.12-3.14, with and without extras |
| DEC-57 | DEC-57 | BUILT | Strict OTel pins, capped at the next minor |
| DEC-58 | DEC-58 | BUILT | v1 scrubs exported telemetry with its own rules |
| DEC-59 | DEC-59 | BUILT | Environment variables: standard names where they exist, `OTEL_WRAPPER_*` for ours |
| DEC-60 | DEC-60 | BUILT | Auto-tracing a user's package (`otel.instrument(my_package)`) |
| DEC-61 | DEC-61 | BUILT | Un-instrumentation, beyond the pytest plugin's per-test reset |
| DEC-62 | DEC-62 | BUILT | v0 pins `sqlalchemy[asyncio]<2.1` until the contrib instrumentor supports 2.1 |
| DEC-63 | DEC-63 | BUILT | v0 is pinned by a characterization suite: plain tests, strict xfails for bugs, `v0_specific` for intended changes |
| DEC-64 | DEC-64 | BUILT | Magic variable names through `varname` |
| DEC-65 | DEC-65 | BUILT | Instrument pydantic |
| DEC-66 | DEC-66 | SUPERSEDED | No sanitizer: just don't log secrets |
| DEC-67 | DEC-67 | BUILT | Locate source with `tracemalloc` or `sys.settrace` |
| DEC-68 | DEC-68 | BUILT | Mark functions as do-not-instrument, or give them a sampling ratio |
| DEC-69 | DEC-69 | BUILT | RED metrics computed in the library |

