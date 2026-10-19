---
type: Decision
id: DEC-90
title: OTEL_WRAPPER_HEADER_ATTRIBUTES_EXCLUDE adds to the default denylist; only configure() in code replaces it
decision_status: PROVISIONAL
actor: owner
tasks: [OTW-7]
tags: [api, privacy]
decided: 2026-10-19
session: 2026-10-19a
body_sha: sha256:3c3a2af7e19b151363fb0228561662e296b116b3bede19bf3dfbac8560bd4bd7
---

Owner, 2026-10-19 (session 2026-10-19a). The session asked (multiple choice): "OTW-7 (x-userinfo headers): as built, setting OTEL_WRAPPER_HEADER_ATTRIBUTES_EXCLUDE *replaces* the default denylist (`*token*,at_hash,c_hash,nonce,session_state,sid`). So `...EXCLUDE=email` would start recording access_token and refresh_token unredacted, because the scrubber lets x-userinfo claims through (DEC-2). What should the variable do?" The owner chose, verbatim:

> Env adds to default (Recommended)

whose option read: "The env var adds patterns to the default list. Only an explicit `otel.configure(header_attributes_exclude=[...])` in code replaces it, so a single env typo can't leak tokens."
