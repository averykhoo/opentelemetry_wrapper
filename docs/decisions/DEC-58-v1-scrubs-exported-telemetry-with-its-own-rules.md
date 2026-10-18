---
type: Decision
id: DEC-58
title: v1 scrubs exported telemetry with its own rules
actor: owner
decided: 2026-10-18
session: 2026-10-18a
decision_status: PROVISIONAL
supersedes: [DEC-66]
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:de7b9ad50cadba161d6934707ad7fac3f7a04d2cd209e9ed537659fd191c1af3
tags: [scrubbing]
---

Our own rules, designed from examples (2026-10-18), not copied from logfire's list. Applied in wrappers around every
exporter we build (spans: attributes, event and link attributes; logs: attributes and body; the in-memory test
exporters too), on the exporter thread, so the cost stays off the caller's path; also to the stderr JSON logs
(decided 2026-10-17) and, via `scrub_argv`, to `process.command_args`. Defence in depth: the primary controls remain
"no arguments on spans" and the header denylist. Anything not behind our wrappers (a user's own processors) is
unscrubbed; README says so.

| won't do: sanitizer, sampling | sampling: the SDK's standard samplers. Sanitizer: now done after all (workstream 5b), because spans and logs from instrumentors carry headers, URLs and extras we don't control |

*Imported at adoption (2026-10-18) from `PLAN.md` § Workstreams § 5b. Scrubbing, `PLAN.md` § `TODO.md` triage against the rebuild, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
