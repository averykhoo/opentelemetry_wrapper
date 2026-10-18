---
type: Decision
id: DEC-53
title: Classes span methods and constructors, selected dunders, `@otel.ignore`; `attributes` as a dict (proposal 11)
actor: owner + agent
decided: 2026-10-08
session: 2026-10-18a
decision_status: PROVISIONAL
relaxes: [DEC-68]
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:838ebe3b8860cb1e6078c9cfb3efbb7d1954549e3d1c33fefd961471e9f6352f
tags: [api]
---

11. **Smaller points** (F12):
    - instrumenting a class spans methods and constructors by default, properties opt-in
      (`@otel(properties=True)`), since a property read in a loop is the noisiest thing in the library;
    - *(review)* dunders: only `__new__`, `__init__`, `__post_init__`, `__call__`, `__enter__`/`__exit__` (and async
      versions). Never `__repr__`, `__eq__`, `__hash__` etc.: they're noisy and can recurse (a span attribute that
      calls `repr(self)`);
    - *(review)* a per-method opt-out for hot methods inside an instrumented class, e.g. `@otel.ignore`;
    - document the standard sampler variables (`OTEL_TRACES_SAMPLER=parentbased_traceidratio` +
      `OTEL_TRACES_SAMPLER_ARG=0.1` for 10%);
    - `attributes={...}` as a dict (not `**kwargs`), so it can't collide with options.

*Imported at adoption (2026-10-18) from `PLAN.md` § Proposals, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
