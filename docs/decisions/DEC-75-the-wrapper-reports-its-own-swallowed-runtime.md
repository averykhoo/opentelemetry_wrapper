---
type: Decision
id: DEC-75
title: 'The wrapper reports its own swallowed runtime failures: one stderr JSON line per site, tracebacks opt-in'
actor: owner
decided: 2026-10-18
session: 2026-10-18e
decision_status: PROVISIONAL
answers: ASK-19
body_sha: sha256:feb41abd21d370f7f0c8a934310176b2af1883368dadb9adb0a02a73f336afd4
relaxes: [DEC-49]
tasks: [OTW-3]
---

Owner, answering ASK-19: *"Owner, 2026-10-18e, answering ASK-19 (may the wrapper report its own runtime failures, to debug it, and how). The agent's recommendation: when the wrapper swallows one of its own exceptions at runtime, it writes one line of JSON to stderr, once per failure site (the exception type plus our code location), directly and inside its own try/except, never through `warnings` or `logging`; an opt-in env var (e.g. `OTEL_WRAPPER_DEBUG=1`) adds the traceback and reports every occurrence. Verbatim: *"Okay with your recommendations on writing our own errors"*

This relaxes G-4 and DEC-49 by one bounded channel. Startup warnings are unchanged: `OtelWrapperWarning` through `warnings.warn`, startup paths only. At runtime, a swallowed internal failure is the one thing the wrapper may write, as above. It still emits no spans or logs of its own. The env var's final name is OTW-3's to settle, under DEC-59's naming."*
