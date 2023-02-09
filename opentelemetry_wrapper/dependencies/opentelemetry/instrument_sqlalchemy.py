from typing import Dict
from typing import Optional
from typing import TypeVar

from opentelemetry.instrumentation.sqlalchemy import EngineTracer
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

from opentelemetry_wrapper import instrument_decorate
from opentelemetry_wrapper.config.otel_headers import OTEL_WRAPPER_DISABLED
from opentelemetry_wrapper.dependencies.sqlalchemy.engine_typedef import is_sqlalchemy_async_engine
from opentelemetry_wrapper.dependencies.sqlalchemy.engine_typedef import is_sqlalchemy_engine
from opentelemetry_wrapper.dependencies.sqlalchemy.engine_typedef import is_sqlalchemy_sync_engine

SqlAlchemyEngineType = TypeVar('SqlAlchemyEngineType', bound=type)

_CACHE_INSTRUMENTED: Dict[int, EngineTracer] = dict()


@instrument_decorate
def instrument_sqlalchemy_engine(engine: SqlAlchemyEngineType,
                                 enable_commenter: bool = True,
                                 commenter_options: Optional[Dict[str, bool]] = None,
                                 ) -> SqlAlchemyEngineType:
    """
    instrument an SQLAlchemy engine or async engine
    see: https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/sqlalchemy/sqlalchemy.html

    commenter_options defaults to: {
        'db_driver': True,  # adds any underlying driver like psycopg2 /db_driver='psycopg2'/
        'db_framework': True,  # adds db_framework and its version /db_framework='sqlalchemy:0.41b0'/
        'opentelemetry_values': True,  # add traceparent values /traceparent='00-...-...-01'/
    }

    :param engine: SQLAlchemy engine instance
    :param enable_commenter: enrich the query with contextual information
    :param commenter_options: see notes above
    :return:
    """

    # no-op
    if OTEL_WRAPPER_DISABLED:
        return engine

    # ensure it's actually an engine
    if not is_sqlalchemy_engine(engine):
        return engine

    # avoid double-instrumentation
    _id = id(engine)
    if _id in _CACHE_INSTRUMENTED:
        return engine

    # unwrap async engine
    if is_sqlalchemy_sync_engine(engine):
        _engine = engine
    elif is_sqlalchemy_async_engine(engine) or hasattr(engine, 'sync_engine'):
        _engine = engine.sync_engine  # type: ignore[assignment,attr-defined]
    else:
        _engine = engine

    # instrument engine
    if commenter_options is None:
        _CACHE_INSTRUMENTED[_id] = SQLAlchemyInstrumentor().instrument(engine=_engine,
                                                                       enable_commenter=enable_commenter)
    else:
        _CACHE_INSTRUMENTED[_id] = SQLAlchemyInstrumentor().instrument(engine=_engine,
                                                                       enable_commenter=enable_commenter,
                                                                       commenter_options=commenter_options)

    return engine


@instrument_decorate
def instrument_sqlalchemy() -> None:
    """
    this function is idempotent; calling it multiple times has no additional side effects
    """

    # no-op
    if OTEL_WRAPPER_DISABLED:
        return

    _instrumentor = SQLAlchemyInstrumentor()  # assume this is a singleton
    if not _instrumentor.is_instrumented_by_opentelemetry:
        _instrumentor.instrument()
