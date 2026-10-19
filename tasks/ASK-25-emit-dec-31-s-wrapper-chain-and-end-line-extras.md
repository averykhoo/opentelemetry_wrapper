---
type: Question
id: ASK-25
title: Emit DEC-31's wrapper-chain and end-line extras (opentelemetry_wrapper.code.*) on every span, or only is_class as built?
brief: 'Recommendation: only is_class for now; each extra adds an attribute to every span with no consumer yet'
pri: LATER
state: open
deps: []
source: session 2026-10-18l
created: 2026-10-19
moved: 2026-10-18l
updated: 2026-10-18l
last_asked:
blocks: [OTW-5]
---

DEC-31 says to put extras (wrapper chain, is_class, end line) under opentelemetry_wrapper.code.*. OTW-5 built is_class only (on classes). Options: (a) emit all three as DEC-31 lists; (b) is_class only, add the others when someone needs them. Recommendation: (b).
