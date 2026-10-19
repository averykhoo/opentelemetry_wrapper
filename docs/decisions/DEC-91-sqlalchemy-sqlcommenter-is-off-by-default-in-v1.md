---
type: Decision
id: DEC-91
title: SQLAlchemy sqlcommenter is off by default in v1 (env opt-in); aiosqlite joins the test dependencies
decision_status: PROVISIONAL
actor: owner
tasks: [OTW-4, OTW-16]
tags: [api, deps]
decided: 2026-10-19
session: 2026-10-19a
body_sha: sha256:ef157f3c4ebece1b974bb6f213f06f26a8d3f25972c556239798d003ba43c65e
---

Owner, 2026-10-19 (session 2026-10-19a). The session asked two multiple-choice questions.

1. "SQLAlchemy sqlcommenter: v0 turns it ON by default, adding traceparent/driver/framework comments to every SQL statement. Upstream leaves it off. v1 as built offers it through OTEL_WRAPPER_SQLALCHEMY_COMMENTER (true, or a list of db_driver,db_framework,opentelemetry_values,attribute), OFF by default. What should v1's default be?" The owner chose, verbatim:

> Off by default (Recommended)

whose option read: "As built and as upstream does. Comments on every SQL statement change query text, which can defeat statement caches and pg_stat_statements grouping. The Upgrading guide notes the v0 difference."

2. "May I add `aiosqlite` to the dev/test dependencies (requirements and the conda env), so AsyncEngine is tested against a real async driver? Today the test uses a stand-in module." The owner chose, verbatim:

> Yes, add it (Recommended)

whose option read: "Install aiosqlite into the conda env, add it to the test dependencies (and CI), and switch the test to the real driver."
