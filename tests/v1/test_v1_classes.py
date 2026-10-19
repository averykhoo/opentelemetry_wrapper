"""
v1's `@otel` on classes (OTW-6, DEC-53, DEC-48): members wrapped once at decoration time, never `__getattribute__`;
selected dunders, properties opt-in, `@otel.ignore`; inherited methods; class-based context managers (DEC-22)

each scenario runs in a fresh interpreter (global OTel state can't be reset). The v0 class bugs these guard against
(first class only, two spans through instances, the leak, the source read per property access) are also pinned by
`tests/v0/test_v0_classes.py`, which passes under `OTW_IMPL=v1` (AC-11)
"""
import pytest
from tests.v0._harness import scenario
from tests.v1._prelude import PRELUDE as BASE_PRELUDE

PRELUDE = BASE_PRELUDE + r'''
import asyncio, dataclasses, functools, gc, threading, weakref
from opentelemetry_wrapper.v1 import _classes


def names():
    return [s['name'] for s in take(exporter)]


@otel
def leaf():
    return 1


@otel
def body():
    return 2
'''


def short(spans):
    return [s['name'].replace('__main__.', '') for s in spans]


# ----------------------------------------------------------------------------------------------------------------------
# what gets a span: methods, constructors, static and class methods, nested classes, selected dunders
# ----------------------------------------------------------------------------------------------------------------------

MEMBERS = scenario(__name__, 'v1_classes_members', PRELUDE + r'''
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')

    @otel
    class Shop:
        tax = 0.1
        error = ValueError  # a class it refers to, not one it defines: left alone

        def __new__(cls, *args, **kwargs):
            return super().__new__(cls)

        def __init__(self, n=0):
            self.n = n

        def buy(self):
            return self._price() * 2

        def _price(self):
            return 3

        async def abuy(self):
            return 4

        @staticmethod
        def static():
            return 5

        @classmethod
        def make(cls):
            return cls(1)

        def __call__(self):
            return 6

        def __repr__(self):
            return f'Shop({self.n})'

        def __eq__(self, other):
            return isinstance(other, Shop) and other.n == self.n

        def __hash__(self):
            return hash(self.n)

        def __len__(self):
            return self.n

        @property
        def total(self):
            return 7

        @functools.cached_property
        def cached(self):
            return 8

        @property
        @otel  # DEC-48: asked for explicitly, so it has a span even without properties=True
        def explicit(self):
            return 9

        @otel  # already ours: one span, not two
        def predecorated(self):
            return 10

        @otel.ignore
        def hot(self):
            return 11

        @staticmethod
        @otel.ignore
        def hot_static():
            return 12

        @otel.ignore
        @classmethod
        def hot_class(cls):
            return 13

        class Inner:
            def go(self):
                return 14

    @otel
    class Second:  # v0 gave method spans only to the first class it instrumented
        def method(self):
            return 15
emit('warnings', otel_warnings(caught))
emit('same_class', [otel(Shop) is Shop, otel(otel(Shop)) is Shop])
emit('getattribute', '__getattribute__' in vars(Shop))
emit('error_untouched', vars(ValueError).get(_classes.CLASS_MARK) is None)

shop = Shop();                                          emit('construct', names())
assert shop.buy() == 6;                                 emit('method', take(exporter))
assert asyncio.run(shop.abuy()) == 4;                   emit('async', names())
assert (shop.static(), Shop.static(), Shop.make().n) == (5, 5, 1); emit('static_class', names())
assert shop() == 6;                                     emit('call', names())
repr(shop); shop == shop; hash(shop); len(shop);       emit('other_dunders', names())
shop.total; shop.cached; shop.tax; shop.n;              emit('properties_and_attributes', names())
assert (shop.explicit, shop.predecorated()) == (9, 10); emit('explicit', names())
assert (shop.hot(), Shop.hot_static(), Shop.hot_class()) == (11, 12, 13); emit('ignored', names())
assert Shop.Inner().go() == 14;                         emit('nested', names())
assert Second().method() == 15;                         emit('second', names())

# no instance is kept: not by its methods, not by a `with`
used = Shop(); used.buy(); used(); used.static()
ref = weakref.ref(used)
del used
gc.collect()
emit('freed', ref() is None)
''')


