---
type: Task
id: OTW-16
title: 'v1 documentation: README_v1.md becomes README.md, with an Upgrading guide'
brief: the README states every decided behaviour; nothing in it contradicts a decision
pri: LATER
state: open
deps: []
source: session 2026-10-18a
created: 2026-10-18
moved: 2026-10-18a
updated: 2026-10-18a
labels: [v1, docs]
---

`README_v1.md` is the draft v1 README, matching the decisions. At the switch (DEC-37) it replaces `README.md`, with the "Upgrading from v0" notes of DEC-52 (env var renames, header URL-encoding, the Downward API recipe, the dropped `async ` prefix). From `TODO.md` ("documentation pls, including design decisions"): the design decisions are the records in `docs/decisions/`; link them rather than copying them. The Prometheus trailing-slash note `TODO.md` asked for is moot: v1 uses `add_route`, not a mount (OTW-12).

## Traps

- The fallback `service.name` is `unknown_service:python.exe` on Windows (DEC-4): `README_v1.md` must match.

## Read first

- [history](../docs/evidence/history-to-2026-10-18.md)
