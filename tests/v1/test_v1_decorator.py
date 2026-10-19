"""
v1's `@otel` on functions (OTW-3): spans, kinds, idempotency, never-crash, exceptions (DEC-3)

each scenario runs in a fresh interpreter (global OTel state can't be reset), so these pass under OTW_IMPL=v0 and v1
"""
import pytest
from tests.v0._harness import scenario
from tests.v1._prelude import PRELUDE

FUNCTIONS = scenario(__name__, 'v1_decorator_functions', PRELUDE + r'''
import asyncio, functools, inspect

def add(x, y=1):
    """doc"""
    return x + y

async def double(x):
    await asyncio.sleep(0)
    return x * 2

def gen(n):
    yield from range(n)

async def agen(n):
    for i in range(n):
        yield i

kinds = {}
for f in (add, double, gen, agen):
    w = otel(f)
    kinds[f.__name__] = [inspect.iscoroutinefunction(w) == inspect.iscoroutinefunction(f),
                         inspect.isgeneratorfunction(w) == inspect.isgeneratorfunction(f),
                         inspect.isasyncgenfunction(w) == inspect.isasyncgenfunction(f),
                         inspect.signature(w) == inspect.signature(f), w.__wrapped__ is f,
                         w.__name__ == f.__name__, w.__doc__ == f.__doc__]
emit('kinds', kinds)
emit('configured_by_decorating', _config.is_configured())

async def collect(agenerator):
    return [i async for i in agenerator]

emit('results', [otel(add)(1, y=2), asyncio.run(otel(double)(21)), list(otel(gen)(3)),
                 asyncio.run(collect(otel(agen)(2)))])
emit('configured_by_first_span', _config.is_configured())
emit('spans', take(exporter))

@otel()
def bare_call():
    return 1

@otel(name='price lookup', attributes={'currency': 'SGD'})
def with_options():
    return 2

bare_call(); with_options()
emit('options', take(exporter))
''')


@pytest.mark.criterion('AC-1')
def test_sync_async_and_generator_wrappers_keep_kind_and_signature():  # AC-1
    for name, checks in FUNCTIONS.result()['kinds'].items():
        assert checks == [True] * 7, name


@pytest.mark.criterion('AC-1')
def test_one_span_per_call_named_module_qualname_with_stable_code_attributes():  # AC-1
    result = FUNCTIONS.result()
    assert result['results'] == [3, 42, [0, 1, 2], [0, 1]]
    spans = result['spans']
    assert [s['name'] for s in spans] == ['__main__.add', '__main__.double', '__main__.gen', '__main__.agen']
    for s in spans:
        assert s['status'] == 'OK' and s['parent'] is None
        assert s['attributes']['code.function.name'] == s['name']
        assert s['attributes']['code.file.path'].endswith('.py')
        assert isinstance(s['attributes']['code.line.number'], int)


@pytest.mark.criterion('AC-3')
def test_decorating_configures_nothing_and_the_first_span_does():  # AC-3 (DEC-27 rule 1)
    assert FUNCTIONS.result()['configured_by_decorating'] is False
    assert FUNCTIONS.result()['configured_by_first_span'] is True


@pytest.mark.criterion('AC-1')
def test_bare_call_and_options():  # AC-1, DEC-50
    spans = FUNCTIONS.result()['options']
    assert [s['name'] for s in spans] == ['__main__.bare_call', 'price lookup']
    assert spans[1]['attributes']['currency'] == 'SGD'


NO_ARGUMENTS = scenario(__name__, 'v1_decorator_no_arguments', PRELUDE + r'''
import asyncio
otel.configure(service_name='svc')  # no configure option records arguments (none exists, by design: DEC-26)

@otel
def handler(password, *args, **kwargs):
    return 'RETURNED-SECRET'

@otel
async def ahandler(token):
    return 'RETURNED-SECRET'

handler('ARG-SECRET', 'ARG-SECRET', key='ARG-SECRET')
asyncio.run(ahandler('ARG-SECRET'))
with otel('block') as span:
    handler('ARG-SECRET')
spans = take(exporter)
emit('values', [repr(v) for s in spans for v in s['attributes'].values()] + [repr(s['name']) for s in spans])
emit('count', len(spans))
''')


@pytest.mark.criterion('AC-32')
def test_no_span_carries_arguments_or_return_values():  # AC-32 (DEC-26)
    result = NO_ARGUMENTS.result()
    assert result['count'] == 4
    assert not [v for v in result['values'] if 'SECRET' in v]


IDEMPOTENT = scenario(__name__, 'v1_decorator_idempotent', PRELUDE + r'''
import dataclasses, functools

def target():
    return 'ok'

once = otel(target)
emit('same', [otel(once) is once, otel(target) is once, otel(otel(target)) is once])
once(); emit('twice', len(take(exporter)))

cached = functools.lru_cache(once)
emit('lru_unchanged', otel(cached) is cached)
part = functools.partial(once)
emit('partial_unchanged', otel(part) is part)

class Thing:
    @otel
    def method(self):
        return 1

    @otel
    def __call__(self):
        return 2

thing = Thing()
emit('bound_unchanged', otel(thing.method)() == 1)
take(exporter)
otel(thing.method)(); thing.__call__(); thing(); otel(thing.__call__)()
emit('through_instances', [s['name'] for s in take(exporter)])

@dataclasses.dataclass
class Data:
    x: int = 0

    @otel
    def __post_init__(self):
        pass

Data(); emit('post_init', [s['name'] for s in take(exporter)])
''')