@pytest.mark.criterion('AC-11')
def test_methods_constructors_static_and_class_methods_and_nested_classes_get_one_span_each():
    result = MEMBERS.result()
    assert result['warnings'] == []
    assert result['same_class'] == [True, True]
    assert short_names(result['construct']) == ['Shop.__new__', 'Shop.__init__']
    method = {s['name']: s for s in result['method']}
    assert sorted(short(method.values())) == ['Shop._price', 'Shop.buy']
    assert method['__main__.Shop._price']['parent'] == '__main__.Shop.buy'
    assert all(s['status'] == 'OK' for s in method.values())
    assert short_names(result['async']) == ['Shop.abuy']
    assert sorted(short_names(result['static_class'])) == ['Shop.__init__', 'Shop.__new__', 'Shop.make',
                                                           'Shop.static', 'Shop.static']
    assert short_names(result['call']) == ['Shop.__call__']
    assert short_names(result['nested']) == ['Shop.Inner.go']


@pytest.mark.criterion('AC-11')
def test_a_second_class_gets_method_spans_too():  # v0: only the first class instrumented in a process did
    assert short_names(MEMBERS.result()['second']) == ['Second.method']


@pytest.mark.criterion('AC-11')
def test_an_instance_is_freed_after_its_methods_were_used():  # v0 cached bound methods forever
    assert MEMBERS.result()['freed'] is True


def test_getattribute_is_never_patched_and_a_class_it_only_refers_to_is_left_alone():
    result = MEMBERS.result()
    assert result['getattribute'] is False
    assert result['error_untouched'] is True


def test_other_dunders_and_properties_get_no_span_unless_asked_for():  # DEC-53
    result = MEMBERS.result()
    assert result['other_dunders'] == []  # __repr__, __eq__, __hash__, __len__
    assert result['properties_and_attributes'] == []


@pytest.mark.criterion('AC-6')
def test_a_member_that_is_already_ours_gets_one_span():  # AC-6, DEC-48
    assert sorted(short_names(MEMBERS.result()['explicit'])) == ['Shop.explicit', 'Shop.predecorated']


def test_ignored_methods_get_no_span_whatever_the_decorator_order():  # DEC-53: `@otel.ignore`
    assert MEMBERS.result()['ignored'] == []


def short_names(names):
    return [n.replace('__main__.', '') for n in names]


# ----------------------------------------------------------------------------------------------------------------------
# properties (opt-in), names and attributes, classes without source, inheritance, disabled, unsupported
# ----------------------------------------------------------------------------------------------------------------------

OPTIONS = scenario(__name__, 'v1_classes_options', PRELUDE + r'''
@otel(properties=True)
class Account:
    def __init__(self):
        self._balance = 0

    @property
    def balance(self):
        return self._balance

    @balance.setter
    def balance(self, value):
        self._balance = value

    @functools.cached_property
    def report(self):
        return 'report'

    @property
    @otel.ignore
    def hot(self):
        return 1

account = Account(); take(exporter)
account.balance = 3
assert (account.balance, account.report, account.report, account.hot) == (3, 'report', 'report', 1)
emit('properties', names())

@otel(name='shop', attributes={'team': 'payments'})
class Named:
    def pay(self):
        return 1

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return None

with Named() as named:
    named.pay()
emit('named', [(s['name'], s['parent'], s['attributes'].get('team')) for s in take(exporter)])

namespace = {}
source = ("class NoSource:\n    def m(self):\n        return 1\n    @property\n    def p(self):\n        return 2\n")
exec(compile(source, '<generated>', 'exec'), namespace)  # like a frozen app: no source file to read
NoSource = otel(namespace['NoSource'], properties=True)
emit('no_source', [NoSource().m(), NoSource().p, [(s['name'], s['attributes'].get('code.line.number'))
                                                   for s in take(exporter)]])

class Base:
    def __init__(self):
        self.x = 1

    def shared(self):
        return 'base'

    def overridden(self):
        return 'base'

@otel
class Child(Base):
    def overridden(self):
        return super().overridden() + ' child'

assert (Base().shared(), Base().overridden()) == ('base', 'base')
emit('base_unchanged', names())
child = Child()
assert (child.shared(), child.overridden()) == ('base', 'base child')
emit('child', names())
emit('copied', sorted(k for k in ('__init__', 'shared', 'overridden') if k in vars(Child)))

@otel
class Parent:
    def __init__(self):
        pass

    def m(self):
        return 1

@otel
class Kid(Parent):
    def __init__(self):
        super().__init__()

    def n(self):
        return self.m()

Kid().n()
emit('kid', [(s['name'], s['parent']) for s in take(exporter)])
emit('kid_dict', sorted(k for k in ('__init__', 'm', 'n') if k in vars(Kid)))

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    emit('builtin_unchanged', [otel(dict) is dict, otel(int) is int])
    emit('builtin_warnings', otel_warnings(caught))
''')


