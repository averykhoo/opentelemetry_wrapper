from typing import Any
from typing import TypeVar

try:
    from sqlalchemy.engine import Engine as LegacyEngine
    from sqlalchemy.ext.asyncio import AsyncEngine
    from sqlalchemy.future import Engine as FutureEngine


    def is_sqlalchemy_engine(item: Any) -> bool:
        return isinstance(item, (LegacyEngine, AsyncEngine, FutureEngine))


    def is_sqlalchemy_sync_engine(item: Any) -> bool:
        return isinstance(item, (LegacyEngine, FutureEngine))


    def is_sqlalchemy_async_engine(item: Any) -> bool:
        # noinspection PyTypeHints
        return isinstance(item, AsyncEngine)

except ImportError:
    def is_sqlalchemy_engine(item: Any) -> bool:
        return False


    LegacyEngine = Any
    AsyncEngine = Any
    FutureEngine = Any

AnyEngine = TypeVar('AnyEngine', LegacyEngine, FutureEngine, AsyncEngine)
