# Decisions

Generated from each decision's frontmatter by `context-engine decision index`; never edit it by hand (G-D6).

## BUILT

### api

- [DEC-41](DEC-41-type-checking-py-stays-in-the-repo-unchanged.md): `type_checking.py` stays in the repo, unchanged, outside v1's API *(owner, 2026-10-08)*

### architecture

- [DEC-15](DEC-15-logfire-is-not-a-dependency-v1-builds-on-the.md): Logfire is not a dependency: v1 builds on the plain OTel SDK (Q15) *(owner, 2026-10-17)*

### config

- [DEC-7](DEC-7-no-logfire-environment-variables-q7-obsolete.md): No `LOGFIRE_*` environment variables (Q7, obsolete with logfire) *(owner, 2026-10-17)*

### process

- [DEC-14](DEC-14-proposals-3-8-10-and-11-signed-off-as-amended-9.md): Proposals 3-8, 10 and 11 signed off as amended; 9 withdrawn (Q14) *(owner, 2026-10-08)*
- [DEC-40](DEC-40-hosting-stays-on-github-and-pypi-ci-is-github.md): Hosting stays on GitHub and PyPI; CI is GitHub Actions *(owner, 2026-10-08)*
- [DEC-70](DEC-70-adopt-context-engine-fully-as-is-engine.md): Adopt context-engine fully, as is: engine defaults, automatic commits, a full migration of the v1 plan, an OTW board with a v1 epic *(owner, 2026-10-18)*

### telemetry

- [DEC-6](DEC-6-baggage-is-never-copied-onto-spans-q6-obsolete.md): Baggage is never copied onto spans (Q6, obsolete with logfire) *(owner, 2026-10-17)*

### testing

- [DEC-39](DEC-39-settle-the-shape-of-v1-before-writing-its-tests.md): Settle the shape of v1 before writing its tests *(owner, 2026-10-08)*
- [DEC-63](DEC-63-v0-is-pinned-by-a-characterization-suite-plain.md): v0 is pinned by a characterization suite: plain tests, strict xfails for bugs, `v0_specific` for intended changes *(owner + agent, 2026-10-07)*

### v0

- [DEC-62](DEC-62-v0-pins-sqlalchemy-asyncio-2-1-until-the.md): v0 pins `sqlalchemy[asyncio]<2.1` until the contrib instrumentor supports 2.1 *(owner + agent, 2026-10-08)*

### untagged

- [DEC-73](DEC-73-charter-gains-a-purpose-and-goals-g-11-g-12.md): Charter gains a purpose and goals G-11, G-12 from the v0 talk; only a cleaned deck summary is committed *(owner, 2026-10-18)*
- [DEC-76](DEC-76-g-13-added-for-request-context-g-7-stays-g-13.md): G-13 added for request context; G-7 stays; G-13 leads the Helpful tier *(owner + agent, 2026-10-18)*

## PROVISIONAL

### api

