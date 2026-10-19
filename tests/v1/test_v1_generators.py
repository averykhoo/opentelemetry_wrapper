"""
v1's `@otel` on generators, async generators and `@contextmanager` functions (OTW-10, DEC-22, AC-17)

each scenario runs in a fresh interpreter (global OTel state can't be reset). The wrapper of a generator function is a
generator function, so `send`, `throw` and `close` reach the target and FastAPI / pytest still see a `yield`
"""
import pytest
from tests.v0._harness import ASGI_HELPER_SOURCE
from tests.v0._harness import scenario
from tests.v1._prelude import PRELUDE as BASE_PRELUDE



def by_name(spans, suffix):
    return [s for s in spans if s['name'].endswith(suffix)]


PRELUDE = ASGI_HELPER_SOURCE + BASE_PRELUDE + r'''
import asyncio, contextlib, inspect, time, gc


@otel
def leaf():
    return 1


@otel
def consumer_step():
    return 2
'''

# ----------------------------------------------------------------------------------------------------------------------
# case 1: a generator's span: current only while its body runs, wall time vs active time, yield count
# ----------------------------------------------------------------------------------------------------------------------

BASIC = scenario(__name__, 'v1_generators_basic', PRELUDE + r'''
@otel
def numbers(n):
    for i in range(n):
        time.sleep(0.02)  # the body's own time
        leaf()
        yield i


@otel
def outer():
    out = []
    for value in numbers(3):
        consumer_step()  # between iterations: the generator's span must not be current
        time.sleep(0.05)
        out.append(value)
    return out


emit('result', outer())
finished = {s.name: s for s in exporter.get_finished_spans()}
gen = finished['__main__.numbers']
emit('wall', (gen.end_time - gen.start_time) / 1e9)
emit('spans', take(exporter))
''')


@pytest.mark.criterion('AC-17')
def test_a_generator_span_is_current_only_while_its_body_runs():
    result = BASIC.result()
    assert result['result'] == [0, 1, 2]
    spans = result['spans']
    assert [s['parent'] for s in by_name(spans, 'leaf')] == ['__main__.numbers'] * 3
    assert [s['parent'] for s in by_name(spans, 'consumer_step')] == ['__main__.outer'] * 3
    (gen,) = by_name(spans, 'numbers')
    assert gen['parent'] == '__main__.outer' and gen['status'] == 'OK'


@pytest.mark.criterion('AC-17')
def test_a_generator_span_records_yield_count_and_active_time_beside_wall_time():
    result = BASIC.result()
    (gen,) = by_name(result['spans'], 'numbers')
    attributes = gen['attributes']
    assert attributes['opentelemetry_wrapper.yields'] == 3
    active = attributes['opentelemetry_wrapper.active_seconds']
    assert 0.05 <= active < result['wall'] - 0.1  # the consumer's 3 x 50 ms is suspended time
    assert result['wall'] >= 0.2  # wall-clock duration includes time suspended


# ----------------------------------------------------------------------------------------------------------------------
# case 2: send, throw, close, return value, exceptions, early close: forwarded exactly, the span ended exactly once
# ----------------------------------------------------------------------------------------------------------------------

PROTOCOL = scenario(__name__, 'v1_generators_protocol', PRELUDE + r'''
def source(trail):
    got = []
    try:
        while True:
            try:
                got.append((yield len(got)))
            except KeyError:
                got.append('caught')
    finally:
        leaf()  # a span made while closing
        trail.append(list(got) + ['closed'])


def drive(factory):
    trail = []
    gen = factory(trail)
    out = [next(gen), gen.send('a'), gen.throw(KeyError()), gen.send('b')]
    gen.close()
    return out, trail


plain = drive(source)
exporter.clear()
through = drive(otel(source))
emit('plain', plain)
emit('same', plain == through)
emit('protocol_spans', take(exporter))


@otel
def returns(n):
    yield n
    return 'done'


def delegating():
    got = yield from returns(1)
    yield got


emit('return_value', list(delegating()))
exporter.clear()


@otel
def breaks():
    yield 1
    yield 2


for value in breaks():
    break
gc.collect()  # CPython closes the abandoned generator at once; this is for other implementations
emit('break_spans', take(exporter))


@otel
def explodes():
    yield 1
    raise ValueError('boom')


try:
    list(explodes())
except ValueError:
    emit('raised', True)
emit('error_spans', take(exporter))


@otel
def uncaught():
    yield 1


gen = uncaught()
next(gen)
try:
    gen.throw(KeyError('thrown'))
except KeyError:
    emit('thrown_through', True)
emit('thrown_spans', take(exporter))

never_started = breaks()
never_started.close()
del never_started
emit('never_started_spans', take(exporter))
emit('is_gen', [inspect.isgeneratorfunction(otel(source)), inspect.isgeneratorfunction(breaks)])
''')


