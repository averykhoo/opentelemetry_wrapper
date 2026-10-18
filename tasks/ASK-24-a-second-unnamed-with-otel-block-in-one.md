---
type: Question
id: ASK-24
title: A second unnamed 'with otel:' block in one function warns at __enter__ (DEC-47), but AC-22/DEC-49 say warnings fire only at startup, decoration or instrumentation time. Which wins?
brief: "Recommendation: keep the DEC-47 warning but at runtime send it to stderr once, so -W error can't raise it"
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

Under an error filter (-W error) the DEC-47 warning raises into the app from __enter__, which breaks never-crash. Options: (a) keep the warning and amend AC-22 to allow it; (b) at runtime report it to stderr once instead of warnings.warn, so filters cannot turn it into an exception (as DEC-75 does for swallowed failures); (c) drop it. Recommendation: (b).