@pytest.mark.criterion('AC-6')
def test_decorating_twice_behaves_as_once():  # AC-6
    result = IDEMPOTENT.result()
    assert result['same'] == [True, True, True]
    assert result['twice'] == 1
    assert result['lru_unchanged'] is True
    assert result['partial_unchanged'] is True


@pytest.mark.criterion('AC-6')
def test_methods_reached_through_instances_call_and_post_init_give_one_span():  # AC-6
    result = IDEMPOTENT.result()
    assert result['through_instances'] == ['__main__.Thing.method'] + ['__main__.Thing.__call__'] * 3
    assert result['post_init'] == ['__main__.Data.__post_init__']


UNSUPPORTED = scenario(__name__, 'v1_decorator_unsupported', PRELUDE + r'''
import functools

def plain(a, b):
    return a * b

class Callable:
    def __call__(self, x):
        return x

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    emit('int_unchanged', otel(42) == 42)
    emit('int_warnings', otel_warnings(caught))
    caught.clear()
    emit('class_unchanged', otel(dict) is dict)  # a built-in type can't be changed (OTW-6)
    emit('class_warnings', otel_warnings(caught))
    caught.clear()
    emit('partial', otel(functools.partial(plain, 3))(5))
    emit('callable', otel(Callable())(5))
    emit('supported_warnings', len(otel_warnings(caught)))
emit('names', [s['name'] for s in take(exporter)])
''')


@pytest.mark.criterion('AC-7')
@pytest.mark.criterion('AC-22')
def test_an_unsupported_target_is_returned_unchanged_with_one_warning():  # AC-7
    result = UNSUPPORTED.result()
    assert result['int_unchanged'] is True
    assert len(result['int_warnings']) == 1 and 'not callable' in result['int_warnings'][0]
    assert result['class_unchanged'] is True
    assert len(result['class_warnings']) == 1 and 'built-in or extension type' in result['class_warnings'][0]


def test_partials_and_callable_instances_are_wrapped_without_warnings():  # AC-7, AC-10 (partly)
    result = UNSUPPORTED.result()
    assert (result['partial'], result['callable'], result['supported_warnings']) == (15, 5, 0)
    assert result['names'] == ['__main__.plain', '__main__.Callable.__call__']


_INTERNAL_FAILURE = PRELUDE + r'''
import sys
from opentelemetry_wrapper.v1 import _spans

class Broken:
    def start_span(self, *args, **kwargs):
        raise RuntimeError('tracer is broken')

@otel
def f(x):
    return x + 1

f(0)  # configure first, then break our own tracer
_spans._TRACER = Broken()
emit('results', [f(1), f(2)])
with otel('block') as span:
    emit('block_span_is_invalid', span is __import__('opentelemetry').trace.INVALID_SPAN)
'''
INTERNAL_FAILURE = scenario(__name__, 'v1_decorator_internal_failure', _INTERNAL_FAILURE,
                            env={'PYTHONWARNINGS': 'error'})
INTERNAL_FAILURE_DEBUG = scenario(__name__, 'v1_decorator_internal_failure_debug', _INTERNAL_FAILURE,
                                  env={'OTEL_WRAPPER_DEBUG': 'true'})


def _report_lines(result):
    import json
    lines = [json.loads(line) for line in result.stderr_lines if line.startswith('{"opentelemetry_wrapper"')]
    assert len(lines) == len([line for line in result.stderr_lines if 'opentelemetry_wrapper' in line]), result.stderr
    return lines


@pytest.mark.criterion('AC-7')
@pytest.mark.criterion('AC-22')
def test_a_failure_inside_the_wrapper_never_raises_and_is_reported_once_per_site():  # AC-7, AC-22 (DEC-75)
    result = INTERNAL_FAILURE.result()
    assert result['results'] == [2, 3]  # PYTHONWARNINGS=error: the report is not a warning, so it can't raise
    assert result['block_span_is_invalid'] is True
    lines = _report_lines(result)
    assert [(line['site'], line['error.type']) for line in lines] == [('span.start', 'builtins.RuntimeError')]
    assert 'traceback' not in lines[0]


@pytest.mark.criterion('AC-22')
def test_the_debug_variable_reports_every_occurrence_with_its_traceback():  # AC-22 (DEC-75)
    lines = _report_lines(INTERNAL_FAILURE_DEBUG.result())
    assert len(lines) == 3  # two calls and one block
    assert all('tracer is broken' in line['traceback'] for line in lines)


