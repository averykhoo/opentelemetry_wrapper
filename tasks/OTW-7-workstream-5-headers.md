---
type: Task
id: OTW-7
title: 'Workstream 5: headers'
brief: denied claims are dropped before recording; the raw base64 header never appears
pri: LATER
state: open
deps: [OTW-6, OTW-8]
source: session 2026-10-18a
created: 2026-10-18
moved: 2026-10-18a
updated: 2026-10-18a
aliases: [WS5]
labels: [v1]
---

Criteria: AC-12. Decisions: DEC-2, DEC-59.

*Workstream 5 of the v1 design, verbatim from the pre-adoption `PLAN.md` (`docs/archive/PLAN.md`); there, "workstream n" is the task aliased `WSn` (OTW-1 lists them), "Decided" / "proposal n" / "Qn" are decisions (`docs/evidence/adoption-map-2026-10-18.md`), and "`HANDOFF.md`" is the old note in `docs/evidence/history-to-2026-10-18.md`.*

Keep `x-userinfo` flattening (with the base64 padding fix), passed as `server_request_hook`, and keep the raw header
out of `capture_headers` (e.g. by adding it to the sanitize-fields list).

**Which claims (Q2, decided 2026-10-07): everything except a denylist.** Site-specific claims such as an
`employee_id` come through without being named anywhere. The denylist is
`OTEL_WRAPPER_HEADER_ATTRIBUTES_EXCLUDE`: comma-separated glob patterns matched against the flattened claim path
(`realm_access.roles`, `email`). Denied claims are **dropped** before they're recorded, not scrubbed with a marker.
Everything else is recorded as-is, so the scrubber lets all remaining `http.request.header.x-userinfo.*` attributes
through (a generic scrubber would mangle `auth_time`, `session_state` and `iss`; see Evidence). Default (confirmed
2026-10-18): credentials and session handles, `*token*,at_hash,c_hash,nonce,session_state,sid`. Personal data
(`email`, `name`) is captured unless added to the list; README says so.

Response headers: `OTEL_WRAPPER_RESPONSE_HEADER_ATTRIBUTES`, symmetric with the request-header variable, defaulting to
v0's hardcoded Kong / Envoy list (`instrument_requests.py`, including `X-Envoy-Upstream-Service-Time` as upstream
latency), via `RequestsInstrumentor().instrument(response_hook=...)`.

**Done when:** a Keycloak-style header of every base64 length decodes; a custom claim (`employee_id`) and the
claims a generic scrubber would mangle (`auth_time`, `iss`) are recorded unchanged; denylisted claims are absent; the
raw base64 value never appears, including with header capture on.

## Traps

- base64 padding is `-len % 4` `=`; v0's unconditional `==` fails 2 of 3 lengths on 3.12 and records the raw header.

## Read first

- The decisions: [DEC-2](../docs/decisions/DEC-2-x-userinfo-record-every-claim-except-a-denylist.md), [DEC-59](../docs/decisions/DEC-59-environment-variables-standard-names-where-they.md); [the criteria](../docs/criteria.md)
- [v1 design evidence](../docs/evidence/v1-design-evidence-2026-10-18.md): Headers and scrubbing
