---
type: Question
id: ASK-22
title: Should configure pick hyperscan automatically when it is installed (engine='auto'), once OTW-13 declares the [hyperscan] extra?
brief: "Recommendation: yes, 'auto' once the extra exists (DEC-16's intent); re until then"
pri: NEXT
state: closed
deps: []
source: session 2026-10-18l
created: 2026-10-18
moved: 2026-10-18l
updated: 2026-10-18l
last_asked: 2026-10-18l
blocks: [OTW-8]
status: deprecated
closed: 2026-10-18l
answered: {on: 2026-10-19, session: 2026-10-18l, decision: DEC-83}
---

DEC-16: stdlib re by default, hyperscan when installed. As built, the default engine is re and engine='auto' picks hyperscan when importable; configure does not pass 'auto' yet. Recommendation: OTW-3/OTW-13 switch configure to 'auto' once the [hyperscan] extra is declared, so only users who opt into the extra get it.

## Log

- 2026-10-18l (claude-code/2.1.287): answered by the owner: DEC-83
