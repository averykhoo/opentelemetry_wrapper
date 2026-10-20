from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine

from opentelemetry_wrapper import otel

if __name__ == '__main__':
    # spans on stdout (v1 exports nothing unless told to)
    otel.configure(traces_exporter='console')

    engine = create_engine('sqlite:///:memory:')

    # `otel.instrument` takes a sync `Engine` or an `AsyncEngine` (v0 had its own checks for these)
    print('is_sqlalchemy_engine', isinstance(engine, (Engine, AsyncEngine)))
    print('is_sqlalchemy_sync_engine', isinstance(engine, Engine))
    print('is_sqlalchemy_async_engine', isinstance(engine, AsyncEngine))

    otel.instrument(engine)

    conn = engine.connect()

    # noinspection SqlDialectInspection,SqlNoDataSourceInspection
    exe = conn.execute(text('SELECT * FROM sqlite_master'))
    assert exe.fetchmany() == []
