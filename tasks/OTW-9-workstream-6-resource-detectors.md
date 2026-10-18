---
type: Task
id: OTW-9
title: 'Workstream 6: resource detectors'
brief: never call the Kubernetes API; never put a whole pod name in service.name
pri: NEXT
state: open
deps: [OTW-2, OTW-8]
source: session 2026-10-18a
created: 2026-10-18
moved: 2026-10-18a
updated: 2026-10-18a
aliases: [WS6]
labels: [v1]
---

Criteria: AC-14, AC-15, AC-16. Decisions: DEC-4, DEC-12, DEC-29, DEC-30, DEC-33.

*Workstream 6 of the v1 design, verbatim from the pre-adoption `PLAN.md` (`docs/archive/PLAN.md`); there, "workstream n" is the task aliased `WSn` (OTW-1 lists them), "Decided" / "proposal n" / "Qn" are decisions (`docs/evidence/adoption-map-2026-10-18.md`), and "`HANDOFF.md`" is the old note in `docs/evidence/history-to-2026-10-18.md`.*

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

## Traps

- `detect()` must finish well inside `get_aggregated_resources`' 5 s timeout.
- Fork behaviour can only be checked on Linux CI.

## Read first

- The decisions: [DEC-4](../docs/decisions/DEC-4-process-executable-name-is-the-base-name-of-sys.md), [DEC-12](../docs/decisions/DEC-12-no-kubernetes-api-calls-labels-and-annotations.md), [DEC-29](../docs/decisions/DEC-29-service-name-follows-semconv-v0-s-readable-name.md), [DEC-30](../docs/decisions/DEC-30-record-the-full-command-line-as-process-command.md), [DEC-33](../docs/decisions/DEC-33-resource-precedence-our-detectors-otel-service.md); [the criteria](../docs/criteria.md)
- [v1 design evidence](../docs/evidence/v1-design-evidence-2026-10-18.md): Resources
