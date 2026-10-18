---
type: Question
id: ASK-19
title: May the wrapper report its own runtime failures (to debug it), and how?
brief: 'No runtime warnings.warn: PYTHONWARNINGS=error would crash the app (DEC-8); G-4 and DEC-49 allow only startup output'
pri: LATER
state: closed
deps: []
source: session 2026-10-18e
created: 2026-10-18
moved: 2026-10-18e
updated: 2026-10-18e
last_asked: 2026-10-18e
blocks: [OTW-3]
status: deprecated
closed: 2026-10-18e
answered: {on: 2026-10-18, session: 2026-10-18e, decision: DEC-75}
---

Owner (DEC-72): never crash is top; if all else fails, no spans. *"But I guess we also do need a way to debug the otel wrapper so maybe it should be allowed to output something if it was about to crash?"*

Today the plan swallows runtime failures silently: G-4 and DEC-49 allow `OtelWrapperWarning` only on startup paths. DEC-8 accepts a crash under `PYTHONWARNINGS=error` *only because* our warnings never fire lazily, so a runtime report must not go through `warnings.warn`. It must not go through `logging` either: that is the app's pipeline, and our own JSON handler could recurse.

**Recommendation:** when the wrapper swallows one of its own exceptions at runtime, it writes one line of JSON to stderr, once per failure site (exception type plus our code location), directly and inside its own try/except: never through `warnings` or `logging`. An opt-in env var (e.g. `OTEL_WRAPPER_DEBUG=1`) adds the traceback and reports every occurrence. This relaxes G-4 by one bounded channel, so DEC-49 gets amended.

## Log

- 2026-10-18e (claude-code/2.1.287): answered by the owner: DEC-75
