## Testing

```shell
pip install flake8
flake8 --max-line-length 119 ./opentelemetry_wrapper/

pip install sqlalchemy2-stubs
pip install mypy
mypy --install-types
mypy ./opentelemetry_wrapper/
```

also run the following files:

* experiment_otel_logging.py
* fastapi_main.py
* setup_otel_logging.py
* sqlalchemy_example.py
* log_weird_things.py

## publishing (notes for myself)

* init
    * create `~/.pypirc` file with the following contents:
      ```ini
      [pypi]
      username = __token__
      password = <insert pypi token here> 
      ```
    * `flit init`
    * `pip install flit`
    * make sure `opentelemetry_wrapper/__init__.py` contains a docstring and version
* publish / update
    * increment `__version__` in `opentelemetry_wrapper/__init__.py`
    * `flit publish`
* check that it can be downloaded/installed
    * `cd tmp`
    * `pip download opentelemetry_wrapper==X.Y.Z` <- replace with latest `__version__`

## todo

* allow exposing prometheus via fastapi endpoint in an instrumented app
    * probably create an asgi app and mount it to /metrics or something
* consider RED metrics, e.g. whatever `prometheus-fastapi-instrumentator` is doing
* documentation pls, including design decisions
* rename `OTEL_EXPORTER_*` to `OTEL_COLLECTOR_*`
    * and have separate metric, log, and trace collectors
    * separate for http and grpc exporters too
    * maybe allow multiple urls (delimited by whitespace)?
* env var to enable/disable console printing for logs, metrics (off by default), and traces
* set `__tracebackhide__=True` (pytest) and `__traceback_hide__=True` (a few others like sentry) in the functions
* update [introspect.py](./opentelemetry_wrapper/utils/introspect.py) for pep 626
    * The f_lineno attribute of frame objects will always contain the expected line number.
    * The co_lnotab attribute of code objects is deprecated and will be removed in 3.12.
    * Code that needs to convert from offset to line number should use the new co_lines() method instead.
* `OTEL_HEADER_ATTRIBUTES` behaves too much like `OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_REQUEST`
    * consider removing it?
* `with ...` instrumentation for non-callable code (e.g. settings, semi-hardcoded config)
    * see [next_version_intended_usage.py](./next_version_intended_usage.py)
* type-checking decorator, with warning on unmatched types
    * https://github.com/prechelt/typecheck-decorator/blob/master/README.md
    * https://stackoverflow.com/questions/36879932/python-type-checking-decorator
    * https://towardsdatascience.com/the-power-of-decorators-fef4dc97020e
    * https://typeguard.readthedocs.io/en/latest/userguide.html
    * or use `pydantic.TypeAdaptor` to manually check
* correctly handle generators and context managers (and async versions of them)
* instrument pydantic?
* validate support for metrics
    * the asgi/fastapi already supports some metrics
    * https://github.com/instana/python-sensor/blob/master/instana/autoprofile/samplers
        * memory profiling
        * reading frames to make a statistical guess how much time is spent in each function
    * https://psutil.readthedocs.io/en/latest/
    * Request Error Duration metrics can be calculated from spans
* also add a prometheus endpoint for scraping?
* builtin `tracemalloc` can be used locate the source file and line number of a function, if started early enough
    * check for the [`PYTHONTRACEMALLOC`](https://docs.python.org/3/using/cmdline.html#envvar-PYTHONTRACEMALLOC) var?
* somehow mark functions/endpoints as do-not-instrument, for extremely spammy functions? or specify a sampling ratio?
    * the nearest sampling ratio should overwrite, but idk how to do that
* add a (regex-based?) sanitizer to erase strings/patterns from log output
* print config at startup? at least print the version?
    * or maybe print a json string with all the (non-sensitive) config?