@pytest.mark.criterion('AC-17')
def test_send_throw_and_close_reach_the_target_exactly_as_without_the_wrapper():
    result = PROTOCOL.result()
    assert result['plain'] == [[0, 1, 2, 3], [['a', 'caught', 'b', 'closed']]]
    assert result['same'] is True
    assert result['return_value'] == [1, 'done']
    assert result['is_gen'] == [True, True]


@pytest.mark.criterion('AC-17')
def test_a_generator_closed_early_ends_its_span_once_with_closed_early_and_no_error():
    result = PROTOCOL.result()
    protocol = result['protocol_spans']
    (gen,) = by_name(protocol, 'source')
    assert gen['attributes']['opentelemetry_wrapper.closed_early'] is True
    assert gen['status'] == 'UNSET' and gen['attributes']['opentelemetry_wrapper.yields'] == 4
    assert by_name(protocol, 'leaf')[0]['parent'] == '__main__.source'  # the body's finally runs under its span
    (broken,) = by_name(result['break_spans'], 'breaks')  # a `break`, then the generator is dropped
    assert broken['attributes']['opentelemetry_wrapper.closed_early'] is True and broken['status'] == 'UNSET'


@pytest.mark.criterion('AC-17')
def test_a_generator_that_raises_ends_its_span_once_with_error_and_the_exception_reaches_the_consumer():
    result = PROTOCOL.result()
    assert result['raised'] is True and result['thrown_through'] is True
    (exploded,) = by_name(result['error_spans'], 'explodes')
    assert exploded['status'] == 'ERROR' and exploded['attributes']['error.type'] == 'ValueError'
    (thrown,) = by_name(result['thrown_spans'], 'uncaught')
    assert thrown['status'] == 'ERROR' and thrown['attributes']['error.type'] == 'KeyError'


@pytest.mark.criterion('AC-17')
def test_a_generator_never_started_makes_no_span():
    assert PROTOCOL.result()['never_started_spans'] == []


# ----------------------------------------------------------------------------------------------------------------------
# the residual: parented where the generator is first advanced, not where it was created
# ----------------------------------------------------------------------------------------------------------------------

CREATED_ELSEWHERE = scenario(__name__, 'v1_generators_created_elsewhere', PRELUDE + r'''
@otel
def numbers():
    yield 1


@otel
def creator():
    return numbers()  # created here, consumed after `creator` has ended


gen = creator()
list(gen)
emit('spans', take(exporter))
''')


@pytest.mark.xfail(strict=True, reason='DEC-22: a generator function wrapper is itself a generator function, so '
                                       'nothing runs at creation: the span is parented at the first next() (OTW-10)')
def test_a_generator_is_parented_where_it_was_created():
    (gen,) = by_name(CREATED_ELSEWHERE.result()['spans'], 'numbers')
    assert gen['parent'] == '__main__.creator'


# ----------------------------------------------------------------------------------------------------------------------
# case 3: async generators
# ----------------------------------------------------------------------------------------------------------------------

ASYNC = scenario(__name__, 'v1_generators_async', PRELUDE + r'''
async def source(trail):
    got = []
    try:
        while True:
            try:
                got.append((yield len(got)))
            except KeyError:
                got.append('caught')
    finally:
        leaf()
        trail.append(list(got) + ['closed'])


async def drive(factory):
    trail = []
    agen = factory(trail)
    out = [await agen.asend(None), await agen.asend('a'), await agen.athrow(KeyError()), await agen.asend('b')]
    await agen.aclose()
    return out, trail


@otel
async def counted(n):
    for i in range(n):
        await asyncio.sleep(0.01)
        leaf()
        yield i


@otel
async def outer():
    out = []
    async for value in counted(2):
        consumer_step()
        out.append(value)
    return out


@otel
async def raises():
    yield 1
    raise ValueError('boom')


@otel
async def abandoned():
    yield 1
    yield 2


async def main():
    plain = await drive(source)
    exporter.clear()
    through = await drive(otel(source))
    emit('plain', plain)
    emit('same', plain == through)
    emit('protocol_spans', take(exporter))
    emit('outer', await outer())
    emit('counted_spans', take(exporter))
    try:
        async for _ in raises():
            pass
    except ValueError:
        emit('raised', True)
    emit('error_spans', take(exporter))
    async for _ in abandoned():
        break  # left suspended: the loop's finalizer hook schedules `aclose()`
    await asyncio.sleep(0)
    emit('is_asyncgen', inspect.isasyncgenfunction(otel(source)))


asyncio.run(main())
emit('abandoned_spans', take(exporter))
''')


