"""
v1's `with otel:` blocks (DEC-47, DEC-20, DEC-50), the escape hatches (DEC-45) and the disabled mode (DEC-24, DEC-5)
"""
from tests.v0._harness import scenario
from tests.v1._prelude import PRELUDE

BLOCKS = scenario(__name__, 'v1_with_blocks', PRELUDE + r'''
import asyncio
from opentelemetry import trace

def load_config():
    with otel as span:
        inside = otel.span_id == format(span.get_span_context().span_id, '016x')
        current = trace.get_current_span() is span
    return inside and current

emit('current_inside', load_config())
with otel:
    pass
with otel():
    pass
with otel('named', attributes={'k': 'v'}) as span:
    span.set_attribute('count', 3)

async def main():
    async with otel('async block'):
        @otel
        def child():
            pass
        child()

asyncio.run(main())
spans = take(exporter)
emit('names', sorted(s['name'] for s in spans))  # sorted: start times can tie on Windows' clock
by_name = {s['name']: s for s in spans}
emit('named_attributes', by_name['named']['attributes'])
emit('line', [by_name['__main__.load_config']['attributes']['code.line.number'],
              by_name['__main__.<module>']['attributes']['code.line.number']])
emit('child_parent', by_name['__main__.main.<locals>.child']['parent'])

def two_blocks():
    with otel:
        pass
    with otel:
        pass

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    two_blocks(); two_blocks()
    emit('two_blocks_warnings', otel_warnings(caught))
take(exporter)

# DEC-20: two tasks share the module-level `otel`; A enters first and exits first
async def task(name, enter_after, exit_after, ids):
    await asyncio.sleep(enter_after)
    with otel(name) as span:
        ids[name] = format(span.get_span_context().span_id, '016x')
        await asyncio.sleep(exit_after)
        ids[name + ' current at exit'] = otel.span_id

async def race():
    ids = {}
    await asyncio.gather(task('A', 0, 0.02, ids), task('B', 0.01, 0.03, ids))
    return ids

with otel('outer') as outer:
    with otel('inner'):
        pass
    emit('nested_current_after_inner', otel.span is outer)
emit('nested', {s['name']: s['parent'] for s in take(exporter)})

ids = asyncio.run(race())
emit('race_ids', ids)
emit('race_end_order', [s.name for s in sorted(exporter.get_finished_spans(), key=lambda s: s.end_time)])
emit('race_spans', {s['name']: [s['span_id'][2:], s['parent']] for s in take(exporter)})
''')


def test_with_otel_opens_a_span_that_is_current_inside_the_block():  # AC-2
    assert BLOCKS.result()['current_inside'] is True


def test_unnamed_blocks_are_named_after_the_enclosing_function_never_a_line():  # AC-2 (DEC-47, DEC-50)
    result = BLOCKS.result()
    assert result['names'] == sorted(['__main__.load_config', '__main__.<module>', '__main__.<module>', 'named',
                                      'async block', '__main__.main.<locals>.child'])
    assert all(isinstance(line, int) and line > 0 for line in result['line'])
    assert result['named_attributes'] == {'k': 'v', 'count': 3}
    assert result['child_parent'] == 'async block'


def test_two_unnamed_blocks_in_one_function_warn_once():  # AC-2 (DEC-47), AC-22
    warnings = BLOCKS.result()['two_blocks_warnings']
    assert len(warnings) == 1 and 'two_blocks' in warnings[0]


def test_nested_blocks_close_innermost_first():  # AC-2 (DEC-20)
    result = BLOCKS.result()
    assert result['nested'] == {'inner': 'outer', 'outer': None}
    assert result['nested_current_after_inner'] is True


def test_concurrent_tasks_never_close_each_others_spans():  # AC-2 (DEC-20)
    result = BLOCKS.result()
    ids, spans = result['race_ids'], result['race_spans']
    assert ids['A current at exit'] == ids['A'] and ids['B current at exit'] == ids['B']
    assert spans == {'A': [ids['A'], None], 'B': [ids['B'], None]}
    assert result['race_end_order'] == ['A', 'B']  # A's exit ends A's span, not B's (the shared-stack bug)


HATCHES = scenario(__name__, 'v1_with_escape_hatches', PRELUDE + r'''
from opentelemetry import trace
emit('outside', [otel.span is trace.INVALID_SPAN, otel.trace_id, otel.span_id])
with otel('x') as span:
    context = span.get_span_context()
    emit('inside', [otel.span is span, otel.trace_id == format(context.trace_id, '032x'),
                    otel.span_id == format(context.span_id, '016x'), len(otel.trace_id), len(otel.span_id)])
''')


def test_span_is_never_none_and_ids_are_hex_strings():  # AC-26 (DEC-45)
    result = HATCHES.result()
    assert result['outside'] == [True, '0' * 32, '0' * 16]
    assert result['inside'] == [True, True, True, 32, 16]


_DISABLED = PRELUDE + r'''
import asyncio
from opentelemetry import trace

def f(x):
    return x

async def af():
    return 1

emit('unchanged', [otel(f) is f, otel(af) is af, otel(name='n')(f) is f])
with otel as span:
    emit('invalid_span', [span is trace.INVALID_SPAN, otel.trace_id, otel.span_id])

def raises():
    raise KeyError('k')

try:
    with otel('x'):
        raises()
except KeyError as e:
    emit('propagated', [type(e).__name__, e.__traceback__.tb_next is not None])
emit('configured', _config.is_configured())
emit('spans', len(exporter.get_finished_spans()))
'''
DISABLED = scenario(__name__, 'v1_with_disabled', _DISABLED, env={'OTEL_WRAPPER_DISABLED': 'true'})
SDK_DISABLED = scenario(__name__, 'v1_with_sdk_disabled', _DISABLED, env={'OTEL_SDK_DISABLED': 'true'})

DISABLED_LATER = scenario(__name__, 'v1_with_disabled_later', PRELUDE + r'''
import os

@otel
def f():
    return 1

f()
os.environ['OTEL_WRAPPER_DISABLED'] = 'true'  # e.g. a test that sets it after import
f()
with otel('x'):
    pass
emit('spans', [s['name'] for s in take(exporter)])
''')


def test_disabled_decorators_return_the_target_and_blocks_yield_the_invalid_span():  # AC-4 (DEC-24, DEC-5)
    for scenario_ in (DISABLED, SDK_DISABLED):
        result = scenario_.result()
        assert result['unchanged'] == [True, True, True]
        assert result['invalid_span'] == [True, '0' * 32, '0' * 16]
        assert result['propagated'] == ['KeyError', True]
        assert result['configured'] is False
        assert result['spans'] == 0


def test_existing_wrappers_check_the_disabled_switch_at_call_time():  # AC-4 (DEC-24)
    assert DISABLED_LATER.result()['spans'] == ['__main__.f']
