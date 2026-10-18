---
type: Task
id: OTW-8
title: 'Workstream 5b: scrubbing'
brief: rules stay in a regex subset an automaton can handle; scrub on the exporter thread; fail closed
pri: LATER
state: open
deps: [OTW-2]
source: session 2026-10-18a
created: 2026-10-18
moved: 2026-10-18a
updated: 2026-10-18a
aliases: [WS5b]
labels: [v1]
---

Criteria: AC-13, AC-15. Decisions: DEC-16, DEC-18, DEC-58.

*Workstream 5b of the v1 design, verbatim from the pre-adoption `PLAN.md` (`docs/archive/PLAN.md`); there, "workstream n" is the task aliased `WSn` (OTW-1 lists them), "Decided" / "proposal n" / "Qn" are decisions (`docs/evidence/adoption-map-2026-10-18.md`), and "`HANDOFF.md`" is the old note in `docs/evidence/history-to-2026-10-18.md`.*

Our own rules, designed from examples (2026-10-18), not copied from logfire's list. Applied in wrappers around every
exporter we build (spans: attributes, event and link attributes; logs: attributes and body; the in-memory test
exporters too), on the exporter thread, so the cost stays off the caller's path; also to the stderr JSON logs
(decided 2026-10-17) and, via `scrub_argv`, to `process.command_args`. Defence in depth: the primary controls remain
"no arguments on spans" and the header denylist. Anything not behind our wrappers (a user's own processors) is
unscrubbed; README says so.

- **Two kinds of rules.** Key rules: the key's last word names a secret (`password`, `client_secret`,
  `authorization`, `cookie`, ...) -> the whole value is redacted. Value rules: the value *looks like* a secret by
  format, whatever its key (Vault `hvs.`/`hvb.`/`hvr.`, GitHub / GitLab / Slack / Stripe / AWS / Google keys, JWTs,
  `Bearer` / `Basic` credentials, PEM private keys, passwords in URL userinfo, secret-named URL query parameters,
  inline `key=value`) -> only the secret part is redacted (`Bearer [REDACTED]`, `postgresql://user:[REDACTED]@db`,
  `password=[REDACTED]`), so messages stay readable. Rules may have a post-match check (e.g. `Basic` must decode to
  `user:pass`), which keeps false positives like "Basic configuration" out.
- **Not redacted:** `input_tokens`, `tokenizer`, `token_count`, `password_policy`, `passwordless`, trace ids, UUIDs,
  digests. SQL keeps its statement with literals redacted. Exception messages and stack traces get value rules only.
  Command line: `--token abc` redacts the next argument (2+ character flags only; `-p hunter2` is ambiguous).
- **Known false positives** (accepted for now; all verified on the prototype):
  - keys: pagination cursors (`next_token`, `page_token`, `continuation_token`), `cancellation_token`, boolean flags
    (`is_secret`, `has_password`), `access_key` (often a key *id*);
  - inline text: bare `token:` (`token: 7`, `Token: Expired`), prose after a secret name (`password: The password
    must...` redacts "The"), `pwd: /home/bob`, `private_key: /path/to/key.pem`;
  - URL query parameters: `?key=`, `?auth=`, `?page_token=`;
  - value formats: `sk-` slugs (`sk-blue-widget-2024-edition-pro`), 20-character all-caps words starting `ASIA`
    (`ASIAPACIFICREGION123`).
- AWS (`AKIA`/`ASIA`) and Google (`AIza`) keys must end at a word boundary, so a longer run isn't truncated and
  partly redacted.
- **Engine:** rules live in a registry and compile into one matcher behind a small engine interface, so the engine can
  change without touching the rules or callers. Rules stay in a regex subset an automaton library can handle (no
  backreferences, no lookarounds), enforced by a test; which rule fired is found by re-testing the rules on the matched
  text only. Benchmark (2026-10-18, µs per call; 10 attributes / 2 KB body containing "password" / 2 KB body with a
  secret):

  | engine | attrs | "password" body | secret body |
  |---|--:|--:|--:|
  | one `re` per rule | 137 | 1075 | 991 |
  | `re` alternation, named groups | 191 | 1890 | 2070 |
  | `re` alternation, factored, no groups, 32-char prefilter (stdlib default) | 99 | 480 | 480 |
  | greenery automaton union, run on `re` | 94 | 382 | 402 |
  | `re2`, factored, named groups | 151 | 20 | 94 |
  | hybrid: `re` below 256 chars, `re2` above | 78 | 17 | 103 |

  Findings: under `re`, named groups cost ~2x on bodies and ~40% on attributes, and a plain alternation is *slower*
  than one regex per rule (factoring the shared boundaries and dropping groups is what wins). Under `re2`, groups cost
  nothing. The `regex` module is 1.5-2x slower than `re` everywhere. A greenery union only gains ~25% over the
  factored `re` alternation, takes ~3 s to build and can't express `\A`/`\Z`, lazy quantifiers or named groups:
  keep it out of the runtime. `interegular` is useful as a **test-time lint** for overlapping rules (it found one
  overlap, resolved by rule order). `re2` has ~4 µs fixed overhead per call, hence the hybrid. Prefilter at 32
  characters costs nothing measurable on short strings and is 15x faster on trigger-free bodies. Possessive
  quantifiers / atomic groups and Hyperscan were measured too; engine choice and numbers: Q16.
- Never crash: if scrubbing a value fails, drop it (fail closed) and note it. Redactions are listed in an
  `opentelemetry_wrapper.scrubbed` attribute (paths and rule names, never the values).

**Done when:** every must-redact and must-keep example passes; the stderr JSON logs, the in-memory test exporters and
`process.command_args` go through the same scrubber; the per-span overhead benchmark (workstream 0) includes it.

## Traps

- Possessive quantifiers and atomic groups are 30-45% slower under `re` (DEC-16): don't.

## Read first

- The decisions: [DEC-16](../docs/decisions/index.md), [DEC-18](../docs/decisions/index.md), [DEC-58](../docs/decisions/index.md); [the criteria](../docs/criteria.md)
