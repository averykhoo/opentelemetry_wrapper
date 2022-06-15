# opentelemetry-experiments

testing out python logging with opentelemetry

## read the docs

* [OpenTelemetry](https://opentelemetry.io/docs)
* [OpenTracing](https://opentracing.io/docs)
* [SkyWalking](https://skywalking.apache.org/docs/skywalking-python/latest/readme/)

## best practices to consider

* [Implementing health checks](https://aws.amazon.com/builders-library/implementing-health-checks/)
* [Instrumenting distributed systems for operational visibility](https://aws.amazon.com/builders-library/instrumenting-distributed-systems-for-operational-visibility/)
* [Instana ASGI Middleware](https://github.com/instana/python-sensor/blob/master/instana/middleware.py)
* [IBM Best Practices](https://www.ibm.com/docs/en/obi/current?topic=tracing-best-practices)
* [10 Things We Forgot to Monitor](https://word.bitly.com/post/74839060954/ten-things-to-monitor)
* `/var/run/secrets/kubernetes.io/serviceaccount/namespace`
  * or `/token` which is a jwt containing the namepace
  * also see `/etc/hostname`
* available instrumentation
  * https://github.com/open-telemetry/opentelemetry-python
  * [`pip install opentelemetry-instrumentation-fastapi`](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html)
  * [`pip install opentelemetry-instrumentation-sqlalchemy`](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/sqlalchemy/sqlalchemy.html)
  * [`pip install opentelemetry-instrumentation-requests`](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/requests/requests.html)
  * [`pip install opentelemetry-instrumentation-logging`](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/logging/logging.html)
* examples
  * jaeger
    * https://github.com/Blueswen/fastapi-jaeger
    * https://github.com/fike/fastapi-blog
    * https://guitton.co/posts/fastapi-monitoring
    * 