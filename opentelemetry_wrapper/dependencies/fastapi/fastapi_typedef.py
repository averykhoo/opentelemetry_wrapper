from typing import Any

try:
    from fastapi import FastAPI


    def is_fastapi_app(item: Any) -> bool:
        return isinstance(item, FastAPI)

except ImportError:
    # noinspection PyUnusedLocal
    def is_fastapi_app(_) -> bool:
        return False
