---
type: Question
id: ASK-23
title: Make the package root v1 (otel, OtelWrapperWarning) with v0's names as lazy aliases, so importing opentelemetry_wrapper no longer configures v0 at import?
brief: 'Recommendation: yes, in OTW-13: root exports otel; v0 names load lazily via module __getattr__ (DEC-46)'
pri: LATER
state: open
deps: []
source: session 2026-10-18l
created: 2026-10-18
moved: 2026-10-18l
updated: 2026-10-18l
last_asked: 2026-10-18l
blocks: [OTW-3]
---

DEC-46 wants from opentelemetry_wrapper import otel. Today the root imports v0 eagerly and v0 sets a global tracer provider at import, so v1 always finds 'someone else configured first'. Making v0's names lazy (module __getattr__) keeps v0 users' imports working but moves v0's import-time side effect to first use of a v0 name: a v0 behaviour change (DEC-71 says v0 is not touched; the root __init__ is not v0 code, but it changes when v0 configures). Recommendation: do it in OTW-13, with a note in the release; until then tests import v1 through tests/impl.py's import_v1.
