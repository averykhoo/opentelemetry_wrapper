# opentelemetry_wrapper

OpenTelemetry tracing, logs and metrics for Python apps with one object, `otel`. It's built on the plain OpenTelemetry
SDK and the standard OpenTelemetry instrumentations ([DEC-15]), and follows the OpenTelemetry semantic conventions.

```python
from opentelemetry_wrapper import otel
```

`otel` is a decorator and a context manager, and `otel.instrument(...)` instruments libraries and apps ([DEC-19]).
Whatever you use it on:

- **it's idempotent**: decorating or instrumenting the same thing twice, from anywhere, behaves as if you did it once.
- **it never crashes your app**: anything it can't handle is returned unchanged, with a single warning.
- **it's safe with threads and asyncio**: nested and concurrent spans each get the right parent. A configured
  `otel('name')` object holds no state, so one can be shared freely ([DEC-20]).

Python 3.12+ ([DEC-44]). Upgrading from v0? See [Upgrading from v0](#upgrading-from-v0); v0's README is archived in
[docs/archive/README_v0.md][v0-readme].

## Installing

```shell
pip install opentelemetry_wrapper
pip install "opentelemetry_wrapper[fastapi,sqlalchemy,requests,system-metrics,hyperscan]"
```

Each integration is optional, behind an extra that brings its instrumentation and the library: `[fastapi]`,
`[sqlalchemy]`, `[requests]`, `[system-metrics]` (CPU, memory and so on, through `psutil`) and `[hyperscan]` (a faster
engine for [secret scrubbing](#secret-scrubbing)). Until 1.0.0, v0's dependencies (FastAPI, SQLAlchemy, requests,
pydantic, the gRPC exporter, ...) are still installed by the plain install, so that v0's names keep working ([DEC-80]).
The OpenTelemetry packages are pinned to one minor release at a time, since OpenTelemetry has shipped breaking changes
in minor releases ([DEC-57]).

## Quick start

Nothing needs to be set up: with no environment variables, this runs, writes one line of JSON per log to stderr and
exports nothing. Set `OTEL_EXPORTER_OTLP_ENDPOINT` (e.g. `http://localhost:4318`) and the same code exports its
traces, logs and metrics over OTLP.

```python
import logging

from opentelemetry import metrics

from opentelemetry_wrapper import otel

otel.instrument()  # logging, requests and system metrics, whichever are installed
orders = metrics.get_meter('shop').create_counter('orders')


@otel
def checkout(cart):
    with otel('charge card', attributes={'items': len(cart)}):
        logging.info('charging', extra={'items': len(cart)})
    orders.add(1)
    return 'ok'


checkout(['apple', 'pear'])
```

Metrics of your own use the standard OpenTelemetry API (`opentelemetry.metrics`), as above; the wrapper sets up where
they go.

## Making spans

### Functions

One span per call, named after the function (`module.qualname`). The attributes record where the code lives, with the
stable semantic-convention keys (`code.function.name`, `code.file.path`, `code.line.number`, [DEC-31]); arguments and
return values are never recorded ([DEC-26]): add what you need with `attributes={...}` or on the span. Sync and async
functions both work.

```python
from opentelemetry_wrapper import otel


@otel
def square(x):
    return x * x


@otel
async def fetch(url):
    ...


square(3)
```

### Functions, with options

```python
from opentelemetry_wrapper import otel


@otel(name='price lookup', attributes={'currency': 'SGD'})
def lookup(sku):
    ...


lookup('A-1')
```

`attributes` is a dict, so its keys can never clash with options. `@otel()` with no options is the same as `@otel`
([DEC-50]). `otel.instrument(f)` on a function or class is the same as `@otel`.

### Methods

Works on plain methods, `@staticmethod`, `@classmethod` and `@property`. Put `@property` on top and `@otel`
underneath: both orders work at runtime, but mypy rejects any decorator above `@property` ([DEC-48]).

```python
from opentelemetry_wrapper import otel


class Cart:
    @otel
    def checkout(self):
        ...

    @property
    @otel
    def total(self):
        ...


Cart().checkout()
```

### Classes and dataclasses

Every method call gets a span, as do the constructors (`__new__`, `__init__`, `__post_init__`), `__call__`, and
`__enter__` / `__exit__` (one span for the whole `with` block). Other dunder methods (`__repr__`, `__eq__`,
`__hash__`, ...) don't. Properties are left out unless you ask for them with `@otel(properties=True)`, since a
property read in a loop is the noisiest thing there is. To leave out a hot method, mark it with `@otel.ignore`
([DEC-53]).

```python
from dataclasses import dataclass

from opentelemetry_wrapper import otel


@otel
class Cart:
    def add(self, item):
        ...

    @otel.ignore
    def __len__(self):
        ...


@otel
@dataclass
class Item:
    sku: str
    price: float


Cart().add(Item('A-1', 2.5))
```

Only the members defined in the decorated class's own body get spans, not the ones it inherits: to span a base class's
methods, decorate the base ([DEC-89]). Nothing is copied into the subclass, so method lookup and signatures are exactly
as they were. Put `@otel` above `@dataclass`, so it sees the generated `__init__`.

Decorating a class changes that class for the whole process, including when you do it to a library's class
(`otel(SortedList)`). Built-in and extension types (`dict`, most C classes) can't be changed: they're returned as they
are, with a warning.

### Generators

One span from the first item until the generator is exhausted, closed or garbage-collected ([DEC-22]). The span's
parent is whatever span is current where the first item is asked for (the first `next()`), which is usually the loop
that consumes it. Only the generator's own work is inside the span; whatever the loop body does between items stays
under the caller. The span records how many items were yielded (`opentelemetry_wrapper.yields`) and how long the
generator was actually running (`opentelemetry_wrapper.active_seconds`), since its duration also includes time spent
waiting for the consumer. A generator abandoned before the end gets `opentelemetry_wrapper.closed_early = true`
(on PyPy, only once it's garbage-collected). Async generators work the same way. The decorated function is still a
generator function, so FastAPI `yield` dependencies and pytest `yield` fixtures keep working.

```python
from opentelemetry_wrapper import otel


@otel
def read_rows(lines):
    for line in lines:
        yield line.split(',')


for row in read_rows(['apple,1', 'pear,2']):  # this loop body is not part of the `read_rows` span
    print(row)
```

### Context managers

Put `@otel` **above** `@contextmanager` / `@asynccontextmanager`. The span covers entry, the whole `with` block and
exit, and anything inside the block becomes a child of it. (With `@otel` underneath, it sees only a generator, so
the block is not a child of the span.)

```python
from contextlib import contextmanager

from opentelemetry_wrapper import otel


@otel
@contextmanager
def transaction():
    print('begin')
    yield
    print('commit')


with transaction():  # spans and logs in here are children of `transaction`
    print('work')
```

Class-based context managers get the same single entry-to-exit span when the class is decorated.

### Blocks of code

`with otel:` without a name is named after the function it's in, e.g. `app.config.load_config` (or
`app.config.<module>` at module level, [DEC-47]). The line number isn't part of the name, so editing the file doesn't
change it; it's in `code.line.number`. Two unnamed blocks in one function would share a name, so you get a warning
(on stderr, the first time it happens); prefer `with otel('name'):`. `with otel():` is the same as `with otel:`, and
`async with` works too.

```python
from opentelemetry_wrapper import otel

with otel:
    ...

with otel('load settings'):
    ...

with otel('load settings', attributes={'source': 'env'}) as span:
    span.set_attribute('count', 3)
```

`span` is a standard OpenTelemetry `Span` ([DEC-25]).

### The current span

`otel.span` is the current span (a span that records nothing when there isn't one, never `None`). `otel.trace_id`
and `otel.span_id` are its ids as hex strings (all zeros when there's no span or telemetry is disabled), e.g. to put
in an error response so a user's report can be matched to its trace ([DEC-45]).

```python
from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import JSONResponse
from opentelemetry.trace import Status
from opentelemetry.trace import StatusCode

from opentelemetry_wrapper import otel

app = otel.instrument(FastAPI())


@otel
def place_order(order_id, key):
    otel.span.set_attribute('order_id', order_id)
    otel.span.add_event('cache miss', {'key': key})
    try:
        raise TimeoutError('payment provider is slow')
    except TimeoutError as exc:
        otel.span.record_exception(exc)                                  # record without raising
    otel.span.set_status(Status(StatusCode.ERROR, 'quota exceeded'))  # mark failed without raising


@app.exception_handler(Exception)
async def internal_error(request: Request, exc: Exception):
    return JSONResponse({'error': 'internal', 'trace_id': otel.trace_id}, status_code=500)


place_order(7, 'sku:A-1')
```

Logs are linked to the current span automatically, and `extra={...}` becomes attributes on the log record:
`logging.info('paid', extra={'order_id': 7})`. Baggage is never copied onto spans ([DEC-6]).

### Exceptions

An exception raised through spans is re-raised untouched, and recorded once ([DEC-3]):

| Raised through the span | Status | Recorded |
|---|---|---|
| an `Exception`, on the innermost span it passes through | ERROR | an `exception` event with the stack trace, and `error.type` |
| the same exception, on each outer span | ERROR | `error.type` only |
| `StopIteration` / `StopAsyncIteration` | unset | nothing (the normal end of iteration) |
| `GeneratorExit` (a generator closed early) | unset | `opentelemetry_wrapper.closed_early = true` |
| `asyncio.CancelledError` | unset | `opentelemetry_wrapper.cancelled = true` |
| `KeyboardInterrupt` | unset | `opentelemetry_wrapper.interrupted = true` |
| `SystemExit` | ERROR if the exit code isn't zero | `process.exit.code` |

Cancellation is normal control flow (timeouts, client disconnects), so it isn't an error; where a timeout causes it,
`asyncio.timeout` raises `TimeoutError` at the scope that set the timeout, and that span is ERROR.

## Libraries and apps

Pass the thing itself to `otel.instrument`; you get it back, instrumented.

```python
import logging

import requests
import sqlalchemy
from fastapi import FastAPI

from opentelemetry_wrapper import otel

app = otel.instrument(FastAPI())  # request spans, decoded x-userinfo attributes, /metrics route
otel.instrument(sqlalchemy)       # every SQLAlchemy engine created from now on: query and connect spans
engine = sqlalchemy.create_engine('sqlite://')
otel.instrument(engine)           # just this Engine or AsyncEngine: query spans, but no connect spans
otel.instrument(requests)         # outgoing HTTP spans
otel.instrument(logging)          # OTel log records + one-line JSON on stderr, linked to the current span
otel.instrument()                 # logging, requests and system metrics, whichever are installed
```

`otel.instrument()` with no argument instruments logging, `requests` and system metrics (with the `[system-metrics]`
extra); never apps, engines or SQLAlchemy ([DEC-11]). A module it doesn't support (anything but `logging`, `requests`
and `sqlalchemy`) is a warning, and so is an app that has already started serving: instrument the app before it
handles its first request. There is no un-instrumenting ([DEC-61]).

**FastAPI:** one server span per request. FastAPI's ASGI `http send` / `http receive` spans under it are off by
default, as noise in most traces; set `OTEL_WRAPPER_FASTAPI_ASGI_SPANS=true` to get them back for debugging
([DEC-93]). The `/metrics` route is described under [Metrics](#metrics). Upstream's
`OTEL_PYTHON_FASTAPI_EXCLUDED_URLS` (or `OTEL_PYTHON_EXCLUDED_URLS`) still leaves out the URLs you list.

**SQLAlchemy** ([DEC-1]): `otel.instrument(sqlalchemy)` only reaches engines created *after* the call, so call it
before creating engines, or also pass the existing engines in. It patches `sqlalchemy.create_engine`, so a
`create_engine` imported by name (`from sqlalchemy import create_engine`) *before* the call still makes untraced
engines. `otel.instrument(engine)` traces that engine's queries only, whenever it was created: connection spans
(`connect`) come from the global instrumentation and aren't available per engine. Both together are fine: an engine is
never traced twice. An `AsyncEngine` is traced through its sync engine, and an engine made with
`engine.execution_options(...)` through the engine it was made from (they share its connections), so passing either
traces both. `otel.instrument()` leaves SQLAlchemy out, because query spans are noisy. Without the `[sqlalchemy]`
extra, either call warns once and changes nothing.

The [sqlcommenter](https://google.github.io/sqlcommenter/) is off by default, as upstream has it ([DEC-91]): a
comment changes the query text, which can defeat statement caches and `pg_stat_statements` grouping. To add its comment
(the traceparent, the driver and the framework) to every query, set `OTEL_WRAPPER_SQLALCHEMY_COMMENTER` before
instrumenting.

**x-userinfo** ([DEC-2]): the header (base64 or plain JSON, as an API gateway such as Kong passes on Keycloak's
userinfo) is decoded and every claim is recorded on the request span as `http.request.header.x-userinfo.<claim>`
(custom ones such as `employee_id` included; nested ones flattened, e.g. `realm_access.roles.[0]`), except those
matching the denylist (tokens and session ids by default). Personal data such as `email` and `name` is recorded unless
you add it: `OTEL_WRAPPER_HEADER_ATTRIBUTES_EXCLUDE=email,name` adds those patterns to the default ones, so tokens stay
out whatever the variable says ([DEC-90]). Only `otel.configure(header_attributes_exclude=[...])` in code replaces the
default list (`[]` clears it, recording every claim). Denied claims are dropped, not masked. The raw header value is
never recorded, also not by `OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_*` (it shows as `[REDACTED]` there, through
`OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SANITIZE_FIELDS`).

**Upstream latency:** `requests` calls record the response headers in `OTEL_WRAPPER_RESPONSE_HEADER_ATTRIBUTES` on
the client span, e.g. `http.response.header.x-envoy-upstream-service-time`.

## Logs

`otel.instrument(logging)` adds two handlers to the root logger, once however often it is called, and sets the root
logger's level (`OTEL_WRAPPER_LOG_LEVEL`, `info` by default). Logs are real OpenTelemetry log records, never spans
([DEC-32]):

- **OTel log records**, exported when an endpoint is set. Each carries the current span's trace and span ids (zeros
  outside spans), its `extra={...}` as attributes and the stable `code.*` keys. The function name is the bare
  `record.funcName` (`load_config`), as `logging` gives it ([DEC-13]). Sampling never drops a log: when the span is
  sampled out, its logs are still exported.
- **One line of JSON per log on stderr** ([DEC-34]), for log pipelines that don't speak OTLP: every field of the log
  record, plus `otelTraceID` / `otelSpanID` (the same ids, as `0x`-prefixed hex), `otelTraceSampled`,
  `otelServiceName`, and the local time as `asctime` (ISO 8601 with the offset), `tz_name` and
  `tz_utc_offset_seconds`. Anything can be logged: values that aren't JSON (a `Decimal`, a class, a pydantic model,
  an object) are converted, a log never raises, secrets are redacted and strings longer than 10,000 characters are
  cut. Pydantic is never imported by the wrapper; pydantic 2 models are written with `model_dump(mode='json')`, and
  pydantic 1 isn't supported (one warning; its models are written as their attributes, [DEC-35]).
  `OTEL_WRAPPER_LOG_FORMAT=off` turns the JSON lines off. There's no pretty console: for spans on the terminal, use
  `OTEL_TRACES_EXPORTER=console`.

`uvicorn.access` logs repeat the request spans, so they are written to stderr but not exported. Logging takes no
options per call ([DEC-43]): use the environment variables or `otel.configure(...)`.

## Configuration

Everything is configured with environment variables, using the standard OpenTelemetry names wherever one exists
([DEC-59], [DEC-28]). Nothing needs to be set up before using `otel`: `otel.instrument(...)` configures it, and
otherwise the first span does; decorating never configures anything, so import order doesn't matter ([DEC-27]).

To set options in code instead, call `otel.configure(...)` at startup, **before `otel.instrument(...)`** and before
the first span; explicit options beat environment variables, which beat the defaults.

```python
from opentelemetry_wrapper import otel

otel.configure(service_name='checkout', resource_attributes={'service.namespace': 'shop'})
print(otel.config['service_name'])  # the effective configuration, read-only, secrets redacted
```

Configuration is final once it's been set up (by `otel.configure`, `otel.instrument` or the first span): a later call
with different options is ignored, with a warning; only the log level can still change ([DEC-9]). `otel.config` is a
read-only view of the effective configuration, with the OTLP header values redacted: each option as set by
`otel.configure(...)`, or else by its variable, `OTEL_SERVICE_NAME`, `OTEL_RESOURCE_ATTRIBUTES`,
`OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_EXPORTER_OTLP_HEADERS` included, though OpenTelemetry reads those itself. It
doesn't show what's detected or defaulted on the resource (a `service_name` of `None` means the default service name
below; the spans' resource has the rest), nor the per-signal `OTEL_EXPORTER_OTLP_<SIGNAL>_ENDPOINT` and `_HEADERS`.

If something else configured OpenTelemetry first (the app set its own tracer provider), you get one warning and the
wrapper follows it where it can: it adds its span and log processors to an SDK tracer or logger provider (whose
resource is then not changed), and leaves any other provider alone, a meter provider included.

Exports are flushed at exit, also in `multiprocessing` children, with a bound (5 seconds), so an unreachable collector
never holds up a process's exit.

**Standard OpenTelemetry variables**

| Variable | Effect | Default |
|---|---|---|
| `OTEL_SERVICE_NAME` | `service.name` ([DEC-29]) | in Kubernetes, the workload name (Deployment, StatefulSet, ...); otherwise `unknown_service:<executable>`, the base name of `sys.executable` ([DEC-4]): e.g. `unknown_service:python3.12` on Linux, `unknown_service:python.exe` on Windows |
| `OTEL_RESOURCE_ATTRIBUTES` | extra resource attributes, e.g. `service.namespace=shop,service.version=1.2.0` | detected Kubernetes, process and host attributes ([below](#detected-automatically)) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` (and `OTEL_EXPORTER_OTLP_{TRACES,LOGS,METRICS}_ENDPOINT`) | where to push traces, logs and metrics, OTLP over HTTP, usually port 4318 ([DEC-36]). The per-signal variants override it for one signal; the exporters also read `OTEL_EXPORTER_OTLP_TIMEOUT` and the rest of the standard set themselves | nothing is exported |
| `OTEL_EXPORTER_OTLP_HEADERS` | headers sent to the endpoint: `key=value,key2=value2`, values URL-encoded | none |
| `OTEL_EXPORTER_OTLP_PROTOCOL` (and `OTEL_EXPORTER_OTLP_{TRACES,LOGS,METRICS}_PROTOCOL`) | only `http/protobuf` is exported: `grpc` is a warning at startup | `http/protobuf` |
| `OTEL_TRACES_SAMPLER` / `OTEL_TRACES_SAMPLER_ARG` | which traces to keep, decided at the root span and followed by its children ([DEC-23]). To keep 10%: `OTEL_TRACES_SAMPLER=parentbased_traceidratio` and `OTEL_TRACES_SAMPLER_ARG=0.1` | keep everything |
| `OTEL_TRACES_EXPORTER` / `OTEL_LOGS_EXPORTER` / `OTEL_METRICS_EXPORTER` | `otlp`, `console` (print to the terminal, for local debugging) or `none`; for metrics also `prometheus`, which serves them on `OTEL_EXPORTER_PROMETHEUS_PORT` (port 9464 unless set, [DEC-92]) | `otlp` when an endpoint is set, otherwise `none` |
| `OTEL_EXPORTER_PROMETHEUS_PORT` / `OTEL_EXPORTER_PROMETHEUS_HOST` | serve metrics for Prometheus on this port and interface. In Kubernetes, set the host to `0.0.0.0` | not served unless `OTEL_METRICS_EXPORTER` names `prometheus` (port 9464); host `localhost` |
| `OTEL_SDK_DISABLED` | `true` is the same as `OTEL_WRAPPER_DISABLED=true` ([DEC-5]) | `false` |
| `OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_*` | record raw request/response headers as span attributes (`..._SERVER_REQUEST`, `..._CLIENT_REQUEST`, ...); the x-userinfo header is redacted there | none |
| `OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SANITIZE_FIELDS` | header names whose captured values are `[REDACTED]`; the wrapper adds its decoded headers to the list | the decoded headers (`x-userinfo`) |
| `OTEL_PYTHON_FASTAPI_EXCLUDED_URLS` / `OTEL_PYTHON_EXCLUDED_URLS` | URLs that get no request span; the Prometheus route is always added to them | the Prometheus route only |
| `OTEL_EXPERIMENTAL_RESOURCE_DETECTORS` | for plain OpenTelemetry without the wrapper: `otel_wrapper_k8s` and `otel_wrapper_process` are the wrapper's two resource detectors, registered as entry points | not used by the wrapper itself |

**Our own variables**

| Variable | Effect | Default |
|---|---|---|
| `OTEL_WRAPPER_DISABLED` | `true` turns everything into a no-op ([DEC-24]): decorators return your function unchanged (so tracebacks are exactly your code's), `otel.instrument` does nothing, and `with otel as span` gives a span that accepts every call and records nothing. It's also checked at call time, so setting it after decorating works | `false` |
| `OTEL_WRAPPER_LOG_LEVEL` | log level set by `otel.instrument(logging)` | `info` |
| `OTEL_WRAPPER_LOG_FORMAT` | log output on stderr: `json` (one line per log, secrets redacted) or `off` | `json` |
| `OTEL_WRAPPER_HEADER_ATTRIBUTES` | comma-separated request headers to decode (base64 / JSON) and flatten into span attributes; the raw header is not recorded | `x-userinfo` |
| `OTEL_WRAPPER_HEADER_ATTRIBUTES_EXCLUDE` | comma-separated glob patterns of decoded claims to leave out, matched against the flattened name (e.g. `realm_access.roles`, `email`); they are added to the default patterns, which only `otel.configure(header_attributes_exclude=[...])` replaces ([DEC-90]) | `*token*,at_hash,c_hash,nonce,session_state,sid` (always applied unless replaced in code) |
| `OTEL_WRAPPER_RESPONSE_HEADER_ATTRIBUTES` | comma-separated response headers from `requests` calls to record on the client span | `x-kong-proxy-latency,x-kong-upstream-latency,x-envoy-upstream-service-time,x-authz-response-time-seconds,x-process-time-seconds` |
| `OTEL_WRAPPER_SQLALCHEMY_COMMENTER` | add a sqlcommenter comment to every SQLAlchemy query traced from then on: `true` (driver, framework and traceparent), or a comma-separated choice of `db_driver`, `db_framework` and `opentelemetry_values` (the traceparent), plus `attribute` to also record the commented statement on the span ([DEC-91]) | `false` (queries run unchanged) |
| `OTEL_WRAPPER_FASTAPI_ASGI_SPANS` | `true` adds FastAPI's ASGI `http send` / `http receive` spans under each request's server span, for debugging; a value other than `true` or `false` warns once and is ignored ([DEC-93]) | `false` (one server span per request) |
| `OTEL_WRAPPER_PROMETHEUS_PATH` | path for the `/metrics` route added to FastAPI apps, served with and without its trailing slash ([DEC-92]); empty to disable | `/metrics` |
| `OTEL_WRAPPER_CAPTURE_COMMAND_ARGS` | record the process's full command line (secrets redacted); `false` to leave it out | `true` |
| `OTEL_WRAPPER_PODINFO_DIR` | where the pod's labels and annotations are mounted (Downward API volume, [below](#detected-automatically)) | `/etc/podinfo` |
| `OTEL_WRAPPER_DEBUG` | `true` (or `1`) reports every internal failure the wrapper swallows, with its traceback, instead of once per site; a scrubbing failure's message stays withheld even then ([below](#warnings-and-the-wrappers-own-errors)); any other value is off | `false` |

**`otel.configure(...)` options** (each beats its variable)

| Option | Variable | Default |
|---|---|---|
| `service_name` | `OTEL_SERVICE_NAME` | as `OTEL_SERVICE_NAME` |
| `resource_attributes` (a dict) | `OTEL_RESOURCE_ATTRIBUTES` | none beyond the detected ones |
| `traces_exporter` / `logs_exporter` / `metrics_exporter` (a name or a list) | `OTEL_TRACES_EXPORTER` / `OTEL_LOGS_EXPORTER` / `OTEL_METRICS_EXPORTER` | `otlp` when an endpoint is set, otherwise none |
| `otlp_endpoint` | `OTEL_EXPORTER_OTLP_ENDPOINT` | none |
| `otlp_headers` (a dict) | `OTEL_EXPORTER_OTLP_HEADERS` | none |
| `log_level` | `OTEL_WRAPPER_LOG_LEVEL` | `info` |
| `log_format` | `OTEL_WRAPPER_LOG_FORMAT` | `json` |
| `prometheus_path` | `OTEL_WRAPPER_PROMETHEUS_PATH` | `/metrics` |
| `prometheus_host` | `OTEL_EXPORTER_PROMETHEUS_HOST` | `localhost` |
| `prometheus_port` | `OTEL_EXPORTER_PROMETHEUS_PORT` | none (9464 when `metrics_exporter` names `prometheus`) |
| `header_attributes` (a list) | `OTEL_WRAPPER_HEADER_ATTRIBUTES` | `x-userinfo` |
| `header_attributes_exclude` (a list; replaces the default) | `OTEL_WRAPPER_HEADER_ATTRIBUTES_EXCLUDE` (adds to it) | `*token*,at_hash,c_hash,nonce,session_state,sid` |
| `response_header_attributes` (a list) | `OTEL_WRAPPER_RESPONSE_HEADER_ATTRIBUTES` | `x-kong-proxy-latency,x-kong-upstream-latency,x-envoy-upstream-service-time,x-authz-response-time-seconds,x-process-time-seconds` |
| `fastapi_asgi_spans` | `OTEL_WRAPPER_FASTAPI_ASGI_SPANS` | `false` |

An option of the wrong type is ignored with a warning (it falls back to the variable, then the default); an unknown
option is a `TypeError`.

## Metrics

Push them (OTLP, when an endpoint is set) or let Prometheus scrape them:

- **From the app's own port**: FastAPI apps get a `/metrics` route (`OTEL_WRAPPER_PROMETHEUS_PATH`), which makes no
  request span, also under a `root_path`. It answers at both `/metrics` and `/metrics/`, whichever form the path is
  given in, with no redirect ([DEC-92]); only those two paths, so `/api/metrics` and `/metrics/foo` are traced as
  usual. A route of the app's own at either path, even one declared after `otel.instrument(app)`, is kept instead.
- **From a separate port**: `OTEL_EXPORTER_PROMETHEUS_PORT`, which serves metrics on every path, or
  `OTEL_METRICS_EXPORTER=prometheus` alone, which serves them on the spec's default port, 9464 ([DEC-92]).

With several workers per container (`uvicorn --workers N`, gunicorn), each worker has its own metrics: only one can
listen on the Prometheus port (the others warn once and carry on), and the `/metrics` route answers from whichever
worker took the request. In multi-worker deployments use push, or one worker per container. The wrapper computes no
request-rate or latency metrics of its own ([DEC-69]); the instrumentations' standard metrics (e.g.
`http.server.duration`) and your backend cover them.

## Detected automatically

Resource attributes, attached to every span, log and metric. Our detectors are guesses, so `OTEL_SERVICE_NAME` and
`OTEL_RESOURCE_ATTRIBUTES` beat them, and `otel.configure(...)` beats both ([DEC-33]).

- **Kubernetes:** namespace, pod and workload, read from inside the pod with no configuration needed. The Kubernetes
  API is never called ([DEC-12]). `service.name` is the workload name, `service.namespace` the namespace, and
  `service.instance.id` a random id per process (each worker has its own, [DEC-29]). To use the pod's labels and
  annotations too (`app.kubernetes.io/name`, `app.kubernetes.io/instance` and `app.kubernetes.io/version` for
  `service.name` and `service.version`, or `resource.opentelemetry.io/service.name` to set it explicitly), mount them
  with the Downward API at `/etc/podinfo` (or set `OTEL_WRAPPER_PODINFO_DIR`):

  ```yaml
  spec:
    containers:
      - name: app
        volumeMounts:
          - name: podinfo
            mountPath: /etc/podinfo
    volumes:
      - name: podinfo
        downwardAPI:
          items:
            - path: labels
              fieldRef:
                fieldPath: metadata.labels
            - path: annotations
              fieldRef:
                fieldPath: metadata.annotations
  ```
- **Process:** the full command line including the interpreter and its flags (`process.command_args`, e.g.
  `python -X utf8 -m uvicorn app:app`, with secrets redacted, [DEC-30]), the executable name (`process.executable.name`,
  the base name of `sys.executable`, [DEC-4]) and path, the runtime (`cpython`, `pypy`, ...), and which Python
  environment it runs in (`opentelemetry_wrapper.python.environment`: `conda`, `venv`, `system`, `pyodide` or
  `frozen`, with its name and path where it has them).
- **A readable label**, `opentelemetry_wrapper.instance.label`: `<namespace>/<workload>/<pod>` in Kubernetes, otherwise
  `<user>@<host>:<main.py>`. It's the one-glance summary of the attributes above (and v0's old `service.name`).

## Secret scrubbing

Everything the wrapper exports passes through its own scrubbing rules first ([DEC-58]): span attributes, event and
link attributes, log record attributes and bodies, the JSON lines on stderr and `process.command_args`. Keys that name
a secret (`password`, `api_key`, `authorization`, `cookie`, `session_id`, ...) have their whole value replaced by
`[REDACTED]`; values that look like one (bearer and basic credentials, JWTs, private keys, cloud and platform tokens,
the password in `scheme://user:password@host`, secret query parameters) have just the secret part replaced, so
messages stay readable. The span or log record lists what was redacted in `opentelemetry_wrapper.scrubbed` (the path
and the rule, never the value). Decoded x-userinfo claims are let through as they are: the denylist is their control
([DEC-2]).

Scrubbing runs on the exporter's thread, off your code's path. It never crashes the export: a value that fails to
scrub is dropped and replaced by `[REDACTED: scrubbing failed]` ([DEC-74]), and a record whose scrubbing fails as a
whole is exported bare (name, ids, times and an error note), and dropped only if even that fails ([DEC-82]). The
default engine is Python's `re`; with the `[hyperscan]` extra installed, the faster Hyperscan engine is used
automatically ([DEC-16], [DEC-83]).

Scrubbing is a second line of defence, not a licence to log secrets: the first is that arguments are never recorded.
**Anything not behind the wrapper's exporters is not scrubbed**: span processors or exporters you add to the providers
yourself see the raw data, as do the exporters of a provider someone else configured.

## Warnings and the wrapper's own errors

When something can't be instrumented or is misconfigured, you get one `OtelWrapperWarning` (through `warnings.warn`)
at startup: from decoration, `otel.instrument`, `otel.configure` or reading environment variables ([DEC-49]). Never
one per call, and never as a log. To make these fail your tests instead, put
`filterwarnings = error::opentelemetry_wrapper.OtelWrapperWarning` in pytest's configuration or run pytest with
`-W error::opentelemetry_wrapper.OtelWrapperWarning` (not `python -W ...` or `PYTHONWARNINGS`, which the interpreter
parses before the package can be imported). `PYTHONWARNINGS=error` in production turns these startup warnings into
exceptions, which is accepted: it's what was asked for, and it happens before the app is ready ([DEC-8]).

At runtime the wrapper never uses `warnings` ([DEC-81]): a warning that comes up while the app runs (a second unnamed
`with otel:` block, or one from configuration done implicitly by the first span) is one JSON line on stderr, once.
A failure inside the wrapper itself is swallowed and reported the same way, one JSON line on stderr per failure site;
`OTEL_WRAPPER_DEBUG=true` reports every occurrence, with its traceback ([DEC-75]). A value that fails to scrub is
reported the same way, but its exception's message is never written, debug or not, since it could contain the value
itself ([DEC-94]). Under `OTEL_WRAPPER_DEBUG=true` its traceback still shows the stack of every chained exception (its
cause and context), each with its message withheld. Every such report also says what is safe to say about the value:
`value.type` (e.g. `builtins.str`), `value.length` (where it has a length) and `value.path` (the attribute or nested
path, named as in `opentelemetry_wrapper.scrubbed`, `*` for a whole record), each left out when unknown. The wrapper
emits no spans or logs of its own.

## Testing with pytest

The package has a pytest plugin ([DEC-10]). Request the `otel_spans` or `otel_logs` fixture and that test captures
exactly what would be exported (scrubbed, in memory), while the real exporters are switched off for it; the fixtures
start empty in every test. `otel_capture = true` in the pytest configuration switches the exporters off for the whole
suite. Loading the plugin does nothing else; `pytest -p no:opentelemetry_wrapper` keeps it out.

```python
import logging

from opentelemetry_wrapper import otel


@otel
def charge(amount):
    logging.warning('charged %s', amount)


def test_charge_makes_one_span_and_one_log(otel_spans, otel_logs):
    otel.instrument(logging)
    charge(5)
    assert [span.name for span in otel_spans.get_finished_spans()] == [f'{__name__}.charge']
    assert otel_logs.get_finished_logs()[0].log_record.body == 'charged 5'
```

## What it doesn't do

- Record function arguments or return values ([DEC-26]), or copy baggage onto spans ([DEC-6]).
- Sample per span: sampling is decided at the root span ([DEC-23]); there's no do-not-instrument list beyond
  `@otel.ignore` ([DEC-68]).
- Trace a whole package of yours (`otel.instrument(my_package)`, [DEC-60]), or instrument pydantic ([DEC-65]).
- Compute request-rate or latency metrics ([DEC-69]).
- Export over gRPC ([DEC-36]), or print a pretty console ([DEC-34]).
- Undo instrumentation ([DEC-61]).

The design decisions behind all of this are records in [docs/decisions][decisions], each linked above where it
applies.

## Upgrading from v0

Change the import to `from opentelemetry_wrapper import otel`. Until 1.0.0, v0's functions still import from the
package root and behave exactly as they did in v0 ([DEC-80]): they are v0's own code, loaded the first time one of
them is used, not wrappers around v1. At 1.0.0 v0 is deleted ([DEC-37]). Each has a v1 replacement:

| v0 | v1 |
|---|---|
| `@instrument_decorate` | `@otel` |
| `instrument_fastapi_app(app)` | `otel.instrument(app)` |
| `instrument_sqlalchemy()` | `otel.instrument(sqlalchemy)` |
| `instrument_sqlalchemy_engine(engine)` | `otel.instrument(engine)` |
| `instrument_requests()` / `instrument_logging()` | `otel.instrument(requests)` / `otel.instrument(logging)` |
| `instrument_system_metrics()` | `otel.instrument()` (with the `[system-metrics]` extra) |
| `instrument_all()` | `otel.instrument()` |
| `instrument_dataclasses()` (every `@dataclass` in the process) | removed: put `@otel` on the dataclasses you want ([DEC-42]) |

What else changed ([DEC-52]):

- Python 3.12 or later ([DEC-44]).
- `instrument_sqlalchemy_engine(engine)` added a sqlcommenter comment to every query by default; v1 leaves it off,
  so `otel.instrument(engine)` runs queries unchanged ([DEC-91]). To turn v0's comment back on, set
  `OTEL_WRAPPER_SQLALCHEMY_COMMENTER=true` (v0's `commenter_options` are its comma-separated choices).
- `instrument_fastapi_app(app)` also emitted ASGI `http send` / `http receive` spans under each request's server
  span; `otel.instrument(app)` leaves them out ([DEC-93]). To get them back, for debugging, set
  `OTEL_WRAPPER_FASTAPI_ASGI_SPANS=true`.
- `instrument_logging(...)` took options per call; `otel.instrument(logging)` takes none ([DEC-43]). The level is
  `OTEL_WRAPPER_LOG_LEVEL`, the JSON lines go to stderr (`OTEL_WRAPPER_LOG_FORMAT=off` turns them off), and there is
  no text format and no `clobber_other_log_handlers`. The JSON lines keep v0's fields; `tz_utc_offset_seconds` is now
  negative west of UTC (v0 wrote `68400` for UTC-5) and follows daylight saving per log, and functions and classes
  are named `module.qualname`, as span names are.
- `service.name` is now the workload name rather than `namespace/deployment/pod` ([DEC-29]). The old string is in
  `opentelemetry_wrapper.instance.label`, and its parts are in `k8s.namespace.name`, `k8s.deployment.name` and
  `k8s.pod.name`. Outside Kubernetes it's `unknown_service:<executable>` unless you set `OTEL_SERVICE_NAME`
  (`unknown_service:python.exe` on Windows).
- A decorated class spans only the members defined in its own body ([DEC-89]). v0 also spanned the ones it
  inherited: decorate the base classes whose methods you want spans for.
- A decorated generator's span is parented where its first item is asked for, not where the generator object was
  created ([DEC-22]); usually that's the same place, the loop that consumes it.
- Span names: async functions no longer get an `async ` prefix, and unnamed `with` blocks no longer include a line
  number ([DEC-47]).
- Code attributes use the stable semantic-convention keys (`code.function.name`, `code.file.path`,
  `code.line.number`, [DEC-31]).
- Exports are HTTP only, no gRPC ([DEC-36]). If the endpoint uses port `4317` or `grpc://`, or
  `OTEL_EXPORTER_OTLP_PROTOCOL` is `grpc`, you get a warning at startup: point it at the collector's HTTP port,
  usually `4318`.
- `OTEL_EXPORTER_OTLP_HEADERS` values are URL-encoded, so a space becomes `%20`:
  `OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic%20dXNlcjpwYXNz`.
- Exported telemetry is scrubbed of secrets ([DEC-58]), and the configuration is no longer logged with its auth
  header in it.
- Pods without a service account can still set the namespace with the Downward API:

  ```yaml
  env:
    - name: POD_NAMESPACE
      valueFrom:
        fieldRef:
          fieldPath: metadata.namespace
    - name: OTEL_RESOURCE_ATTRIBUTES
      value: service.namespace=$(POD_NAMESPACE)
  ```

Renamed variables (the old names still work for one release, with a warning at startup):

| v0 | v1 |
|---|---|
| `OTEL_LOG_LEVEL` | `OTEL_WRAPPER_LOG_LEVEL` (the old name is the SDK's own internal log level, so it is **not** read, only warned about) |
| `OTEL_HEADER_ATTRIBUTES` | `OTEL_WRAPPER_HEADER_ATTRIBUTES` |
| `OTEL_EXPORTER_PROMETHEUS_ENDPOINT` | `OTEL_WRAPPER_PROMETHEUS_PATH` |
| `OTEL_EXPORTER_OTLP_HEADER` + `OTEL_EXPORTER_OTLP_HEADER_SEPARATOR` (default a tab) | `OTEL_EXPORTER_OTLP_HEADERS` |
| `OTEL_SERVICE_NAMESPACE` | `OTEL_RESOURCE_ATTRIBUTES=service.namespace=...` |
| `OTEL_EXPORTER_OTLP_INSECURE` | removed (a warning): use an `http://` or `https://` endpoint |

[v0-readme]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/archive/README_v0.md
[decisions]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/index.md
[DEC-1]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-1-sqlalchemy-otel-instrument-sqlalchemy-is-global.md
[DEC-2]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-2-x-userinfo-record-every-claim-except-a-denylist.md
[DEC-3]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-3-exception-status-error-on-the-innermost-span.md
[DEC-4]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-4-process-executable-name-is-the-base-name-of-sys.md
[DEC-5]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-5-otel-sdk-disabled-true-also-means-otel-wrapper.md
[DEC-6]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-6-baggage-is-never-copied-onto-spans-q6-obsolete.md
[DEC-8]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-8-pythonwarnings-error-may-crash-startup-accepted.md
[DEC-9]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-9-only-the-log-level-may-change-after.md
[DEC-10]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-10-pytest-plugin-opt-in-requesting-otel-spans-otel.md
[DEC-11]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-11-otel-instrument-with-no-arguments-logging.md
[DEC-12]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-12-no-kubernetes-api-calls-labels-and-annotations.md
[DEC-13]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-13-log-records-keep-the-bare-record-funcname-q13.md
[DEC-15]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-15-logfire-is-not-a-dependency-v1-builds-on-the.md
[DEC-16]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-16-scrubbing-engine-stdlib-re-by-default-hyperscan.md
[DEC-19]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-19-one-otel-object-decorates-and-opens-spans.md
[DEC-20]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-20-configured-otel-objects-are-immutable-and.md
[DEC-22]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-22-generators-and-context-managers-one-span-each.md
[DEC-23]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-23-no-per-span-sampling-sampling-is-decided-at-the.md
[DEC-24]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-24-otel-wrapper-disabled-means-no-telemetry-at-all.md
[DEC-25]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-25-our-spans-come-from-the-otel-tracer-the-exposed.md
[DEC-26]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-26-no-arguments-or-return-values-on-spans.md
[DEC-27]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-27-configuration-implicit-and-explicit-together.md
[DEC-28]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-28-exporters-are-chosen-from-the-standard-otel-env.md
[DEC-29]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-29-service-name-follows-semconv-v0-s-readable-name.md
[DEC-30]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-30-record-the-full-command-line-as-process-command.md
[DEC-31]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-31-stable-semconv-code-keys-everywhere.md
[DEC-32]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-32-logs-are-real-otel-log-records-never-spans.md
[DEC-33]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-33-resource-precedence-our-detectors-otel-service.md
[DEC-34]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-34-console-one-line-json-logs-on-stderr-no-pretty.md
[DEC-35]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-35-pydantic-2-only-optional-never-imported-by-us.md
[DEC-36]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-36-otlp-http-only-grpc-export-dropped.md
[DEC-37]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-37-rollout-v1-ships-beside-v0-becomes-the-default.md
[DEC-42]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-42-global-dataclass-instrumentation-is-dropped.md
[DEC-43]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-43-logging-options-come-from-env-vars-and-otel.md
[DEC-44]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-44-v1-requires-python-3-12-or-later.md
[DEC-45]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-45-escape-hatches-otel-span-otel-trace-id-otel.md
[DEC-47]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-47-unnamed-with-otel-blocks-are-named-after-the.md
[DEC-48]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-48-property-on-top-otel-underneath-proposal-6.md
[DEC-49]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-49-one-otelwrapperwarning-through-warnings-warn-on.md
[DEC-50]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-50-otel-and-with-otel-mean-the-same-as-otel-and.md
[DEC-52]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-52-migration-from-v0-old-env-var-names-for-one.md
[DEC-53]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-53-classes-span-methods-and-constructors-selected.md
[DEC-57]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-57-strict-otel-pins-capped-at-the-next-minor.md
[DEC-58]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-58-v1-scrubs-exported-telemetry-with-its-own-rules.md
[DEC-59]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-59-environment-variables-standard-names-where-they.md
[DEC-60]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-60-auto-tracing-a-user-s-package-otel-instrument.md
[DEC-61]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-61-un-instrumentation-beyond-the-pytest-plugin-s.md
[DEC-65]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-65-instrument-pydantic.md
[DEC-68]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-68-mark-functions-as-do-not-instrument-or-give.md
[DEC-69]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-69-red-metrics-computed-in-the-library.md
[DEC-74]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-74-a-value-that-fails-to-scrub-is-dropped-and.md
[DEC-75]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-75-the-wrapper-reports-its-own-swallowed-runtime.md
[DEC-80]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-80-root-is-v1-v0-s-names-load-lazily-v0-s.md
[DEC-81]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-81-runtime-warnings-go-to-stderr-once-never.md
[DEC-82]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-82-a-record-whose-scrubbing-fails-is-exported-bare.md
[DEC-83]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-83-configure-uses-the-auto-scrubbing-engine-once.md
[DEC-89]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-89-a-decorated-class-spans-only-the-members.md
[DEC-90]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-90-otel-wrapper-header-attributes-exclude-adds-to.md
[DEC-91]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-91-sqlalchemy-sqlcommenter-is-off-by-default-in-v1.md
[DEC-92]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-92-otel-metrics-exporter-prometheus-serves-on-9464.md
[DEC-93]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-93-fastapi-s-asgi-send-receive-spans-are-off-by.md
[DEC-94]: https://github.com/averykhoo/opentelemetry_wrapper/blob/main/docs/decisions/DEC-94-with-otel-wrapper-debug-true-a-scrubbing.md
