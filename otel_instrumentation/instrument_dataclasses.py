import dataclasses
import inspect
from functools import wraps

from otel_instrumentation.instrument_decorator import instrument_decorate


@instrument_decorate
def instrument_dataclasses():
    """
    magical way to auto-instrument all dataclasses created using the @dataclass decorator
    note that this MUST be called **before** any code imports dataclasses.dataclass
    """
    _original = dataclasses.dataclass

    @wraps(dataclasses.dataclass)
    def wrapped(*args, **kwargs):
        dataclass_or_wrap = _original(*args, **kwargs)
        if inspect.isclass(dataclass_or_wrap):
            return instrument_decorate(dataclass_or_wrap)
        else:
            @wraps(dataclass_or_wrap)
            def double_wrap(*args, **kwargs):
                return instrument_decorate(dataclass_or_wrap(*args, **kwargs))

            return double_wrap

    dataclasses.dataclass = wrapped
