from typing import Any

# note: ignore E303 too many blank lines since flak8 disagrees with pycharm
try:
    from fastapi import FastAPI


    def is_fastapi_app(item: Any) -> bool:  # noqa: E303
        return isinstance(item, FastAPI)


    # noqa: E303
    FastApiType = FastAPI

except ImportError:
    def is_fastapi_app(item: Any) -> bool:
        return False


    # noqa: E303
    # ignore mypy here since we're only using this as a typedef
    FastApiType = Any  # type: ignore[assignment,misc]