- [DEC-3](DEC-3-exception-status-error-on-the-innermost-span.md): Exception status: ERROR on the innermost span; cancellation and interrupts stay unset (Q3) *(owner, 2026-10-18)*
- [DEC-8](DEC-8-pythonwarnings-error-may-crash-startup-accepted.md): `PYTHONWARNINGS=error` may crash startup: accepted and documented (Q8) *(owner, 2026-10-18)*
- [DEC-11](DEC-11-otel-instrument-with-no-arguments-logging.md): `otel.instrument()` with no arguments: logging, requests, system metrics (Q11) *(owner, 2026-10-18)*
- [DEC-19](DEC-19-one-otel-object-decorates-and-opens-spans.md): One `otel` object decorates and opens spans; integrations use `otel.instrument(x)` *(owner, 2026-10-08)*
- [DEC-20](DEC-20-configured-otel-objects-are-immutable-and.md): Configured `otel(...)` objects are immutable and stateless; span state lives in a `ContextVar` *(owner, 2026-10-08)*
- [DEC-21](DEC-21-no-blocked-behaviour-code-info-is-looked-up-at.md): No "blocked" behaviour: code info is looked up at run time from the target *(owner, 2026-10-08)*
- [DEC-22](DEC-22-generators-and-context-managers-one-span-each.md): Generators and context managers: one span each, as prototyped *(owner, 2026-10-08)*
- [DEC-25](DEC-25-our-spans-come-from-the-otel-tracer-the-exposed.md): Our spans come from the OTel tracer; the exposed span type is OTel's `trace.Span` (proposal 2) *(owner, 2026-10-08)*
- [DEC-42](DEC-42-global-dataclass-instrumentation-is-dropped.md): Global dataclass instrumentation is dropped *(owner, 2026-10-08)*
- [DEC-45](DEC-45-escape-hatches-otel-span-otel-trace-id-otel.md): Escape hatches: `otel.span`, `otel.trace_id`, `otel.span_id` (proposal 3) *(owner + agent, 2026-10-08)*
- [DEC-46](DEC-46-import-path-from-opentelemetry-wrapper-import.md): Import path: `from opentelemetry_wrapper import otel` (proposal 4) *(owner + agent, 2026-10-08)*
- [DEC-47](DEC-47-unnamed-with-otel-blocks-are-named-after-the.md): Unnamed `with otel:` blocks are named after the enclosing function (proposal 5) *(owner + agent, 2026-10-08)*
- [DEC-48](DEC-48-property-on-top-otel-underneath-proposal-6.md): `@property` on top, `@otel` underneath (proposal 6) *(owner + agent, 2026-10-08)*
- [DEC-49](DEC-49-one-otelwrapperwarning-through-warnings-warn-on.md): One `OtelWrapperWarning` through `warnings.warn`, on startup paths only (proposal 7) *(owner + agent, 2026-10-08)*
- [DEC-50](DEC-50-otel-and-with-otel-mean-the-same-as-otel-and.md): `@otel()` and `with otel():` mean the same as `@otel` and `with otel:` (proposal 8) *(owner + agent, 2026-10-08)*
- [DEC-53](DEC-53-classes-span-methods-and-constructors-selected.md): Classes span methods and constructors, selected dunders, `@otel.ignore`; `attributes` as a dict (proposal 11) *(owner + agent, 2026-10-08)*
- [DEC-89](DEC-89-a-decorated-class-spans-only-the-members.md): A decorated class spans only the members defined in its own body, not inherited ones *(owner, 2026-10-19)*
- [DEC-90](DEC-90-otel-wrapper-header-attributes-exclude-adds-to.md): OTEL_WRAPPER_HEADER_ATTRIBUTES_EXCLUDE adds to the default denylist; only configure() in code replaces it *(owner, 2026-10-19)*
- [DEC-91](DEC-91-sqlalchemy-sqlcommenter-is-off-by-default-in-v1.md): SQLAlchemy sqlcommenter is off by default in v1 (env opt-in); aiosqlite joins the test dependencies *(owner, 2026-10-19)*
- [DEC-92](DEC-92-otel-metrics-exporter-prometheus-serves-on-9464.md): OTEL_METRICS_EXPORTER=prometheus serves on 9464; a scrape path is served with and without its trailing slash, no redirect *(owner, 2026-10-19)*
- [DEC-93](DEC-93-fastapi-s-asgi-send-receive-spans-are-off-by.md): FastAPI's ASGI send/receive spans are off by default; an env var turns them on for debugging *(owner, 2026-10-19)*

### config

- [DEC-5](DEC-5-otel-sdk-disabled-true-also-means-otel-wrapper.md): `OTEL_SDK_DISABLED=true` also means `OTEL_WRAPPER_DISABLED` (Q5) *(owner, 2026-10-18)*
- [DEC-9](DEC-9-only-the-log-level-may-change-after.md): Only the log level may change after configuration is built (Q9) *(owner, 2026-10-18)*
- [DEC-24](DEC-24-otel-wrapper-disabled-means-no-telemetry-at-all.md): `OTEL_WRAPPER_DISABLED` means no telemetry at all *(owner, 2026-10-08)*
- [DEC-27](DEC-27-configuration-implicit-and-explicit-together.md): Configuration: implicit and explicit together, final once built (proposal 1) *(owner, 2026-10-08)*
- [DEC-28](DEC-28-exporters-are-chosen-from-the-standard-otel-env.md): Exporters are chosen from the standard `OTEL_*` env vars *(owner, 2026-10-08)*
- [DEC-52](DEC-52-migration-from-v0-old-env-var-names-for-one.md): Migration from v0: old env var names for one release, a port-4317 warning, Upgrading notes (proposal 10) *(owner + agent, 2026-10-08)*
- [DEC-59](DEC-59-environment-variables-standard-names-where-they.md): Environment variables: standard names where they exist, `OTEL_WRAPPER_*` for ours *(owner, 2026-10-08)*

