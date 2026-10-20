import logging
from dataclasses import dataclass
from functools import lru_cache

from opentelemetry_wrapper import otel

if __name__ == '__main__':
    # spans on stdout (v1 exports nothing unless told to), logs as one line of json each on stderr
    otel.configure(traces_exporter='console')

    # v0's `instrument_dataclasses()` instrumented every dataclass; v1 decorates the class (DEC-42), and properties
    # only when asked (v0 spanned them)
    @otel(properties=True)
    @dataclass  # (frozen=True)
    class A:
        x = 1

        @otel
        def __new__(cls, *args, **kwargs):
            logging.info('A.__new__')
            return super(A, cls).__new__(cls, *args, **kwargs)

        # @otel
        def __init__(self):
            logging.info('A.__init__')
            # self.y = 2

        # @otel
        def b(self):
            logging.info('A.b')
            return 1

        # @otel
        def c(self):
            logging.info('A.c')

            @otel
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


    @otel
    @lru_cache
    def f(x):
        return x + 1


    otel.instrument(logging)
    A().b()
    A().c()()
    A()()
    A().__class__
    A().e
    A().e
    A().x

    a = otel(A)()
    a_c = otel(a.c)
    a_c_d = otel(a_c())
    a_c_d()

    with otel(A)():
        ...
