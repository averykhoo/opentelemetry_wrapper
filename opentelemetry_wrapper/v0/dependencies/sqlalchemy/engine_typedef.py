from typing import Any
from typing import Tuple

# sync and async engines are imported separately, since the asyncio extension can be missing even when sqlalchemy
# is installed (e.g. sqlalchemy>=2.1 without greenlet), and that should not disable sync engine detection
_SYNC_ENGINE_TYPES: Tuple[type, ...] = ()
_ASYNC_ENGINE_TYPES: Tuple[type, ...] = ()

try:
    from sqlalchemy.engine import Engine as LegacyEngine
    from sqlalchemy.future import Engine as FutureEngine

    _SYNC_ENGINE_TYPES = (LegacyEngine, FutureEngine)
except ImportError:
    pass

try:
    from sqlalchemy.ext.asyncio import AsyncEngine

    _ASYNC_ENGINE_TYPES = (AsyncEngine,)
except ImportError:
    pass


def is_sqlalchemy_engine(item: Any) -> bool:
    return is_sqlalchemy_sync_engine(item) or is_sqlalchemy_async_engine(item)


def is_sqlalchemy_sync_engine(item: Any) -> bool:
    return isinstance(item, _SYNC_ENGINE_TYPES)


def is_sqlalchemy_async_engine(item: Any) -> bool:
    return isinstance(item, _ASYNC_ENGINE_TYPES)