@pytest.mark.criterion('AC-11')
def test_properties_get_spans_when_asked_for_and_a_cached_property_only_when_it_computes():  # DEC-53
    assert sorted(short_names(OPTIONS.result()['properties'])) == ['Account.balance', 'Account.balance',
                                                                   'Account.report']


def test_a_class_name_names_its_spans_and_its_attributes_go_on_each():
    assert sorted(OPTIONS.result()['named'], key=str) == [['shop.__enter__', None, 'payments'],
                                                          ['shop.pay', 'shop.__enter__', 'payments']]


@pytest.mark.criterion('AC-11')
def test_a_class_without_source_has_method_and_property_spans_with_lines():  # v0 read the source per property access
    m, p, spans = OPTIONS.result()['no_source']
    assert (m, p) == (1, 2)
    assert sorted(spans) == [['NoSource.m', 2], ['NoSource.p', 4]]


def test_inherited_methods_are_wrapped_into_the_subclass_and_the_base_is_unchanged():
    result = OPTIONS.result()
    assert result['base_unchanged'] == []
    assert sorted(short_names(result['child'])) == ['Base.__init__', 'Base.shared', 'Child.overridden']
    assert result['copied'] == ['__init__', 'overridden', 'shared']


@pytest.mark.criterion('AC-6')
def test_methods_inherited_from_an_instrumented_base_get_one_span_and_are_not_copied():  # AC-6
    result = OPTIONS.result()
    assert sorted([short_names([n])[0], p and short_names([p])[0]] for n, p in result['kid']) == sorted([
        ['Kid.__init__', None], ['Parent.__init__', 'Kid.__init__'], ['Kid.n', None], ['Parent.m', 'Kid.n']], key=str)
    assert result['kid_dict'] == ['__init__', 'n']


@pytest.mark.criterion('AC-7')
def test_a_built_in_class_is_returned_unchanged_with_one_warning_each():  # AC-7
    result = OPTIONS.result()
    assert result['builtin_unchanged'] == [True, True]
    assert len(result['builtin_warnings']) == 2
    assert all('built-in or extension type' in w for w in result['builtin_warnings'])


DATACLASSES = scenario(__name__, 'v1_classes_dataclasses', PRELUDE + r'''
@otel
@dataclasses.dataclass
class Point:
    x: int
    y: int = 0

    def __post_init__(self):
        self.norm = abs(self.x) + abs(self.y)

    def scaled(self, k):
        return Point(self.x * k, self.y * k)

@otel
@dataclasses.dataclass(frozen=True)
class Frozen:
    a: int

    def double(self):
        return self.a * 2

p = Point(1, 2)
constructed = [[s['name'], s['parent']] for s in take(exporter)]
emit('construct', sorted(constructed, key=lambda s: s[0].endswith('post_init__')))
q = p.scaled(2)
emit('scaled', names())
emit('behaviour', [p.norm, [q.x, q.y], Point(1, 2) == Point(1, 2), repr(Point(1)), Frozen(3).double()])
take(exporter)
try:
    Frozen(1).a = 2
except dataclasses.FrozenInstanceError:
    emit('frozen', True)
emit('frozen_spans', names())
''')


@pytest.mark.criterion('AC-6')
def test_a_dataclass_gets_constructor_post_init_and_method_spans_and_stays_a_dataclass():  # AC-6
    result = DATACLASSES.result()
    (init, init_parent), (post_init, post_init_parent) = result['construct']
    assert init.endswith('Point.__init__') and init_parent is None  # the generated `__init__`
    assert post_init == '__main__.Point.__post_init__' and post_init_parent == init
    assert sorted(n.rsplit('.', 2)[-2:] for n in result['scaled']) == [['Point', '__init__'],
                                                                       ['Point', '__post_init__'], ['Point', 'scaled']]
    assert result['behaviour'] == [3, [2, 4], True, 'Point(x=1, y=0)', 6]
    assert result['frozen'] is True
    assert [n.rsplit('.', 2)[-2:] for n in result['frozen_spans']] == [['Frozen', '__init__']]


