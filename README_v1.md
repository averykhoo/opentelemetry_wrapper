# opentelemetry_wrapper v1 (draft)

OpenTelemetry tracing, logs and metrics for Python apps with one object, `otel`. It's built on the OpenTelemetry
SDK and the standard OpenTelemetry instrumentations, and follows the OpenTelemetry semantic conventions.

```python
from opentelemetry_wrapper import otel
```

`otel` is a decorator and a context manager, and `otel.instrument(...)` instruments libraries and apps. Whatever you
use it on:

- **it's idempotent**: decorating or instrumenting the same thing twice, from anywhere, behaves as if you did it once.
- **it never crashes your app**: anything it can't handle is returned unchanged, with a single warning.
- **it's safe with threads and asyncio**: nested and concurrent spans each get the right parent.

Python 3.12+.

## Making spans

### Functions

One span per call, named after the function. The attributes record where the code lives (`code.function.name`,
`code.file.path`, `code.line.number`); arguments and return values are not recorded. Sync and async functions both
work.

```python
@otel
def square(x):
    return x * x


@otel
async def fetch(url):
    ...
```

### Functions, with options

```python
@otel(name='price lookup', attributes={'currency': 'SGD'})
def lookup(sku):
    ...
```

`attributes` is a dict, so its keys can never clash with options. `@otel()` with no options is the same as `@otel`.

### Methods

Works on plain methods, `@staticmethod`, `@classmethod` and `@property`. Put `@property` on top and `@otel`
underneath: both orders work at runtime, but mypy rejects any decorator above `@property`.

```python
class Cart:
    @otel
    def checkout(self):
        ...

    @property
    @otel
    def total(self):
        ...
```

### Classes and dataclasses

Every method call gets a span, as do the constructors (`__new__`, `__init__`, `__post_init__`), `__call__`, and
`__enter__` / `__exit__` (one span for the whole `with` block). Other dunder methods (`__repr__`, `__eq__`,
`__hash__`, ...) don't. Properties are left out unless you ask for them with `@otel(properties=True)`, since a
property read in a loop is the noisiest thing there is. To leave out a hot method, mark it with `@otel.ignore`.

```python
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
```

Inherited methods get spans too: they are wrapped into the decorated class, so its base classes are left as they are.
Put `@otel` above `@dataclass`, so it sees the generated `__init__`.

Decorating a class changes that class for the whole process, including when you do it to a library's class
(`otel(SortedList)`). Built-in and extension types (`dict`, most C classes) can't be changed: they're returned as they
are, with a warning.

### Generators

One span from the first item until the generator is exhausted or abandoned. Only the generator's own work is inside the
span; whatever the loop body does between items stays under the caller. The span records how many items were yielded
and how long the generator was actually running, since its duration also includes time spent waiting for the
consumer. Async generators work the same way.

```python
@otel
def read_rows(path):
    with open(path) as f:
        for line in f:
            yield parse(line)


for row in read_rows('data.csv'):  # this loop body is not part of the `read_rows` span
    ...
```

### Context managers

Put `@otel` **above** `@contextmanager` / `@asynccontextmanager`. The span covers entry, the whole `with` block and
exit, and anything inside the block becomes a child of it.

```python
@otel
@contextmanager
def transaction():
    ...
    yield
    ...


with transaction():  # spans and logs in here are children of `transaction`
    ...
```

Class-based context managers get the same single entry-to-exit span when the class is decorated.

### Blocks of code

`with otel:` without a name is named after the function it's in, e.g. `app.config.load_config` (or
`app.config.<module>` at module level). The line number isn't part of the name, so editing the file doesn't change it;
it's in `code.line.number`. Two unnamed blocks in one function would share a name, so you get a warning; prefer
`with otel('name'):`. `with otel():` is the same as `with otel:`, and `async with` works too.

```python
with otel:
    ...

with otel('load settings'):
    ...

with otel('load settings', attributes={'source': 'env'}) as span:
    span.set_attribute('count', 3)
```

`span` is a standard OpenTelemetry `Span`.

### The current span

