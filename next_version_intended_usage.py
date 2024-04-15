import logging
from dataclasses import dataclass
from uuid import uuid4

from fastapi import FastAPI

_MISSING = object()

from types import ModuleType

class PrototypeAutoInstrument:
    def __init__(self, **kwargs):
        self.spans = []
        self.blocked = False
        self.kwargs = kwargs
        if '' in self.kwargs:
            self.blocked = self.kwargs.pop('')

    def __call__(self, thing=_MISSING, /, **kwargs):
        # TODO: consider using `@functools.singledispatch` to split up this function
        if thing is _MISSING and not kwargs:
            print('WARNING!!! empty call pls stop')
            return self
        if self.kwargs and kwargs:
            print('WARNING!!! you should not need to send kwargs multiple times pls stop')

        # support adding kwargs multiple times anyway
        new_kwargs = self.kwargs.copy()  # should it be an error to update kwargs?
        new_kwargs.update(kwargs)

        # instrument
        if thing is not _MISSING:
            if self.blocked:
                print('WARNING!!! already used, should not instrument')
            if isinstance(thing, ModuleType):
                print(f'instrumented module={thing}, {new_kwargs=}')
            elif isinstance(thing, FastAPI):
                print(f'instrumented FastAPI={thing}, {new_kwargs=}')
            elif isinstance(thing, type):
                print(f'instrumented class={thing}, {new_kwargs=}')
            else:
                print(f'instrumented {thing=}, {new_kwargs=}')
            if self.kwargs:
                self.blocked = True
            return thing

        # just update kwargs
        if self.blocked:
            print('WARNING!!! already used, should not update kwargs')
        new_kwargs[''] = self.blocked
        return PrototypeAutoInstrument(**new_kwargs)

    def __enter__(self):
        if self.blocked:
            print('WARNING!!! should not span')
        self.spans.append(uuid4())
        print(f'(span start) {self.spans[-1]} {self.kwargs=}')
        if self.kwargs:
            self.blocked = True
        return self.spans[-1]

    def __exit__(self, exc_type, exc_val, exc_tb):
        print(f'(span end) {self.spans[-1]} {self.kwargs=}')
        self.spans.pop()


otel = PrototypeAutoInstrument()

if __name__ == '__main__':
    # instrumenting a class looks like this
    @otel
    class SomeClass:
        pass


    # instrumenting a dataclass is the same
    @otel(some_kwarg='some_value')
    @dataclass
    class SomeOtherClass:
        pass


    # instrumenting a function uses the same @otel decorator
    @otel(asdf=1)
    def some_function():
        return SomeClass()


    # instrumenting a FastAPI app requires some auto-detection
    app = otel(FastAPI())

    # instrumenting the logging module will look like this
    otel(logging, some_bool=True)

    # to instrument a span of code, it can be used as a context manager
    with otel:
        print(1)

        # the context manager can be nested and used with arguments
        with otel(sampling=0.5):
            print(2)

            # idk why you need the span, but if there's a use case, we can return the span / span
            with otel as span:
                print(3, span)

            print(4)
        print(5)

    # just for testing
    print(6)
    with otel(sampling=0.5, asdf=2):
        print(7)
        with otel:
            print(8)

        print(9)
    print(10)
