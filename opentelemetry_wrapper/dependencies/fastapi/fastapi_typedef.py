try:
    from fastapi import FastAPI as FastApiType
except ImportError:
    # ignore mypy here since we're only using this as a typedef
    from typing import Any as FastApiType  # type: ignore[assignment] # noqa: F401
