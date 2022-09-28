## publishing (notes for myself)

* init
  * `pip install flit`
  * `flit init`
  * make sure `opentelemetry_wrapper/__init__.py` contains a docstring and version
* publish / update
  * increment `__version__` in `nmd/__init__.py`
  * `flit publish`

## references / best practices to consider

* [ ] [Implementing health checks](https://aws.amazon.com/builders-library/implementing-health-checks/)
* [ ] [Instrumenting distributed systems for operational visibility](https://aws.amazon.com/builders-library/instrumenting-distributed-systems-for-operational-visibility/)
* [ ] https://tersesystems.com/blog/2019/07/22/targeted-diagnostic-logging-in-production/
* [ ] https://www.honeycomb.io/blog/so-you-want-to-build-an-observability-tool/
* [x] [Instana ASGI Middleware](https://github.com/instana/python-sensor/blob/master/instana/middleware.py)
* [x] [IBM Best Practices](https://www.ibm.com/docs/en/obi/current?topic=tracing-best-practices)
* [x] [10 Things We Forgot to Monitor](https://word.bitly.com/post/74839060954/ten-things-to-monitor)
* [x] `/var/run/secrets/kubernetes.io/serviceaccount/namespace`
  * [x] or `/var/run/secrets/kubernetes.io/serviceaccount/token` which is a jwt containing the namespace
  * [x] also see `/etc/hostname`
* available instrumentation
  * [x] https://github.com/open-telemetry/opentelemetry-python
  * [x] [`pip install opentelemetry-instrumentation-fastapi`](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html)
  * [ ] [`pip install opentelemetry-instrumentation-sqlalchemy`](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/sqlalchemy/sqlalchemy.html)
  * [x] [`pip install opentelemetry-instrumentation-requests`](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/requests/requests.html)
  * [x] [`pip install opentelemetry-instrumentation-logging`](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/logging/logging.html)
* examples
  * jaeger
    * https://github.com/Blueswen/fastapi-jaeger
    * https://github.com/fike/fastapi-blog
    * https://guitton.co/posts/fastapi-monitoring

## todo

* [ ] metrics
* [ ] correctly handle generators and context managers (and async versions of them)
* [ ] instrument pydantic?
* [ ] `with ...` instrumentation for non-callable code (e.g. settings, semi-hardcoded config)
* [ ] generic typing for `instrument_decorate()`
* [ ] somehow delete dependency on fastapi.FastAPI just for type checking, while still correctly checking types
* [ ] somehow require python >= 3.8 as a dependency
* [ ] line-by-line code safety review
* [ ] type-checking decorator, with warning on unmatched types
* [ ] add [usage](./README.md#usage)
* [ ] add deployment instructions using flit
* [ ] Add support for pushing logs to a real logging platform (Zipkin, Jaeger, etc)
* [ ] Read through the best practices
* [ ] Metrics? Actual telemetry?
  * [ ] https://github.com/instana/python-sensor/blob/master/instana/autoprofile/samplers
    * [ ] memory profiling
    * [ ] reading frames to make a statistical guess how much time is spent in each function
  * [ ] https://psutil.readthedocs.io/en/latest/
  * [ ] Request Error Duration metrics can be calculated from spans
* [ ] builtin `tracemalloc` can be used locate the source file and line number of a function, if started early enough
* [ ] SQLAlchemy
* [ ] Read k8s namespace from container path?
* [ ] somehow mark function as do-not-instrument, for extremely spammy functions? or specify a sampling ratio?
