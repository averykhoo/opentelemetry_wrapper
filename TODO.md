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

## publishing (notes for myself)

* init
    * `pip install flit`
    * `flit init`
    * make sure `opentelemetry_wrapper/__init__.py` contains a docstring and version
* publish / update
    * increment `__version__` in `opentelemetry_wrapper/__init__.py`
    * `flit publish`
    * update `~/.pypirc` with additional line `password = <...>`

## todo

* update [introspect.py](./opentelemetry_wrapper/utils/introspect.py) for pep 626
    * The f_lineno attribute of frame objects will always contain the expected line number.
    * The co_lnotab attribute of code objects is deprecated and will be removed in 3.12. 
    * Code that needs to convert from offset to line number should use the new co_lines() method instead.
* `OTEL_HEADER_ATTRIBUTES` behaves too much like `OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_REQUEST`
    * consider removing it?
* `with ...` instrumentation for non-callable code (e.g. settings, semi-hardcoded config)
* type-checking decorator, with warning on unmatched types
    * https://github.com/prechelt/typecheck-decorator/blob/master/README.md
    * https://stackoverflow.com/questions/36879932/python-type-checking-decorator
    * https://towardsdatascience.com/the-power-of-decorators-fef4dc97020e
    * https://typeguard.readthedocs.io/en/latest/userguide.html
* correctly handle generators and context managers (and async versions of them)
* instrument pydantic?
* support metrics somehow
    * the asgi/fastapi already supports some metrics
    * https://github.com/instana/python-sensor/blob/master/instana/autoprofile/samplers
        * memory profiling
        * reading frames to make a statistical guess how much time is spent in each function
    * https://psutil.readthedocs.io/en/latest/
    * Request Error Duration metrics can be calculated from spans
* builtin `tracemalloc` can be used locate the source file and line number of a function, if started early enough
    * check for the [`PYTHONTRACEMALLOC`](https://docs.python.org/3/using/cmdline.html#envvar-PYTHONTRACEMALLOC) var?
* somehow mark function as do-not-instrument, for extremely spammy functions? or specify a sampling ratio?
* add a (regex-based?) sanitizer to erase strings/patterns from log output
* print config at startup? at least print the version?
    * or maybe print a json string with all the (non-sensitive) config?