DISABLED = scenario(__name__, 'v1_classes_disabled', r'''
import os
os.environ['OTEL_WRAPPER_DISABLED'] = 'true'
''' + PRELUDE + r'''
class Plain:
    def m(self):
        return 1

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return None

before = dict(vars(Plain))
emit('unchanged', [otel(Plain) is Plain, dict(vars(Plain)) == before])
''')


@pytest.mark.criterion('AC-4')
def test_disabled_a_class_is_returned_unchanged():  # AC-4 (DEC-24)
    assert DISABLED.result()['unchanged'] == [True, True]


# ----------------------------------------------------------------------------------------------------------------------
# class-based context managers (DEC-22): one span from `__enter__` to `__exit__`, current in between
# ----------------------------------------------------------------------------------------------------------------------

CONTEXT_MANAGERS = scenario(__name__, 'v1_classes_context_managers', PRELUDE + r'''
import logging
detach_errors = []
logging.getLogger('opentelemetry.context').addHandler(type('H', (logging.Handler,), {
    'emit': lambda self, record: detach_errors.append(record.getMessage())})())

@otel
class Resource:
    def __enter__(self):
        leaf()
        return self

    def __exit__(self, exc_type, exc, tb):
        leaf()
        return False

resource = Resource()
with resource:
    body()
    with resource:  # re-entrant
        body()
emit('reentrant', [(s['name'], s['parent'], s['status']) for s in take(exporter)])

try:
    with resource:
        raise ValueError('boom')
except ValueError:
    pass
emit('raised', [(s['name'], s['status'], s['attributes'].get('error.type')) for s in take(exporter)
                if 'Resource' in s['name']])

@otel
class Suppressing:
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return True

with Suppressing():
    raise KeyError('swallowed')
emit('suppressed', [(s['name'], s['status']) for s in take(exporter)])

@otel
class FailingEnter:
    def __enter__(self):
        raise RuntimeError('no')

    def __exit__(self, *exc_info):
        return None

failing = FailingEnter()
try:
    with failing:
        pass
except RuntimeError:
    pass
emit('failing_enter', [(s['name'], s['status']) for s in take(exporter)])
emit('failing_enter_left_open', id(failing) in _classes._stacks)  # no `__exit__` follows: nothing may wait for one

@otel
class Locked(Resource):  # overrides that call the instrumented base's: still one span per `with`
    def __enter__(self):
        return super().__enter__()

    def __exit__(self, *exc_info):
        return super().__exit__(*exc_info)

with Locked():
    body()
emit('super_chain', [(s['name'], s['parent']) for s in take(exporter)])

class PlainBase:  # not instrumented: its `__enter__` / `__exit__` are wrapped into the subclass
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return None

@otel
class FromPlainBase(PlainBase):
    pass

with FromPlainBase():
    body()
emit('from_plain_base', [(s['name'], s['parent']) for s in take(exporter)])

@otel
class Slotted:  # no `__weakref__`: kept by id until its stack is empty
    __slots__ = ()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return None

@otel
@dataclasses.dataclass
class Unhashable:  # eq=True sets `__hash__ = None`
    x: int = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return None

with Slotted(), Unhashable():
    body()
emit('slotted_unhashable', [(s['name'], s['parent']) for s in take(exporter) if not s['name'].endswith('__init__')])

# two threads inside one instance at once, the first to enter exits first: each closes its own span
shared = Resource()
entered, second_entered, first_left = threading.Event(), threading.Event(), threading.Event()
def first():
    with shared:
        entered.set(); second_entered.wait(5); body()
    first_left.set()
def second():
    entered.wait(5)
    with shared:
        second_entered.set(); first_left.wait(5); body()
threads = [threading.Thread(target=first), threading.Thread(target=second)]
[t.start() for t in threads]; [t.join() for t in threads]
finished = exporter.get_finished_spans()
by_id = {s.context.span_id: s for s in finished}
emit('threads', sorted(by_id[s.parent.span_id].name for s in finished if s.name.endswith('.body')))
emit('threads_distinct', len({s.parent.span_id for s in finished if s.name.endswith('.body')}))
take(exporter)

emit('left_open', [len(_classes._stacks), otel.span_id == '0' * 16])
ref = weakref.ref(resource)
del resource
gc.collect()
emit('freed', ref() is None)

async def main():
    @otel
    class Session:
        async def __aenter__(self):
            leaf()
            await asyncio.sleep(0)
            return self

        async def __aexit__(self, *exc_info):
            await asyncio.sleep(0)
            return None

    session = Session()
    async def task(i):
        async with session:  # one instance, two tasks inside it at once: each its own span
            await asyncio.sleep(0.01 * (2 - i))
            body()
    await asyncio.gather(task(0), task(1))

asyncio.run(main())
finished = exporter.get_finished_spans()
by_id = {s.context.span_id: s for s in finished}
def parent_name(s):
    return by_id[s.parent.span_id].name.rsplit('.', 1)[-1] if s.parent else None
emit('async', sorted((s.name.rsplit('.', 2)[-2:], parent_name(s)) for s in finished))
emit('async_distinct', len({s.parent.span_id for s in finished if s.name.endswith('.body')}))
take(exporter)
emit('detach_errors', detach_errors)
emit('async_left_open', len(_classes._stacks))
''')


