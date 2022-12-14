from typing import TypeVar

from sqlalchemy.engine import Engine as LegacyEngine
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.future import Engine as FutureEngine

AnyEngine = TypeVar('AnyEngine', LegacyEngine, FutureEngine, AsyncEngine)
