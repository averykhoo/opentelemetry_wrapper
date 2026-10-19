---
type: Decision
id: DEC-94
title: With OTEL_WRAPPER_DEBUG=true a scrubbing failure's report shows the real exception message
decision_status: PROVISIONAL
actor: owner
tasks: [OTW-23]
tags: [privacy]
decided: 2026-10-20
session: 2026-10-19a
body_sha: sha256:ba20c5e9a73a43f3070ff34ef1485d43353a77c535db38ef0f94b1372a637e85
---

Owner, 2026-10-20 (session 2026-10-19a). The session asked (multiple choice): "When a value fails to scrub, the wrapper's error report replaces the exception's message with '(withheld: it may contain the value being scrubbed)'. As built, that holds even with OTEL_WRAPPER_DEBUG=true. Before this change, the debug traceback printed the message. Which do you want?" The owner chose, verbatim:

> Show in debug

whose option read: "Debug mode is opt-in, so OTEL_WRAPPER_DEBUG=true prints the real exception message, which may contain the secret."

Read as: without debug, a scrubbing failure's message stays withheld (DEC-74); with OTEL_WRAPPER_DEBUG=true the record and its traceback carry the real message and chained exceptions.
