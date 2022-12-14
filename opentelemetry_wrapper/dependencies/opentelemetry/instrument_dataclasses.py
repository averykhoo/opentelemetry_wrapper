import dataclasses
import inspect
from functools import wraps

from opentelemetry_wrapper.config.config import OTEL_WRAPPER_DISABLED
from opentelemetry_wrapper.dependencies.opentelemetry.instrument_decorator import instrument_decorate

_ORIGINAL = None


@instrument_decorate
def instrument_dataclasses() -> None:
    """
    magical way to auto-instrument all dataclasses created using the @dataclass decorator
    note that this MUST be called **before** any code imports dataclasses.dataclass
    this function is idempotent; calling it multiple times has no additional side effects
    """

    # no-op
    if OTEL_WRAPPER_DISABLED:
        return

    global _ORIGINAL
    if _ORIGINAL is None:
        _ORIGINAL = dataclasses.dataclass

        @wraps(dataclasses.dataclass)
        def wrapped(*args, **kwargs):
            dataclass_or_wrap = _ORIGINAL(*args, **kwargs)
            if inspect.isclass(dataclass_or_wrap):
                return instrument_decorate(dataclass_or_wrap)
            else:
                @wraps(dataclass_or_wrap)
                def double_wrap(*_args, **_kwargs):
                    return instrument_decorate(dataclass_or_wrap(*_args, **_kwargs))

                return double_wrap

        dataclasses.dataclass = wrapped
