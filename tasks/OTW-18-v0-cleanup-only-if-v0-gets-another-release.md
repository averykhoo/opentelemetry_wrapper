---
type: Task
id: OTW-18
title: v0 cleanup, only if v0 gets another release
brief: 'v0 is deleted after v1 (DEC-37): fix only what a v0 release needs'
pri: SOMEDAY
state: open
deps: []
source: session 2026-10-18a
created: 2026-10-18
moved: 2026-10-18a
updated: 2026-10-18a
labels: [v0]
---

The old `HANDOFF.md` § TODO lists v0's confirmed bugs and its cleanup items ([history](../docs/evidence/history-to-2026-10-18.md)). v1 fixes the bugs by design (their strict xfails in `tests/v0` turn green under `OTW_IMPL=v1`); the cleanup items (dead duplicates in `otel_providers.py`, `instrument_system_metrics` missing from `__all__`, wrong docstrings, `get_hostname()`'s early return, the stale `sqlalchemy2-stubs` testing note, 26 flake8 and 19 mypy findings, `requires-python = ">3.8.0"` and the hardcoded `requests` response headers, both redone for v1 in OTW-13 and OTW-7) and `asyncio.iscoroutinefunction` (deprecated in 3.14, removed in 3.16) in `instrument_decorator.py` and `type_checking.py`; the latter stays unchanged by DEC-41, so on 3.16 it needs an owner decision only matter if v0 is released again. The secret in v0's startup log is ASK-17.

## Traps

- none known

## Read first

- [history](../docs/evidence/history-to-2026-10-18.md)
