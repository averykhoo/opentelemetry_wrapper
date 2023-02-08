from typing import Any

try:
    from fastapi import FastAPI


    def is_fastapi_app(item: Any) -> bool:
        return isinstance(item, FastAPI)


    FastApiType = FastAPI

except ImportError:
    def is_fastapi_app(item: Any) -> bool:
        return False


    # ignore mypy here since we're only using this as a typedef
    FastApiType = Any  # type: ignore[assignment,misc]