`otel.span` is the current span (a span that records nothing when there isn't one, never `None`). `otel.trace_id`
and `otel.span_id` are its ids as hex strings (all zeros when there's no span), e.g. to put in an error response so
a user's report can be matched to its trace.

```python
otel.span.set_attribute('order_id', order.id)
otel.span.add_event('cache miss', {'key': key})
otel.span.record_exception(exc)                                  # record without raising
otel.span.set_status(Status(StatusCode.ERROR, 'quota exceeded'))  # mark failed without raising

return JSONResponse({'error': 'internal', 'trace_id': otel.trace_id}, status_code=500)
```

Logs are linked to the current span automatically, and `extra={...}` becomes attributes on the log record:
`logging.info('paid', extra={'order_id': 7})`.

### Warnings

When something can't be instrumented or is misconfigured, you get one `OtelWrapperWarning` at startup (decoration,
`otel.instrument`, `otel.configure` or reading environment variables), never one per call and never as a log. To
make these fail your tests instead, run pytest with `-W error::opentelemetry_wrapper.OtelWrapperWarning`.

### Libraries and apps

Pass the thing itself to `otel.instrument`; you get it back, instrumented.

```python
import logging
import requests
import sqlalchemy

app = otel.instrument(FastAPI())  # request spans, decoded x-userinfo attributes, /metrics route
otel.instrument(sqlalchemy)       # every SQLAlchemy engine created from now on: query and connect spans
otel.instrument(engine)           # just this Engine or AsyncEngine: query spans, but no connect spans
otel.instrument(requests)         # outgoing HTTP spans
otel.instrument(logging)          # OTel log records + one-line JSON on stderr, linked to the current span
otel.instrument()                 # everything installed that can be instrumented globally (logging, requests, ...)
```

**SQLAlchemy:** `otel.instrument(sqlalchemy)` only reaches engines created *after* the call, so call it before
creating engines, or also pass the existing engines in. `otel.instrument(engine)` traces that engine's queries only:
connection spans (`connect`) come from the global instrumentation and aren't available per engine.
`otel.instrument()` leaves SQLAlchemy out, because query spans are noisy.

**x-userinfo:** every claim in the header is recorded (custom ones such as `employee_id` included), except those
matching `OTEL_WRAPPER_HEADER_ATTRIBUTES_EXCLUDE` (tokens and session ids by default). Personal data such as `email`
and `name` is recorded unless you add it to that list.

## Configuration

Everything is configured with environment variables, using the standard OpenTelemetry names wherever one exists.
Nothing needs to be set up before using `otel`: `otel.instrument(...)` configures it, and otherwise the first span
does. To set options in code instead, call `otel.configure(...)` at startup, **before `otel.instrument(...)`** and
before the first span (e.g. `otel.configure(service_name='checkout')`); explicit options beat environment variables.
Configuration is fixed once it's been set up: a later call with different options is ignored, with a warning (only
the log level can still change).

**Standard OpenTelemetry variables**

| Variable | Effect | Default |
|---|---|---|
| `OTEL_SERVICE_NAME` | `service.name` | in Kubernetes, the workload name (Deployment, StatefulSet, ...); otherwise `unknown_service:<executable>`, e.g. `unknown_service:python3.12` or `unknown_service:python.exe` |
| `OTEL_RESOURCE_ATTRIBUTES` | extra resource attributes, e.g. `service.namespace=shop,service.version=1.2.0` | detected Kubernetes, process and host attributes (below) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | where to push traces, logs and metrics (OTLP over HTTP, usually port 4318). Logs are OTel log records carrying the current span's trace and span ids. Per-signal variants `OTEL_EXPORTER_OTLP_{TRACES,LOGS,METRICS}_ENDPOINT` override it | nothing is exported |
| `OTEL_EXPORTER_OTLP_HEADERS` | headers sent to the endpoint: `key=value,key2=value2` | none |
| `OTEL_TRACES_SAMPLER` / `OTEL_TRACES_SAMPLER_ARG` | which traces to keep, decided at the root span and followed by its children. To keep 10%: `OTEL_TRACES_SAMPLER=parentbased_traceidratio` and `OTEL_TRACES_SAMPLER_ARG=0.1` | keep everything |
| `OTEL_TRACES_EXPORTER` / `OTEL_LOGS_EXPORTER` / `OTEL_METRICS_EXPORTER` | `otlp`, `console` (print to the terminal, for local debugging) or `none` | `otlp` when an endpoint is set |
| `OTEL_EXPORTER_PROMETHEUS_PORT` / `_HOST` | serve metrics for Prometheus on this port and interface. In Kubernetes, set `_HOST=0.0.0.0` | not served (host defaults to `localhost`) |
| `OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_*` | record raw request/response headers as span attributes | none |

**Our own variables**

