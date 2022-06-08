import sys
import traceback


def f(x):
    print(x / 0.0)


class A:

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        print('exc_type=', exc_type)
        print('exc_val=', exc_val)
        print('exc_tb=', exc_tb)


if __name__ == '__main__':
    try:
        f(1)
    except Exception as e:
        # exc_type, exc_val, exc_tb = sys.exc_info()
        # print('exc_type=', exc_type)
        # print('exc_val=', exc_val)
        # print('exc_tb=', exc_tb)
        # # traceback.print_tb(exc_tb)
        # traceback.print_stack(f=traceback.extract_stack())
        # tbe = traceback.TracebackException(*sys.exc_info(), capture_locals=True)
        # print(list(tbe.format_exception_only()))
        print(str(type(e).__name__))
        print(str(e))
        print(''.join(traceback.format_tb(e.__traceback__)))

    # with A():
    #     f(1)
