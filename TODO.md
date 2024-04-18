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

* major refactor, renaming and reorganizing all the modules and code
* CICD the tests
* env var to enable/disable console printing for logs, metrics (off by default), and traces
* an intelligent way to include multiple headers in `OTEL_EXPORTER_OTLP_HEADER`
    * may need support for escapes
* rename `OTEL_EXPORTER_*` to `OTEL_COLLECTOR_*`
    * and have separate metric, log, and trace collectors
    * separate for http and grpc exporters too
    * maybe allow multiple urls (delimited by whitespace)?
* rename all env vars to start with `OTEL_WRAPPER_` to make things clear?
* documentation pls, including design decisions
    * make a note somewhere about the trailing slash mounting the prometheus asgi app, which accepts `/**`
    * should the recommendation for `OTEL_EXPORTER_PROMETHEUS_ENDPOINT` be `/metrics` or just `metrics`?
* set `__tracebackhide__=True` (pytest) and `__traceback_hide__=True` (a few others like sentry) in the functions
* how do we disambiguate for the request header attributes `OTEL_HEADER_ATTRIBUTES` and `requests` response attributes?
* `with ...` instrumentation for non-callable code (e.g. settings, semi-hardcoded config)
    * see [next_version_intended_usage.py](./next_version_intended_usage.py)
* correctly handle generators and context managers (and async versions of them)
* [pip install varname](https://github.com/pwwang/python-varname) for magic varname extraction 

### won't do

* ~~instrument pydantic?~~ (too noisy)
* ~~add a (regex-based?) sanitizer to erase strings/patterns from log output~~ (just don't log secrets)
* ~~builtin `tracemalloc` can be used locate the source file and line number of a function, if started early enough~~
    * ~~check for the `PYTHONTRACEMALLOC`var?~~
    * ~~there's also `sys.setttrace`, see also PEP 626~~
* ~~somehow mark functions/endpoints as do-not-instrument, for extremely spammy functions? specify a sampling ratio?~~
    * ~~the nearest sampling ratio should overwrite, but idk how to do that~~
    * ~~how to integrate with the instrumentors? seems impossible?~~
* ~~add RED metrics, e.g. whatever `prometheus-fastapi-instrumentator` is doing~~
    * this should be automatically done in the backend otel collector
