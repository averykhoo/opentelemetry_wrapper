import datetime
import logging
import os
from typing import Callable

import requests
import uvicorn
from fastapi import FastAPI
from fastapi import Request
from fastapi import status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import RedirectResponse
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.logging.constants import DEFAULT_LOGGING_FORMAT
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.export import ConsoleSpanExporter
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI(title='My Super Project',
              description='This is a very fancy project, with auto docs for the API and everything',
              version='2.5.0',  # only semver makes sense here
              )
FastAPIInstrumentor.instrument_app(app)
RequestsInstrumentor().instrument()

# instrument logging.Logger
# write as 0xBEEF instead of BEEF so it matches the trace exactly
_log_format = (DEFAULT_LOGGING_FORMAT
               .replace('%(otelTraceID)s', '0x%(otelTraceID)s')
               .replace('%(otelSpanID)s', '0x%(otelSpanID)s'))
LoggingInstrumentor().instrument(set_logging_format=True, logging_format=_log_format)

# init tracer
trace.set_tracer_provider(tp := TracerProvider())
tp.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter(formatter=lambda span: f'{span.to_json(indent=None)}\n')))
tracer = trace.get_tracer(__name__)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(SessionMiddleware, secret_key='config.settings.secret_key')
app.add_middleware(CORSMiddleware,
                   allow_origins=['*'],
                   allow_credentials=True,
                   allow_methods=['*'],
                   allow_headers=['*'])


@app.middleware('http')
async def add_process_time_header(request: Request, call_next: Callable):
    request.state.start_time = datetime.datetime.now()
    response = await call_next(request)
    process_time = (datetime.datetime.now() - request.state.start_time).total_seconds()
    response.headers['X-Process-Time-Seconds'] = str(process_time)
    return response


@app.get('/', status_code=status.HTTP_307_TEMPORARY_REDIRECT, include_in_schema=False)
async def home():
    return RedirectResponse(url='/docs')


@app.get('/hello')
def hello() -> str:
    logging.info('called `hello`')
    return 'hello'


@app.get('/hello-hello')
def hello_hello() -> str:
    logging.info('called `hello-hello`')
    r = requests.get('http://localhost:8000/hello')
    logging.info(f'`hello` returned {r.text}')
    return r.text


if __name__ == '__main__':
    _module_name = os.path.basename(__file__).rsplit(".", 1)[0]
    uvicorn.run(f'{_module_name}:app',
                host='localhost',
                port=8000,
                reload=True,
                access_log=True,
                # workers=2,  # not valid with reload=True
                # proxy_headers=True,  # github.com/encode/uvicorn/blob/master/uvicorn/middleware/proxy_headers.py
                limit_concurrency=128,
                )
