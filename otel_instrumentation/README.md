# OpenTelemetry instrumentation

* built upon `opentelemetry-instrumentation-*` with a few improvements
  * e.g. all functions are (or should be) idempotent, and shouldn't ever fail or warn

## What this does

* Makes instrumentation idempotent
* Makes re-instrumentation of logging actually work with different format strings
* Logging can (and will by default) print as a one-line JSON dict
* Provides support for decorating functions and classes
* Add global instrumentation of dataclasses
  * But it needs to be run *before* any dataclasses are initialized
  * Otherwise, use the decorator as usual (it's idempotent anyway)
* Add global instrumentation of FastAPI
  * Seems to work even after apps are created for some reason, likely due to how Uvicorn creates the apps

## TODO

* Add support for pushing logs to a real logging platform (Zipkin, Jaeger, etc)
* Read through the best practices
* Metrics? Actual telemetry?
  * https://github.com/instana/python-sensor/blob/master/instana/autoprofile/samplers
    * memory profiling
    * reading frames to make a statistical guess how much time is spent in each function
  * https://psutil.readthedocs.io/en/latest/
  * Request Error Duration metrics can be calculated from spans
* builtin `tracemalloc` can be used locate the source file and line number of a function, if started early enough
* SQLAlchemy
* See [parent README](../README.md)
  * Read k8s namespace from container path?
