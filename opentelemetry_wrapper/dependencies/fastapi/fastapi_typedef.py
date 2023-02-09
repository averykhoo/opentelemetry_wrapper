from typing import Any

# note: ignore E303 too many blank lines since flak8 disagrees with pycharm
try:
    from fastapi import FastAPI


    def is_fastapi_app(item: Any) -> bool:  # noqa: E303
        return isinstance(item, FastAPI)

except ImportError:
    # noinspection PyUnusedLocal
    def is_fastapi_app(item: Any) -> bool:
        return False
