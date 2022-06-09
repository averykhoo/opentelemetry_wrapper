import logging
from functools import reduce
from typing import Any
from typing import Dict
from typing import Optional
from typing import Union

import fastapi
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.export import ConsoleSpanExporter

__version__ = '0.1'

# write IDs as 0xBEEF instead of BEEF so it matches the trace json exactly
LOGGING_FORMAT_VERBOSE = (
    '%(asctime)s '
    '%(levelname)-8s '
    '[%(name)s] '
    '[%(filename)s:%(funcName)s:%(lineno)d] '
    '[trace_id=0x%(otelTraceID)s span_id=0x%(otelSpanID)s resource.service.name=%(otelServiceName)s] '
    '- %(message)s'
)
LOGGING_FORMAT_MINIMAL = (
    '%(levelname)-8s '
    '%(otelServiceName)s '
    '[00-%(otelTraceID)s-%(otelSpanID)s-01] '
    '[%(name)s:%(module)s:%(funcName)s] '
    '%(message)s'
)

# init tracer
trace.set_tracer_provider(tp := TracerProvider())
tp.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter(formatter=lambda span: f'{span.to_json(indent=None)}\n')))
tracer = trace.get_tracer(__name__, __version__)


def instrument_logging(*, verbose: bool = True):
    with tracer.start_as_current_span('instrument_logging'):
        # re-instrument if called
        _instrumentor = LoggingInstrumentor()
        if _instrumentor.is_instrumented_by_opentelemetry:
            _instrumentor.uninstrument()
        _instrumentor.instrument(set_logging_format=False)

        # force overwrite of logging basic config since their instrumentor doesn't do it correctly
        logging.basicConfig(format=LOGGING_FORMAT_VERBOSE if verbose else LOGGING_FORMAT_MINIMAL,
                            level=logging.DEBUG if verbose else logging.INFO,
                            force=True,
                            )


def instrument_fastapi(app: fastapi.FastAPI):
    with tracer.start_as_current_span('instrument_fastapi'):
        # first instrument logging, if not already instrumented
        if not LoggingInstrumentor().is_instrumented_by_opentelemetry:
            instrument_logging()

        # instrument the app
        FastAPIInstrumentor.instrument_app(app)

        # instrument requests as well
        try:
            import requests
            RequestsInstrumentor().instrument()
        except ImportError:
            pass

        # return app
        return app


def logging_tree():
    """
    from: https://github.com/brandon-rhodes/logging_tree/blob/master/logging_tree/nodes.py
    Return a tree of tuples representing the logger layout.
    Each tuple looks like ``('logger-name', <Logger>, [...])`` where the
    third element is a list of zero or more child tuples that share the
    same layout.
    """
    root: Dict[Optional[str], Any] = {None: logging.root}
    for logger_name in sorted(logging.root.manager.loggerDict.keys()):
        logger = logging.root.manager.loggerDict[logger_name]
        if isinstance(logger, logging.Logger):
            reduce(lambda node, name: node.setdefault(name, {}), logger_name.split('.'), root)[None] = logger
    return root


tmp = ('',
       [('asyncio'),
        ('charset_normalizer'),
        ('concurrent',
         [('concurrent.futures')]),
        ('fastapi'),
        # ('opentelemetry',
        # [('opentelemetry.attributes'),
        #  ('opentelemetry.baggage',
        #   [('opentelemetry.baggage.propagation')]),
        #  ('opentelemetry.context'),
        #  ('opentelemetry.instrumentation',
        #   [('opentelemetry.instrumentation.dependencies'),
        #    ('opentelemetry.instrumentation.fastapi'),
        #    ('opentelemetry.instrumentation.instrumentor')]),
        #  ('opentelemetry.propagate'),
        #  ('opentelemetry.propagators',
        #   [('opentelemetry.propagators.composite')]),
        #  ('opentelemetry.sdk',
        #   [('opentelemetry.sdk.resources'),
        #    ('opentelemetry.sdk.trace',
        #     [('opentelemetry.sdk.trace.export'),
        #      ('opentelemetry.sdk.trace.sampling')])]),
        #  ('opentelemetry.trace',
        #   [('opentelemetry.trace.span'),
        #    ('opentelemetry.trace.status')]),
        #  ('opentelemetry.util',
        #   [('opentelemetry.util._providers'),
        #    ('opentelemetry.util.http',
        #     [('opentelemetry.util.http.httplib')]),
        #    ('opentelemetry.util.re')])]),
        ('pkg_resources',
         [('pkg_resources.extern',
           [('pkg_resources.extern.packaging',
             [('pkg_resources.extern.packaging.tags')])])]),
        ('requests'),
        ('urllib3',
         [('urllib3.connection'),
          ('urllib3.connectionpool'),
          ('urllib3.poolmanager'),
          ('urllib3.response'),
          ('urllib3.util',
           [('urllib3.util.retry')])]),
        ('uvicorn',
         [('uvicorn.error')])])
