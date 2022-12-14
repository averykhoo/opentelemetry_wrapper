# opentelemetry_wrapper

a wrapper around `opentelemetry` and `opentelemetry-instrumentation-*` to make life a bit easier

## what this does (or is supposed to do)

* Make instrumentation (more) idempotent
* Make re-instrumentation of logging actually work with different format strings
* Make `logging` print as a one-line JSON dict by default
* Provide support for decorating functions and classes
* Provide support for instrumentation of dataclasses
    * Global instrumentation needs to be run *before* any dataclasses are initialized
    * Otherwise, use the decorator on each class as usual (it's idempotent anyway)
* Add global instrumentation of FastAPI
    * sometimes works even after apps are created for some reason, likely due to how Uvicorn runs in a new process
    * but somehow sometimes doesn't work in prod, for equally unknown reasons
    * probably best to instrument each app instance
* Logs some http headers received by fastapi as span attributes
* Creates OTLP exporter if specific env vars (below) are set

## usage

todo: write stuff here

## env vars

| Variable Name                 | Description                                                                                                                                       | Default (if not set)                                                                        |
|-------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Looks like `http://tempo.localhost:4317`.                                                                                                         | *NA* (traces are not exported to any OTLP endpoint)                                         |
| `OTEL_EXPORTER_OTLP_HEADER`   | Looks like `Header-Name=header value`, where values can contain space ('\x20'). To insert multiple headers, delimit by any other whitespace char. | *NA* (no header sent to OTLP endpoint)                                                      |
| `OTEL_EXPORTER_OTLP_INSECURE` | Set to `true` to disable SSL for OTLP trace exports.                                                                                              | `false` (verifies SSL)                                                                      |
| `OTEL_HEADER_ATTRIBUTES`      | HTTP headers to extract as span attributes, split by whitespace.                                                                                  | x-pf-number, x-client-id, x-preferred-username, x-resource-access                           |
| `OTEL_LOG_LEVEL`              | Log level used by the logging instrumentor (case-insensitive).                                                                                    | `info`                                                                                      |
| `OTEL_SERVICE_NAME`           | Sets the value of the `service.name` resource attribute.                                                                                          | f'{k8s namespace}/{k8s pod name}' or f'{username}@{hostname}.{domain}:<{filename of main}>' |
| `OTEL_SERVICE_NAMESPACE`      | Sets the value of the `service.namespace` resource attribute.                                                                                     | f'{k8s namespace}' or None                                                                  |
| `OTEL_WRAPPER_DISABLED`       | Set to `true` to disable tracing globally (e.g. when running pytest).                                                                             | `false` (tracing is enabled)                                                                |

> **Note:** <br>
> The `service.name` and `service.namespace` can also be set via `OTEL_RESOURCE_ATTRIBUTES`, but any settings there 
> will be overwritten by `OTEL_SERVICE_NAME` and `OTEL_SERVICE_NAMESPACE`. For more details, read the
> original [OpenTelemetry docs](https://opentelemetry.io/docs)
