---
type: Question
id: ASK-21
title: When scrubbing a whole record fails, export it bare (name, ids, times, an error note, no attributes) rather than drop it?
brief: 'Recommendation: yes, export bare; drop only if even that fails (as built)'
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
answered: {on: 2026-10-19, session: 2026-10-18l, decision: DEC-82}
---

OTW-8 built it this way: when scrubbing a whole span or log record fails (not one value, which gets the DEC-74 placeholder), the record is exported with only its name, ids, times and a *:error.<Type> note; it is dropped only if building even that fails. Fail closed either way. Recommendation: keep it; a bare record still shows the operation happened.

## Log

- 2026-10-18l (claude-code/2.1.287): answered by the owner: DEC-82
