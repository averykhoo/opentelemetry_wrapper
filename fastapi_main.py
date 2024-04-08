import datetime
import inspect
import logging
from typing import Callable

import requests
import uvicorn
from fastapi import FastAPI
from fastapi import Request
from fastapi import status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from opentelemetry_wrapper import instrument_all
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_fastapi import instrument_fastapi_app

instrument_all()

app = instrument_fastapi_app(FastAPI(title='My Super Project',
                                     description='This is a very fancy project, with docs for the API and everything',
                                     version='2.5.0',  # only semver makes sense here
                                     ))

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


@app.get('/hello/{name}')
def hello2(name: str) -> str:
    logging.info(f'called `hello/{name}`')
    return 'hello'


@app.get('/hello-hello')
def hello_hello() -> str:
    logging.info('called `hello-hello`')
    r = requests.get('http://localhost:8000/hello/hello')
    logging.info(f'`hello` returned {r.text}')
    return r.text


if __name__ == '__main__':
    uvicorn.run(f'{inspect.getmodulename(__file__)}:app',
                host='localhost',
                port=8000,
                # reload=True,
                access_log=True,
                workers=2,  # not valid with reload=True
                # proxy_headers=True,  # github.com/encode/uvicorn/blob/master/uvicorn/middleware/proxy_headers.py
                limit_concurrency=128,
                # log_config=None, # this tells uvicorn not to set up its own logger
                )
