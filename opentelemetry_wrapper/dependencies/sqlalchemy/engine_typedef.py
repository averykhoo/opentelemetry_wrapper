from typing import TypeVar

try:
    from sqlalchemy.engine import Engine as LegacyEngine
except ImportError:
    # ignore mypy here since we're only using this as a typedef
    from typing import Any as LegacyEngine  # type: ignore[assignment] # flake8: noqa: F401

try:
    from sqlalchemy.ext.asyncio import AsyncEngine
except ImportError:
    # ignore mypy here since we're only using this as a typedef
    from typing import Any as AsyncEngine  # type: ignore[assignment] # flake8: noqa: F401

try:
    from sqlalchemy.future import Engine as FutureEngine
except ImportError:
    # ignore mypy here since we're only using this as a typedef
    from typing import Any as FutureEngine  # type: ignore[assignment] # flake8: noqa: F401

AnyEngine = TypeVar('AnyEngine', LegacyEngine, FutureEngine, AsyncEngine)
