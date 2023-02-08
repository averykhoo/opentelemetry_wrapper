from typing import Any
from typing import TypeVar

# note: ignore E303 too many blank lines since flak8 disagrees with pycharm
try:
    from sqlalchemy.engine import Engine as LegacyEngine
    from sqlalchemy.ext.asyncio import AsyncEngine
    from sqlalchemy.future import Engine as FutureEngine


    def is_sqlalchemy_engine(item: Any) -> bool:  # noqa: E303
        return isinstance(item, (LegacyEngine, AsyncEngine, FutureEngine))


    def is_sqlalchemy_sync_engine(item: Any) -> bool:  # noqa: E303
        return isinstance(item, (LegacyEngine, FutureEngine))


    def is_sqlalchemy_async_engine(item: Any) -> bool:  # noqa: E303
        # noinspection PyTypeHints
        return isinstance(item, AsyncEngine)

except ImportError:
    def is_sqlalchemy_engine(item: Any) -> bool:
        return False


    # noqa: E303
    LegacyEngine = Any  # type: ignore[assignment,misc]
    AsyncEngine = Any  # type: ignore[assignment,misc]
    FutureEngine = Any  # type: ignore[assignment,misc]

AnyEngine = TypeVar('AnyEngine', LegacyEngine, FutureEngine, AsyncEngine)
