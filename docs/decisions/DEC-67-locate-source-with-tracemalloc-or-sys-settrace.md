---
type: Decision
id: DEC-67
title: Locate source with `tracemalloc` or `sys.settrace`
actor: owner
decided: 2022-09-27
session: 2026-10-18a
decision_status: REJECTED
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:4a226125400f533f9563ca8ebbe678d678f303d0d693b717b63e5fa80b617e00
tags: [api]
reopen_if: code objects stop giving a reliable file and line
---

* ~~builtin `tracemalloc` can be used locate the source file and line number of a function, if started early enough~~
    * ~~check for the `PYTHONTRACEMALLOC`var?~~
    * ~~there's also `sys.setttrace`, see also PEP 626~~

*Imported at adoption (2026-10-18) from `TODO.md` § won't do, as committed at `24a0430`; now at `docs/archive/TODO.md`.*
