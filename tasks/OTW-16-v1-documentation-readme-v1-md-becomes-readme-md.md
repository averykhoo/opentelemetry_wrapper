---
type: Task
id: OTW-16
title: 'v1 documentation: README_v1.md becomes README.md, with an Upgrading guide'
brief: the README states every decided behaviour; nothing in it contradicts a decision
pri: NOW
state: closed
deps: []
source: session 2026-10-18a
created: 2026-10-18
moved: 2026-10-19a
updated: 2026-10-19a
labels: [v1, docs]
status: deprecated
closed: 2026-10-19a
---

`README_v1.md` is the draft v1 README, matching the decisions. At the switch (DEC-37) it replaces `README.md`, with the "Upgrading from v0" notes of DEC-52 (env var renames, header URL-encoding, the Downward API recipe, the dropped `async ` prefix). From `TODO.md` ("documentation pls, including design decisions"): the design decisions are the records in `docs/decisions/`; link them rather than copying them. The Prometheus trailing-slash note `TODO.md` asked for is moot: v1 uses `add_route`, not a mount (OTW-12).

## Traps

- The fallback `service.name` is `unknown_service:python.exe` on Windows (DEC-4): `README_v1.md` must match.

## Read first

- [history](../docs/evidence/history-to-2026-10-18.md)

## Log

- 2026-10-18l (claude-code/2.1.287): From OTW-8 (2026-10-19): README must say that anything not behind our exporter wrappers (a user's own processors or exporters) is unscrubbed.
- 2026-10-19a (claude-code/2.1.287): Upgrading guide must say (DEC-89): v1 spans only a decorated class's own-body members, not inherited ones (v0 did); decorate the base to span its methods. Also DEC-22 as amended: a generator's span is parented at its first next().
- 2026-10-19a (claude-code/2.1.287): closed: done in 56fa3c1: README.md is v1's (DEC-1..93 linked, Upgrading guide, snippets run under test), v0's archived; AC-28, AC-29 tested
