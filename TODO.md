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

* allow disabling the sqlalchemy integration since that can be too logging-heavy
* `with ...` instrumentation for non-callable code (e.g. settings, semi-hardcoded config)
* use [`typer`](https://typer.tiangolo.com) to make a cli
  * to auto-modify code in-place to instrument requests, logging, fastapi, and sqlalchemy
  * to auto-instrument classes, dataclasses, functions
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
* somehow mark function as do-not-instrument, for extremely spammy functions? or specify a sampling ratio?