@pytest.mark.criterion('AC-17')
def test_an_async_generator_forwards_asend_athrow_and_aclose_and_ends_its_span_once():
    result = ASYNC.result()
    assert result['plain'] == [[0, 1, 2, 3], [['a', 'caught', 'b', 'closed']]]
    assert result['same'] is True and result['is_asyncgen'] is True
    (gen,) = by_name(result['protocol_spans'], 'source')
    assert gen['attributes']['opentelemetry_wrapper.closed_early'] is True and gen['status'] == 'UNSET'
    assert by_name(result['protocol_spans'], 'leaf')[0]['parent'] == '__main__.source'


@pytest.mark.criterion('AC-17')
def test_an_async_generator_span_is_current_only_while_its_body_runs_and_counts_yields():
    result = ASYNC.result()
    assert result['outer'] == [0, 1]
    spans = result['counted_spans']
    assert [s['parent'] for s in by_name(spans, 'leaf')] == ['__main__.counted'] * 2
    assert [s['parent'] for s in by_name(spans, 'consumer_step')] == ['__main__.outer'] * 2
    (gen,) = by_name(spans, 'counted')
    assert gen['parent'] == '__main__.outer' and gen['status'] == 'OK'
    assert gen['attributes']['opentelemetry_wrapper.yields'] == 2
    assert gen['attributes']['opentelemetry_wrapper.active_seconds'] >= 0.02


@pytest.mark.criterion('AC-17')
def test_an_async_generator_that_raises_or_is_abandoned_ends_its_span_once():
    result = ASYNC.result()
    (exploded,) = by_name(result['error_spans'], 'raises')
    assert exploded['status'] == 'ERROR' and exploded['attributes']['error.type'] == 'ValueError'
    (left,) = by_name(result['abandoned_spans'], 'abandoned')
    assert left['attributes']['opentelemetry_wrapper.closed_early'] is True


# ----------------------------------------------------------------------------------------------------------------------
# case 4: @contextmanager / @asynccontextmanager, in either decorator order
# ----------------------------------------------------------------------------------------------------------------------

MANAGERS = scenario(__name__, 'v1_generators_context_managers', PRELUDE + r'''
@otel
def body():
    time.sleep(0.05)


def make(order):
    def managed(arg=1, *, key=None):
        """doc"""
        leaf()
        try:
            yield 'value'
        finally:
            consumer_step()
    if order == 'on_top':
        return otel(contextlib.contextmanager(managed))
    return contextlib.contextmanager(otel(managed))


top = make('on_top')
emit('kinds', [inspect.isgeneratorfunction(top), top.__name__, top.__doc__,
               str(inspect.signature(top)) == str(inspect.signature(top.__wrapped__)),
               inspect.isgeneratorfunction(top.__wrapped__.__wrapped__), otel(top) is top])

with top() as value:
    body()
emit('value', value)
emit('on_top', take(exporter))

try:
    with top():
        raise KeyError('in body')
except KeyError:
    emit('propagated', True)
emit('on_top_error', take(exporter))


@otel
@contextlib.contextmanager
def suppressing():
    try:
        yield
    except KeyError:
        pass


with suppressing():
    raise KeyError('swallowed')
emit('suppressed', take(exporter))

with make('underneath')():
    body()
emit('underneath', take(exporter))


class Holder:
    @otel
    @contextlib.contextmanager
    def method(self):
        yield self


with Holder().method() as held:
    body()
emit('method', [type(held).__name__, take(exporter)])


@otel
@contextlib.asynccontextmanager
async def amanaged():
    leaf()
    yield 'avalue'


@otel
async def abody():
    await asyncio.sleep(0.05)


async def main():
    emit('akinds', [inspect.isasyncgenfunction(amanaged), otel(amanaged) is amanaged])
    async with amanaged() as avalue:
        await abody()
    emit('avalue', avalue)
    emit('async_spans', take(exporter))
    try:
        async with amanaged():
            raise KeyError('in body')
    except KeyError:
        emit('apropagated', True)
    emit('async_error', take(exporter))


asyncio.run(main())
''')


@pytest.mark.criterion('AC-17')
def test_otel_over_contextmanager_covers_enter_body_exit_with_the_body_a_child():
    result = MANAGERS.result()
    assert result['value'] == 'value'
    spans = result['on_top']
    (managed,) = by_name(spans, 'managed')
    assert managed['parent'] is None and managed['status'] == 'OK'
    assert managed['attributes']['code.function.name'] == '__main__.make.<locals>.managed'
    assert 'contextlib' not in managed['attributes']['code.file.path']
    assert by_name(spans, 'body')[0]['parent'] == managed['name']
    assert by_name(spans, 'leaf')[0]['parent'] == managed['name']  # entering
    assert by_name(spans, 'consumer_step')[0]['parent'] == managed['name']  # exiting


@pytest.mark.criterion('AC-17')
def test_the_context_manager_wrapper_keeps_kind_signature_and_is_idempotent():
    assert MANAGERS.result()['kinds'] == [False, 'managed', 'doc', True, True, True]


