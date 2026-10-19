---
type: Task
id: OTW-10
title: 'Workstream 7: generators and context managers'
brief: a generator function's wrapper must itself be a generator function
pri: NOW
state: open
deps: [OTW-5]
source: session 2026-10-18a
created: 2026-10-18
moved: 2026-10-18l
updated: 2026-10-19a
aliases: [WS7]
labels: [v1]
---

Criteria: AC-17. Decisions: DEC-22, DEC-3.

*Workstream 7 of the v1 design, verbatim from the pre-adoption `PLAN.md` (`docs/archive/PLAN.md`); there, "workstream n" is the task aliased `WSn` (OTW-1 lists them), "Decided" / "proposal n" / "Qn" are decisions (`docs/evidence/adoption-map-2026-10-18.md`), and "`HANDOFF.md`" is the old note in `docs/evidence/history-to-2026-10-18.md`.*

Design (prototyped locally with the plain OTel tracer; all four cases behaved as described):

- **Generators**: one span from the first `next()` until exhausted, closed or garbage-collected, parented to the context
  where the generator was *created*. It is current only while the generator body runs: attach before each
  `send`/`throw`, detach before handing the value back. Forward `send`/`throw`/`close`; `GeneratorExit` ->
  `closed_early`; exceptions -> ERROR. Wall-clock duration includes time suspended, so also record yield count and
  active time (prototype: 468 ms wall, 159 ms active, 3 yields). Same for async generators with `asend`/`athrow`/`aclose`.
- **`@contextmanager` / `@asynccontextmanager` functions**: detect them regardless of decorator order. Every
  `contextmanager`-decorated function shares one `__code__` object (the `helper` closure) and exposes the generator
  function as `__wrapped__`, so `f.__code__ is contextmanager(lambda: (yield)).__code__` is a reliable check. Re-wrap as
  `contextmanager(spanned(f.__wrapped__))`: the span covers enter -> body -> exit and **stays current across the
  single yield**, so the `with` body is a child. If `@otel` sits underneath, we only see a generator function and
  apply generator semantics (correct duration, body not a child). Document "put `@otel` on top".
- **Class-based context managers** (class instrumentation): one span per `__enter__` -> `__exit__` instead of two
  method spans, current in between. Keep a per-instance stack of (span, token) (weakref-keyed, for re-entrant objects).
  If `__exit__` runs in a different context, OTel's `detach` logs instead of raising, so it never crashes.
- Caveat: abandoned generators are closed (span ended) promptly on CPython by refcounting, but only at GC on PyPy.
- The wrapper of a generator function must itself be a generator function (and of an async generator function, an
  async generator function), not a function returning a proxy object. Otherwise `inspect.isgeneratorfunction` is
  false and FastAPI injects the generator object instead of treating a `yield` dependency as a context manager;
  pytest `yield` fixtures break the same way.

**Done when:** the four prototype cases pass as tests, plus a FastAPI `yield` dependency and a pytest `yield` fixture
decorated with `@otel`.

## Traps

- Abandoned generators are closed promptly by refcounting on CPython, but only at GC on PyPy.

## Read first

- The decisions: [DEC-22](../docs/decisions/DEC-22-generators-and-context-managers-one-span-each.md), [DEC-3](../docs/decisions/DEC-3-exception-status-error-on-the-innermost-span.md); [the criteria](../docs/criteria.md)
- [v1 design evidence](../docs/evidence/v1-design-evidence-2026-10-18.md): Generators and context managers

## Log

- 2026-10-18l (claude-code/2.1.287): Stopped mid-build at the owner's request (DEC-86); WIP on branch worktree-agent-a322b3ebbf1274cd5 (c76140d), unverified: see BATON-1.
- 2026-10-19a (claude-code/2.1.287): Merged at 0668ae3 (gate 915/5/25). Code done; AC-17 stays planned: class-based context managers move to OTW-6 (strict xfail test_a_class_based_context_manager_gets_one_span_from_enter_to_exit_current_in_between), and DEC-22's creation-time parenting conflicts with 'the wrapper is a generator function' (strict xfail test_a_generator_is_parented_where_it_was_created) pending the owner.
