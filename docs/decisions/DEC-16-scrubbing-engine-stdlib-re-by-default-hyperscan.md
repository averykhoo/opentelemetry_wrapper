---
type: Decision
id: DEC-16
title: 'Scrubbing engine: stdlib `re` by default, `[hyperscan]` as the optional fast engine (Q16)'
actor: owner
decided: 2026-10-18
session: 2026-10-18a
decision_status: PROVISIONAL
supersedes: [DEC-18]
imported_from: docs/evidence/decision-log-import-2026-10-18.md
aliases: [Q-16]
body_sha: sha256:774ceb147679477ba53448a27784ed601f26aa914fc91bf72fc4a4cfc0b7b05c
tags: [scrubbing]
tasks: [OTW-13, OTW-8]
---

- **Q16. Scrubbing engine** (benchmark in workstream 5b). *Decided 2026-10-18:* stdlib `re` by default (factored
  alternation, no groups, 32-character prefilter), plus an optional fast engine. First decided as an `[re2]` hybrid
  (`re` for short strings, `re2` for long ones: same speed on attributes, 10-20x faster on log bodies), then replaced
  by `[hyperscan]` (below). Greenery not at runtime; `interegular` as a test-time lint (dev dependency).
  Follow-ups measured the same day (µs per call; 10 attributes / 2 KB "password" body / 2 KB secret body / argv /
  2 KB adversarial body):

  | engine | attrs | "password" | secret | argv | adversarial |
  |---|--:|--:|--:|--:|--:|
  | `re` default | 88 | 421 | 388 | 47 | 257 |
  | `re2` hybrid | 100 | 17 | 108 | 69 | 169 |
  | Hyperscan alone | 81 | 14 | 40 | 74 | 137 |

  - **Possessive quantifiers / atomic groups** (an `re`-engine rewrite, no change in any match): 30-45% *slower*
    under `re`, even on the adversarial input, because CPython compiles a plain character-class run to a
    specialised opcode and the possessive form goes through a generic loop; neutral under `regex`. Not used.
  - **Hyperscan** (`hyperscan` 0.9.1 on PyPI, MIT, statically links Vectorscan, the open-source fork; wheels for
    Linux, macOS and Windows): every rule expressible, output identical to `re` on every test including non-ASCII.
    Its fixed cost per call is the lowest (2.5 µs vs `re` 4.0, `re2` 6.8), so it needs no hybrid. Engine notes: it
    reports every end offset and only the leftmost start, so the engine takes the leftmost start, lets `re` decide
    the exact span, rule and post-match check, and rescans from there; ASCII `\w`/`\s` are widened so it can only
    over-report; database compile ~0.8 s, once; one scratch space per thread.
  - *Decided 2026-10-18:* `[hyperscan]` is the optional fast engine, **replacing `[re2]`** (faster everywhere except
    argv-sized strings, one engine fewer to maintain); the engine is picked once at configure time from what's
    installed, falling back to stdlib `re`. There's no official Vectorscan package on PyPI; `hyperscan`
    (darvid/python-hyperscan) is the de facto binding, maintained by one person, which is acceptable for an optional
    extra with a fallback. Keeping `[re2]` as well adds little: *verified* (PyPI, cp312), `hyperscan` has wheels for
    Linux x86_64/aarch64 on both glibc (manylinux2014) and musl (Alpine), macOS and Windows amd64, while `google-re2`
    has no musl wheels and only adds win32 / win_arm64.

*Imported at adoption (2026-10-18) from `PLAN.md` § Questions for later, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