@pytest.mark.criterion('AC-17')
def test_a_context_manager_span_takes_status_from_the_body_exception_and_a_suppressed_one_is_ok():
    result = MANAGERS.result()
    assert result['propagated'] is True
    (errored,) = by_name(result['on_top_error'], 'managed')
    assert errored['status'] == 'ERROR' and errored['attributes']['error.type'] == 'KeyError'
    (suppressed,) = by_name(result['suppressed'], 'suppressing')
    assert suppressed['status'] == 'OK'


@pytest.mark.criterion('AC-17')
def test_otel_underneath_contextmanager_applies_generator_semantics_the_body_is_not_a_child():
    spans = MANAGERS.result()['underneath']
    (managed,) = by_name(spans, 'managed')
    assert managed['status'] == 'OK' and by_name(spans, 'body')[0]['parent'] is None
    assert by_name(spans, 'consumer_step')[0]['parent'] == managed['name']  # the finally still runs in the generator


@pytest.mark.criterion('AC-17')
def test_a_decorated_context_manager_method_works():
    holder, spans = MANAGERS.result()['method']
    assert holder == 'Holder'
    assert by_name(spans, 'body')[0]['parent'].endswith('Holder.method')


@pytest.mark.criterion('AC-17')
def test_otel_over_asynccontextmanager_covers_enter_body_exit_with_the_body_a_child():
    result = MANAGERS.result()
    assert result['akinds'] == [False, True] and result['avalue'] == 'avalue'
    spans = result['async_spans']
    (managed,) = by_name(spans, 'amanaged')
    assert managed['status'] == 'OK' and by_name(spans, 'abody')[0]['parent'] == managed['name']
    assert result['apropagated'] is True
    (errored,) = by_name(result['async_error'], 'amanaged')
    assert errored['status'] == 'ERROR'


# ----------------------------------------------------------------------------------------------------------------------
# the Done-when: a FastAPI `yield` dependency and a pytest `yield` fixture, decorated with `@otel`
# ----------------------------------------------------------------------------------------------------------------------

FASTAPI = scenario(__name__, 'v1_generators_fastapi', PRELUDE + r'''
from fastapi import Depends, FastAPI

events = []
app = FastAPI()


@otel
def resource():
    events.append('setup')
    yield 'the-resource'
    events.append('teardown')


@otel
async def async_resource():
    events.append('async setup')
    yield 'the-async-resource'
    events.append('async teardown')


@app.get('/use')
def use(r: str = Depends(resource), a: str = Depends(async_resource)):
    events.append('handler')
    return {'r': r, 'a': a}


response = asgi_request(app, '/use')
emit('status', response.status)
emit('body', response.text)
emit('events', events)
emit('spans', [s['name'] for s in take(exporter)])
emit('kinds', [inspect.isgeneratorfunction(resource), inspect.isasyncgenfunction(async_resource)])
''')


@pytest.mark.criterion('AC-17')
def test_a_decorated_fastapi_yield_dependency_is_a_context_manager_not_a_generator_object():
    result = FASTAPI.result()
    assert result['kinds'] == [True, True]
    assert result['status'] == 200, result['body']
    assert result['body'] == '{"r":"the-resource","a":"the-async-resource"}'
    events = result['events']
    assert sorted(events) == sorted(['setup', 'async setup', 'handler', 'teardown', 'async teardown'])
    assert events.index('handler') < events.index('teardown')
    assert {'__main__.resource', '__main__.async_resource'} <= set(result['spans'])


PYTEST_FIXTURE = scenario(__name__, 'v1_generators_pytest_fixture', PRELUDE + r'''
import pytest, tempfile, pathlib

directory = pathlib.Path(tempfile.mkdtemp())
(directory / 'test_inner.py').write_text("""
import pytest
from tests.impl import import_v1
otel = import_v1().otel
EVENTS = []

@pytest.fixture
@otel
def resource():
    EVENTS.append('setup')
    yield 'the-resource'
    EVENTS.append('teardown')

def test_uses_it(resource):
    EVENTS.append(resource)

def test_zz_events():
    assert EVENTS == ['setup', 'the-resource', 'teardown']
""")
code = pytest.main(['-q', '-p', 'no:cacheprovider', str(directory / 'test_inner.py')])
emit('exit_code', int(code))
emit('spans', take(exporter))
''')


@pytest.mark.criterion('AC-17')
def test_a_decorated_pytest_yield_fixture_gets_its_value_and_its_teardown():
    result = PYTEST_FIXTURE.result()
    assert result['exit_code'] == 0
    (fixture,) = [s for s in result['spans'] if s['name'].endswith('resource')]
    assert fixture['status'] == 'OK' and fixture['attributes']['opentelemetry_wrapper.yields'] == 1