| Variable | Effect | Default |
|---|---|---|
| `OTEL_WRAPPER_DISABLED` | `true` turns everything into a no-op: decorators return your function unchanged (so tracebacks are exactly your code's), `otel.instrument` does nothing, and `with otel as span` gives a span that accepts every call and records nothing | `false` |
| `OTEL_WRAPPER_LOG_LEVEL` | log level set by `otel.instrument(logging)` | `info` |
| `OTEL_WRAPPER_LOG_FORMAT` | log output on stderr: `json` (one line per log, secrets redacted) or `off` | `json` |
| `OTEL_WRAPPER_HEADER_ATTRIBUTES` | comma-separated request headers to decode (base64 / JSON) and flatten into span attributes; the raw header is not recorded | `x-userinfo` |
| `OTEL_WRAPPER_HEADER_ATTRIBUTES_EXCLUDE` | comma-separated glob patterns of decoded claims to leave out, matched against the flattened name (e.g. `realm_access.roles`, `email`) | `*token*,at_hash,c_hash,nonce,session_state,sid` |
| `OTEL_WRAPPER_RESPONSE_HEADER_ATTRIBUTES` | comma-separated response headers from `requests` calls to record on the client span | Kong and Envoy headers, e.g. `X-Envoy-Upstream-Service-Time` |
| `OTEL_WRAPPER_PROMETHEUS_PATH` | path for the `/metrics` route added to FastAPI apps; empty to disable | `/metrics` |
| `OTEL_WRAPPER_CAPTURE_COMMAND_ARGS` | record the process's full command line (secrets redacted); `false` to leave it out | `true` |
| `OTEL_WRAPPER_PODINFO_DIR` | where the pod's labels and annotations are mounted (Downward API volume, see below) | `/etc/podinfo` |

**Detected automatically** (resource attributes, attached to every span, log and metric):

- **Kubernetes:** namespace, pod and workload, read from inside the pod with no configuration needed. The Kubernetes
  API is never called. To use the pod's labels and annotations too (e.g. `app.kubernetes.io/name` for
  `service.name`, or `resource.opentelemetry.io/service.name` to set it explicitly), mount them with the Downward
  API at `/etc/podinfo` (or set `OTEL_WRAPPER_PODINFO_DIR`):

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
  `python -X utf8 -m uvicorn app:app`), the interpreter path, the runtime (`cpython`, `pypy`, ...), and which Python
  environment it runs in (`opentelemetry_wrapper.python.environment`: `conda`, `venv`, `system`, `pyodide` or
  `frozen`).
- **A readable label**, `opentelemetry_wrapper.instance.label`: `<namespace>/<workload>/<pod>` in Kubernetes, otherwise
  `<user>@<host>:<main.py>`. It's the one-glance summary of the attributes above (and v0's old `service.name`).

### Upgrading from v0

Change the import to `from opentelemetry_wrapper import otel`. For one release, the v0 functions still work as
deprecated aliases:

| v0 | v1 |
|---|---|
| `@instrument_decorate` | `@otel` |
| `instrument_fastapi_app(app)` | `otel.instrument(app)` |
| `instrument_sqlalchemy()` | `otel.instrument(sqlalchemy)` |
| `instrument_sqlalchemy_engine(engine)` | `otel.instrument(engine)` |
| `instrument_requests()` / `instrument_logging()` | `otel.instrument(requests)` / `otel.instrument(logging)` |
| `instrument_all()` | `otel.instrument()` |
| `instrument_dataclasses()` (every `@dataclass` in the process) | removed: put `@otel` on the dataclasses you want |

What else changed:

- `service.name` is now the workload name rather than `namespace/deployment/pod`. The old string is in
  `opentelemetry_wrapper.instance.label`, and its parts are in `k8s.namespace.name`, `k8s.deployment.name` and
  `k8s.pod.name`.
- Span names: async functions no longer get an `async ` prefix, and unnamed `with` blocks no longer include a line
  number.
- Exports are HTTP only (no gRPC). If the endpoint uses port `4317` or `grpc://`, or `OTEL_EXPORTER_OTLP_PROTOCOL` is
  `grpc`, you get a warning at startup: point it at the collector's HTTP port, usually `4318`.
- `OTEL_EXPORTER_OTLP_HEADERS` values are URL-encoded, so a space becomes `%20`:
  `OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic%20dXNlcjpwYXNz`.
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

Renamed variables (the old names still work for one release, with a warning):

| v0 | v1 |
|---|---|
| `OTEL_LOG_LEVEL` | `OTEL_WRAPPER_LOG_LEVEL` (the old name is the SDK's own internal log level, so it is **not** read, only warned about) |
| `OTEL_HEADER_ATTRIBUTES` | `OTEL_WRAPPER_HEADER_ATTRIBUTES` |
| `OTEL_EXPORTER_PROMETHEUS_ENDPOINT` | `OTEL_WRAPPER_PROMETHEUS_PATH` |
| `OTEL_EXPORTER_OTLP_HEADER` + `_HEADER_SEPARATOR` | `OTEL_EXPORTER_OTLP_HEADERS` |
| `OTEL_SERVICE_NAMESPACE` | `OTEL_RESOURCE_ATTRIBUTES=service.namespace=...` |
| `OTEL_EXPORTER_OTLP_INSECURE` | removed: use an `http://` or `https://` endpoint |
