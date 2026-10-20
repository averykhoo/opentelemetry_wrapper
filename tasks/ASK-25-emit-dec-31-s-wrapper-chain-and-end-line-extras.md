---
type: Question
id: ASK-25
title: Emit DEC-31's wrapper-chain and end-line extras (opentelemetry_wrapper.code.*) on every span, or only is_class as built?
brief: 'Recommendation: only is_class for now; each extra adds an attribute to every span with no consumer yet'
pri: LATER
state: closed
deps: []
source: session 2026-10-18l
created: 2026-10-19
moved: 2026-10-18l
updated: 2026-10-20a
last_asked: 2026-10-20a
blocks: [OTW-5]
status: deprecated
closed: 2026-10-20a
answered: {on: 2026-10-20, session: 2026-10-20a, decision: DEC-95}
---

DEC-31 says to put extras (wrapper chain, is_class, end line) under opentelemetry_wrapper.code.*. OTW-5 built is_class only (on classes). Options: (a) emit all three as DEC-31 lists; (b) is_class only, add the others when someone needs them. Recommendation: (b).

## Log

- 2026-10-20a (claude-code/2.1.287): answered by the owner: DEC-95
