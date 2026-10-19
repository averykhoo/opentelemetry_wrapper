---
type: Decision
id: DEC-22
title: 'Generators and context managers: one span each, as prototyped'
actor: owner
decided: 2026-10-08
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:b85aa37051a4508455c87baa61098abb8e2c732d875219c141d6f3c1736a0353
tags: [api]
tasks: [OTW-10]
---

- **Generators and context managers** as in workstream 7 (author approved the prototype).

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

*Imported at adoption (2026-10-18) from `PLAN.md` § Decided, `PLAN.md` § Workstreams § 7. Generators and context managers, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*

## Amendments

- **2026-10-19a (claude-code/2.1.287):** 2026-10-19 (session 2026-10-19a). The session asked the owner (multiple choice): "DEC-22 asks for two things that can't both hold for @otel on a generator function: the span parented where the generator is *created*, and the wrapper itself being a generator function, which FastAPI yield dependencies and pytest yield fixtures need. Calling a generator function runs none of its code, so the creation context can't be captured. Which wins?" The owner chose, verbatim:

  > Keep generator fn (Recommended)

  whose option read: "As built: FastAPI and pytest work, and the span is parented where the first next() runs. DEC-22 gets an amendment, and the strict xfail for creation-time parenting is deleted."