@pytest.mark.criterion('AC-17')
def test_a_class_context_manager_span_covers_enter_body_and_exit_and_is_re_entrant():  # DEC-22
    spans = CONTEXT_MANAGERS.result()['reentrant']
    managers = [s for s in spans if s[0].endswith('Resource.__enter__')]
    assert sorted(str(m[1]) for m in managers) == ['None', '__main__.Resource.__enter__']  # nested
    assert all(s[2] == 'OK' for s in spans)
    children = [s for s in spans if s[0].endswith(('.leaf', '.body'))]
    assert len(children) == 6 and all(s[1] == '__main__.Resource.__enter__' for s in children)


def test_an_exception_through_the_block_is_recorded_unless_exit_suppresses_it():  # DEC-3
    result = CONTEXT_MANAGERS.result()
    assert result['raised'] == [['__main__.Resource.__enter__', 'ERROR', 'ValueError']]
    assert result['suppressed'] == [['__main__.Suppressing.__enter__', 'OK']]
    assert result['failing_enter'] == [['__main__.FailingEnter.__enter__', 'ERROR']]
    assert result['failing_enter_left_open'] is False


def test_overrides_calling_the_base_and_inherited_enter_exit_give_one_span_per_with():
    result = CONTEXT_MANAGERS.result()
    super_chain = result['super_chain']
    assert [s[0] for s in super_chain if 'Locked' in s[0] or 'Resource' in s[0]] == ['__main__.Locked.__enter__']
    assert all(s[1] == '__main__.Locked.__enter__' for s in super_chain if not s[0].endswith('__enter__'))
    assert sorted(result['from_plain_base'], key=str) == [['__main__.PlainBase.__enter__', None],
                                                          ['__main__.body', '__main__.PlainBase.__enter__']]


@pytest.mark.criterion('AC-11')
def test_instances_without_weakrefs_or_hashes_work_and_nothing_is_left_open():
    result = CONTEXT_MANAGERS.result()
    assert sorted(result['slotted_unhashable'], key=str) == [
        ['__main__.Slotted.__enter__', None], ['__main__.Unhashable.__enter__', '__main__.Slotted.__enter__'],
        ['__main__.body', '__main__.Unhashable.__enter__']]
    assert result['left_open'] == [0, True]  # no stack left, and no span left current
    assert result['freed'] is True  # nothing keeps an instance that was used in a `with`
    assert result['async_left_open'] == 0


def test_threads_and_tasks_inside_one_instance_each_close_their_own_span():
    result = CONTEXT_MANAGERS.result()
    assert result['threads'] == ['__main__.Resource.__enter__'] * 2 and result['threads_distinct'] == 2
    assert result['async_distinct'] == 2
    assert [s for s in result['async'] if s[0][-1] == 'body'] == [[['__main__', 'body'], '__aenter__']] * 2
    assert result['detach_errors'] == []  # every exit ran in the context its enter did


CROSS_CONTEXT = scenario(__name__, 'v1_classes_cross_context', PRELUDE + r'''
@otel
class Resource:
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return None

resource = Resource()
resource.__enter__()
errors = []
def exit_elsewhere():
    try:
        resource.__exit__(None, None, None)
    except BaseException as e:
        errors.append(repr(e))
thread = threading.Thread(target=exit_elsewhere)
thread.start(); thread.join()
emit('errors', errors)
emit('ended', [s['name'] for s in take(exporter)])
emit('left_open', len(_classes._stacks))
''')


def test_an_exit_in_another_context_never_crashes_and_still_ends_the_span():  # DEC-22
    result = CROSS_CONTEXT.result()
    assert result['errors'] == []
    assert result['ended'] == ['__main__.Resource.__enter__']
    assert result['left_open'] == 0
