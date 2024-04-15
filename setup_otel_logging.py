import logging
from functools import lru_cache

from opentelemetry_wrapper import instrument_dataclasses
from opentelemetry_wrapper import instrument_decorate
from opentelemetry_wrapper import instrument_logging

if __name__ == '__main__':
    instrument_dataclasses()
    from dataclasses import dataclass


    @dataclass  # (frozen=True)
    class A:
        x = 1

        @instrument_decorate
        def __new__(cls, *args, **kwargs):
            logging.info('A.__new__')
            return super(A, cls).__new__(cls, *args, **kwargs)

        # @instrument_decorate
        def __init__(self):
            logging.info('A.__init__')
            # self.y = 2

        # @instrument_decorate
        def b(self):
            logging.info('A.b')
            return 1

        # @instrument_decorate
        def c(self):
            logging.info('A.c')

            @instrument_decorate
            def d():
                logging.info('A.c.d')
                return 1

            return d

        def __call__(self, *args, **kwargs):
            logging.info('A.call')
            return

        @property
        def e(self):
            logging.info('A.e')
            return 1

        @e.setter
        def e(self, value):
            return

        def __enter__(self):
            pass

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass


    @instrument_decorate
    @lru_cache
    def f(x):
        return x + 1


    instrument_logging()
    A().b()
    A().c()()
    A()()
    A().__class__
    A().e
    A().e
    A().x

    a = instrument_decorate(A)()
    a_c = instrument_decorate(a.c)
    a_c_d = instrument_decorate(a_c())
    a_c_d()

    with instrument_decorate(A)():
        ...