### headers

- [DEC-2](DEC-2-x-userinfo-record-every-claim-except-a-denylist.md): `x-userinfo`: record every claim except a denylist (Q2) *(owner, 2026-10-07)*

### logging

- [DEC-13](DEC-13-log-records-keep-the-bare-record-funcname-q13.md): Log records keep the bare `record.funcName` (Q13) *(owner, 2026-10-18)*
- [DEC-32](DEC-32-logs-are-real-otel-log-records-never-spans.md): Logs are real OTel log records, never spans *(owner, 2026-10-08)*
- [DEC-34](DEC-34-console-one-line-json-logs-on-stderr-no-pretty.md): Console: one-line JSON logs on stderr; no pretty console in 1.0 *(owner, 2026-10-17)*
- [DEC-43](DEC-43-logging-options-come-from-env-vars-and-otel.md): Logging options come from env vars and `otel.configure(...)` only *(owner, 2026-10-08)*

### packaging

- [DEC-35](DEC-35-pydantic-2-only-optional-never-imported-by-us.md): Pydantic 2 only, optional, never imported by us *(owner, 2026-10-08)*
- [DEC-36](DEC-36-otlp-http-only-grpc-export-dropped.md): OTLP/HTTP only: gRPC export dropped *(owner, 2026-10-08)*
- [DEC-44](DEC-44-v1-requires-python-3-12-or-later.md): v1 requires Python 3.12 or later *(owner, 2026-10-08)*
- [DEC-57](DEC-57-strict-otel-pins-capped-at-the-next-minor.md): Strict OTel pins, capped at the next minor *(owner, 2026-10-18)*

### privacy

- [DEC-94](DEC-94-with-otel-wrapper-debug-true-a-scrubbing.md): With OTEL_WRAPPER_DEBUG=true a scrubbing failure's report shows the real exception message *(owner, 2026-10-20)*

### process

- [DEC-37](DEC-37-rollout-v1-ships-beside-v0-becomes-the-default.md): Rollout: v1 ships beside v0, becomes the default, then v0 is deleted after one release of aliases *(owner, 2026-10-08)*
- [DEC-54](DEC-54-upstream-otel-bumps-renovate-prs-that-auto.md): Upstream OTel bumps: Renovate PRs that auto-merge only when CI passes *(owner, 2026-10-18)*
- [DEC-55](DEC-55-dependency-only-merges-are-released.md): Dependency-only merges are released automatically as a patch release to PyPI *(owner, 2026-10-18)*
- [DEC-78](DEC-78-building-starts-otw-2-is-split-renovate-and.md): Building starts; OTW-2 is split: Renovate and auto-release move to a new item after the strict pins *(owner, 2026-10-18)*
- [DEC-79](DEC-79-push-close-otw-2-on-green-ci-then-build-the.md): Push, close OTW-2 on green CI, then build the rest with one ultracode agent per task, minimizing tokens *(owner, 2026-10-18)*
- [DEC-86](DEC-86-stop-after-this-push-s-ci-is-green-the-owner.md): Stop after this push's CI is green; the owner clears context before more work. A 7-day GitHub token for CI logs lives in .scratch *(owner, 2026-10-19)*
- [DEC-87](DEC-87-keep-going-on-the-v1-chain-through-ultracode.md): Keep going on the v1 chain through ultracode workflows, raising only what needs the owner *(owner, 2026-10-19)*
- [DEC-88](DEC-88-push-main-now-and-after-each-merge-this-session.md): Push main now and after each merge this session, gated and CI-watched, no release *(owner, 2026-10-19)*

### release