EXCEPTIONS = scenario(__name__, 'v1_decorator_exceptions', PRELUDE + r'''
import asyncio, traceback

@otel
def inner():
    raise ValueError('boom')

@otel
def outer():
    inner()

try:
    with otel('block'):
        outer()
except ValueError as e:
    tb = traceback.extract_tb(e.__traceback__)
    emit('last_frame', tb[-1].name)
    emit('marker_set', getattr(e, '__opentelemetry_wrapper_recorded__', None))
spans = exporter.get_finished_spans()
emit('error_spans', {s.name: [s.status.status_code.name, s.attributes.get('error.type'),
                              [ev.name for ev in s.events]] for s in spans})
exporter.clear()

def raiser(exc):
    @otel
    def raises():
        raise exc
    return raises

def run(exc):
    try:
        raiser(exc)()
    except BaseException as caught:
        assert caught is exc
    (span,) = exporter.get_finished_spans()
    exporter.clear()
    return [span.status.status_code.name, dict(span.attributes), [ev.name for ev in span.events]]

emit('stop', run(StopIteration()))
emit('interrupt', run(KeyboardInterrupt()))
emit('exit0', run(SystemExit(0)))
emit('exit_none', run(SystemExit()))
emit('exit2', run(SystemExit(2)))

@otel
def closable():
    yield 1
    yield 2

g = closable(); next(g); g.close()
(span,) = exporter.get_finished_spans(); exporter.clear()
emit('closed_early', [span.status.status_code.name, span.attributes.get('opentelemetry_wrapper.closed_early')])

@otel
async def sleeper():
    await asyncio.sleep(10)

async def cancel():
    task = asyncio.create_task(sleeper())
    await asyncio.sleep(0.01)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

asyncio.run(cancel())
(span,) = exporter.get_finished_spans(); exporter.clear()
emit('cancelled', [span.status.status_code.name, span.attributes.get('opentelemetry_wrapper.cancelled')])
''')


@pytest.mark.criterion('AC-25')
def test_error_on_innermost_span_with_stack_trace_and_error_type_only_outside():  # AC-25 (DEC-3)
    result = EXCEPTIONS.result()
    assert result['error_spans'] == {
        '__main__.inner': ['ERROR', 'ValueError', ['exception']],
        '__main__.outer': ['ERROR', 'ValueError', []],
        'block':          ['ERROR', 'ValueError', []],
    }
    assert result['last_frame'] == 'inner'  # re-raised untouched: the traceback still ends where it was raised
    assert result['marker_set'] is True


@pytest.mark.criterion('AC-25')
def test_control_flow_exceptions_leave_the_status_unset_with_their_markers():  # AC-25 (DEC-3)
    result = EXCEPTIONS.result()
    assert result['stop'][0] == 'UNSET' and result['stop'][2] == []
    assert result['interrupt'][0] == 'UNSET' and result['interrupt'][1]['opentelemetry_wrapper.interrupted'] is True
    assert result['closed_early'] == ['UNSET', True]
    assert result['cancelled'] == ['UNSET', True]


@pytest.mark.criterion('AC-25')
def test_system_exit_is_error_only_for_a_non_zero_code():  # AC-25 (DEC-3)
    result = EXCEPTIONS.result()
    assert result['exit0'][0] == 'UNSET' and result['exit0'][1]['process.exit.code'] == 0
    assert result['exit_none'][0] == 'UNSET' and result['exit_none'][1]['process.exit.code'] == 0
    assert result['exit2'][0] == 'ERROR' and result['exit2'][1]['process.exit.code'] == 2


# ----------------------------------------------------------------------------------------------------------------------
# review fix (OTW-3, session 2026-10-18l): disabled at call time, an async generator behaves exactly as unwrapped
# ----------------------------------------------------------------------------------------------------------------------

DISABLED_ASYNC_GENERATOR = scenario(__name__, 'v1_decorator_disabled_async_generator', PRELUDE + r'''
import asyncio, os


async def source(trail):
    got = []
    try:
        while True:
            try:
                got.append((yield len(got)))
            except KeyError:
                got.append('caught')
    finally:
        trail.append(list(got) + ['closed'])


async def drive(factory):
    trail = []
    agen = factory(trail)
    out = [await agen.asend(None), await agen.asend('a'), await agen.athrow(KeyError())]
    await agen.aclose()
    return out, trail


wrapped = otel(source)  # decorated while enabled; disabled afterwards, at call time
os.environ['OTEL_WRAPPER_DISABLED'] = 'true'
plain = asyncio.run(drive(source))
through_wrapper = asyncio.run(drive(wrapped))
emit('plain', plain)
emit('same', plain == through_wrapper)
emit('through_wrapper', through_wrapper)
emit('spans', len(exporter.get_finished_spans()))
''')


@pytest.mark.criterion('AC-4')
def test_a_disabled_async_generator_forwards_asend_athrow_and_aclose():  # AC-4 (DEC-24)
    result = DISABLED_ASYNC_GENERATOR.result()
    assert result['plain'] == [[0, 1, 2], [['a', 'caught', 'closed']]]  # what the target does by itself
    assert result['same'] is True, result['through_wrapper']
    assert result['spans'] == 0
