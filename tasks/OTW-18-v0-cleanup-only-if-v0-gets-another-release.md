---
type: Task
id: OTW-18
title: v0 cleanup, only if v0 gets another release
brief: 'v0 is deleted after v1 (DEC-37): fix only what a v0 release needs'
pri: SOMEDAY
state: closed
deps: []
source: session 2026-10-18a
created: 2026-10-18
moved: 2026-10-18d
updated: 2026-10-18d
labels: [v0]
status: deprecated
closed: 2026-10-18d
---

The old `HANDOFF.md` § TODO lists v0's confirmed bugs and its cleanup items ([history](../docs/evidence/history-to-2026-10-18.md)). v1 fixes the bugs by design (their strict xfails in `tests/v0` turn green under `OTW_IMPL=v1`); the cleanup items are dead duplicates in `otel_providers.py`, `instrument_system_metrics` missing from `__all__`, wrong docstrings, `get_hostname()`'s early return, the stale `sqlalchemy2-stubs` testing note, 26 flake8 and 19 mypy findings, `requires-python = ">3.8.0"` and the hardcoded `requests` response headers (both redone for v1 in OTW-13 and OTW-7), and `asyncio.iscoroutinefunction` (deprecated in 3.14, removed in 3.16) in `instrument_decorator.py` and `type_checking.py`. DEC-41 keeps v0 unchanged, so these matter only if v0 is released again, and keeping v0 working on 3.16 would need an owner decision. The secret in v0's startup log is ASK-17.

## Traps

- none known

## Read first

- [history](../docs/evidence/history-to-2026-10-18.md)

## Log

- 2026-10-18d (claude-code/2.1.287): closed: OTW-18: moot, v0 is not touched (DEC-71), so it gets no further release