- [DEC-84](DEC-84-main-is-the-v1-line-a-v0-only-patch-is-released.md): main is the v1 line; a v0-only patch is released from a branch cut at the last v0 tag *(owner, 2026-10-19)*
- [DEC-85](DEC-85-push-this-session-s-work-once-the-root-v1-agent.md): Push this session's work once the root-v1 agent lands; no release *(owner, 2026-10-19)*
- [DEC-96](DEC-96-the-first-v1-release-is-1-0-0-a-hard-cutover-v0.md): The first v1 release is 1.0.0, a hard cutover: v0 deleted, its root names warn-once aliases onto v1 *(owner, 2026-10-20)*
- [DEC-97](DEC-97-otw-21-waits-until-after-v1-and-ships-push-only.md): OTW-21 waits until after v1 and ships push-only first; publishing is turned on after a couple of correct pushes *(owner, 2026-10-20)*
- [DEC-98](DEC-98-releases-move-to-pypi-trusted-publishing-the.md): Releases move to PyPI trusted publishing; the owner stops using flit publish; push now *(owner, 2026-10-20)*

### resources

- [DEC-4](DEC-4-process-executable-name-is-the-base-name-of-sys.md): `process.executable.name` is the base name of `sys.executable` (Q4) *(owner, 2026-10-18)*
- [DEC-12](DEC-12-no-kubernetes-api-calls-labels-and-annotations.md): No Kubernetes API calls: labels and annotations from the Downward API (Q12) *(owner, 2026-10-18)*
- [DEC-29](DEC-29-service-name-follows-semconv-v0-s-readable-name.md): `service.name` follows semconv; v0's readable name moves to `opentelemetry_wrapper.instance.label` *(owner, 2026-10-08)*
- [DEC-30](DEC-30-record-the-full-command-line-as-process-command.md): Record the full command line as `process.command_args`, plus the Python environment *(owner, 2026-10-08)*
- [DEC-33](DEC-33-resource-precedence-our-detectors-otel-service.md): Resource precedence: our detectors < `OTEL_SERVICE_NAME` / `OTEL_RESOURCE_ATTRIBUTES` < explicit arguments *(owner, 2026-10-17)*

### scrubbing

- [DEC-16](DEC-16-scrubbing-engine-stdlib-re-by-default-hyperscan.md): Scrubbing engine: stdlib `re` by default, `[hyperscan]` as the optional fast engine (Q16) *(owner, 2026-10-18)*
- [DEC-58](DEC-58-v1-scrubs-exported-telemetry-with-its-own-rules.md): v1 scrubs exported telemetry with its own rules *(owner, 2026-10-18)*

### sqlalchemy

- [DEC-1](DEC-1-sqlalchemy-otel-instrument-sqlalchemy-is-global.md): SQLAlchemy: `otel.instrument(sqlalchemy)` is global, `otel.instrument(engine)` is per engine (Q1) *(owner, 2026-10-07)*

### telemetry

- [DEC-23](DEC-23-no-per-span-sampling-sampling-is-decided-at-the.md): No per-span sampling: sampling is decided at the root span through the standard env vars *(owner, 2026-10-08)*
- [DEC-26](DEC-26-no-arguments-or-return-values-on-spans.md): No arguments or return values on spans *(owner, 2026-10-08)*
- [DEC-31](DEC-31-stable-semconv-code-keys-everywhere.md): Stable semconv `code.*` keys everywhere *(owner, 2026-10-08)*

### testing

- [DEC-10](DEC-10-pytest-plugin-opt-in-requesting-otel-spans-otel.md): Pytest plugin opt-in: requesting `otel_spans` / `otel_logs`, or an ini option (Q10) *(owner, 2026-10-18)*
- [DEC-38](DEC-38-proven-safe-is-one-command-tests-v0-under-otw.md): "Proven safe" is one command: `tests/v0` under `OTW_IMPL=v0|v1` *(owner, 2026-10-08)*
- [DEC-56](DEC-56-ci-github-actions-on-push-and-pull-requests.md): CI: GitHub Actions on push and pull requests, Python 3.12-3.14, with and without extras *(owner, 2026-10-18)*

### untagged

