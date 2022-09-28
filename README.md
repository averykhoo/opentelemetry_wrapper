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

## usage

todo: write stuff here

## read the original docs

* [OpenTelemetry](https://opentelemetry.io/docs)
* [OpenTracing](https://opentracing.io/docs)
* [SkyWalking](https://skywalking.apache.org/docs/skywalking-python/latest/readme/)

## Publishing (notes for myself)

* init
  * `pip install flit`
  * `flit init`
  * make sure `opentelemetry_wrapper/__init__.py` contains a docstring and version
* publish / update
  * increment `__version__` in `nmd/__init__.py`
  * `flit publish`