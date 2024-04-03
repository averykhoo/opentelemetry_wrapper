import logging
from dataclasses import dataclass
from uuid import uuid4

from fastapi import FastAPI

_MISSING = object()


class PrototypeAutoInstrument:
    def __init__(self, **kwargs):
        self.spans = []
        self.blocked = False
        self.kwargs = kwargs
        if '' in self.kwargs:
            self.blocked = self.kwargs.pop('')

    def __call__(self, thing=_MISSING, /, **kwargs):
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
    @otel
    class SomeClass:
        pass


    @otel(some_kwarg='some_value')  # this creates a new instance
    @dataclass
    class SomeOtherClass:
        pass


    @otel(asdf=1)
    def some_function():
        pass


    app = otel(FastAPI())

    otel(logging, some_bool=True)

    with otel:
        print(1)
        with otel(sampling=0.5):
            print(2)
            with otel as span_id:
                print(3, span_id)

            print(4)
        print(5)

    print(6)
    with otel(sampling=0.5, asdf=2):
        print(7)
        with otel:
            print(8)

        print(9)
    print(10)