- [DEC-71](DEC-71-no-v0-patch-release-v0-is-not-touched.md): No v0 patch release: v0 is not touched *(owner, 2026-10-18)*
- [DEC-72](DEC-72-charter-review-the-principles-are-a-ranking.md): Charter review: the principles are a ranking; never crash first, no secrets last *(owner, 2026-10-18)*
- [DEC-74](DEC-74-a-value-that-fails-to-scrub-is-dropped-and.md): A value that fails to scrub is dropped and replaced by its own 'scrubbing failed' placeholder *(owner, 2026-10-18)*
- [DEC-75](DEC-75-the-wrapper-reports-its-own-swallowed-runtime.md): The wrapper reports its own swallowed runtime failures: one stderr JSON line per site, tracebacks opt-in *(owner, 2026-10-18)*
- [DEC-77](DEC-77-charter-parsimony-rank-placements-confirmed.md): Charter parsimony: rank placements confirmed, fail small in G-3, slimmer G-1, charter trimmed *(owner, 2026-10-18)*
- [DEC-81](DEC-81-runtime-warnings-go-to-stderr-once-never.md): Runtime warnings go to stderr once, never through warnings.warn *(owner, 2026-10-19)*
- [DEC-82](DEC-82-a-record-whose-scrubbing-fails-is-exported-bare.md): A record whose scrubbing fails is exported bare; dropped only if even that fails *(owner, 2026-10-19)*
- [DEC-83](DEC-83-configure-uses-the-auto-scrubbing-engine-once.md): Configure uses the auto scrubbing engine once the [hyperscan] extra exists *(owner, 2026-10-19)*
- [DEC-95](DEC-95-only-is-class-is-emitted-the-other-dec-31.md): Only is_class is emitted; the other DEC-31 extras stay commented out with the reason *(owner, 2026-10-20)*

## DEFERRED

### api

- [DEC-61](DEC-61-un-instrumentation-beyond-the-pytest-plugin-s.md): Un-instrumentation, beyond the pytest plugin's per-test reset *(owner, 2026-10-08)*

## SUPERSEDED

### architecture

- [DEC-17](DEC-17-v1-rebuilds-on-the-logfire-sdk.md): v1 rebuilds on the Logfire SDK *(owner, 2026-10-04)*; superseded by DEC-15

### scrubbing

- [DEC-18](DEC-18-scrubbing-s-optional-fast-engine-is-an-re2.md): Scrubbing's optional fast engine is an `[re2]` hybrid *(owner, 2026-10-18)*; superseded by DEC-16
- [DEC-66](DEC-66-no-sanitizer-just-don-t-log-secrets.md): No sanitizer: just don't log secrets *(owner, 2023-06-05)*; superseded by DEC-58

### untagged

- [DEC-80](DEC-80-root-is-v1-v0-s-names-load-lazily-v0-s.md): Root is v1; v0's names load lazily; v0's dependencies stay core until 1.0.0 *(owner, 2026-10-19)*; superseded by DEC-96

## REJECTED

### api

- [DEC-60](DEC-60-auto-tracing-a-user-s-package-otel-instrument.md): Auto-tracing a user's package (`otel.instrument(my_package)`) *(owner, 2026-10-08)*
- [DEC-64](DEC-64-magic-variable-names-through-varname.md): Magic variable names through `varname` *(owner + agent, 2026-10-07)*
- [DEC-65](DEC-65-instrument-pydantic.md): Instrument pydantic *(owner, 2022-06-30)*
- [DEC-67](DEC-67-locate-source-with-tracemalloc-or-sys-settrace.md): Locate source with `tracemalloc` or `sys.settrace` *(owner, 2022-09-27)*
- [DEC-68](DEC-68-mark-functions-as-do-not-instrument-or-give.md): Mark functions as do-not-instrument, or give them a sampling ratio *(owner, 2022-09-27)*

### telemetry

- [DEC-51](DEC-51-logfire-s-distributed-tracing-true-option.md): Logfire's `distributed_tracing=True` option (proposal 9) *(owner, 2026-10-17)*
- [DEC-69](DEC-69-red-metrics-computed-in-the-library.md): RED metrics computed in the library *(owner, 2024-04-09)*
