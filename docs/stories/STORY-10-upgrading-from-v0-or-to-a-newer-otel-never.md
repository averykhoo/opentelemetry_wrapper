---
type: Story
id: STORY-10
title: Upgrading, from v0 or to a newer OTel, never breaks a user
actor: agent (reconstructed from PLAN.md § Decided (Process) and § Workstreams 0)
story_status: unconfirmed
goals: [G-10]
date: 2026-10-18
via: adoption, session 2026-10-18a
body_sha: sha256:3896564f61cedab3393185f2c7cfaa96c43ca66957b114e1800771d4763e5365
---

AGENT: reconstructed at adoption (2026-10-18) from PLAN.md § Decided (Process) and § Workstreams 0 (now `docs/archive/PLAN.md`), which the agent wrote from the owner's answers; not the owner's words. Unconfirmed until the owner reviews the charter. The source, verbatim:

- **Rollout: side by side.** v1 ships next to v0 in the same package until it's proven safe against `tests/v0`, then
  becomes the default and v0 is deleted. For one release after that, v0's entry points (`instrument_decorate`,
  `instrument_all`, `instrument_fastapi_app`, `instrument_sqlalchemy_engine`, ...) stay as thin deprecated aliases
  over v1, so users can migrate incrementally.

- **Upstream bumps without anyone watching CI** (the author doesn't check CI results; decided 2026-10-18): automation
  is only worth having if it updates the repo by itself. Use **Renovate** (GitHub app) rather than a home-grown job:
  it opens a PR that raises the OTel caps, the PR's CI runs the suite and the canaries, and Renovate **auto-merges
  only if everything passes**; a failing PR just sits there and the old pins keep protecting users. OTel has shipped
  breaking changes without warning (twice during v0), which is why the pins stay strict (workstream 10). Config to[... the excerpt stops here; the rest is DEC-54]

## Amendments

- **2026-10-18a (claude-code/2.1.287):** corrected: at 1244 (+48) inserted "[... the excerpt stops here; the rest is DEC-54]" after "(workstream 10). Config to"
