---
type: Decision
id: DEC-96
title: 'The first v1 release is 1.0.0, a hard cutover: v0 deleted, its root names warn-once aliases onto v1'
actor: owner
decision_status: PROVISIONAL
tags: [release, api, packaging]
decided: 2026-10-20
session: 2026-10-20a
body_sha: sha256:12fbebd735dff8c9db18be3689489b3e0889f997fbfb75d007faab411e6cc47a
supersedes: [DEC-80]
---

Owner, 2026-10-20 (session 2026-10-20a). The session recommended moving the OTel caps to 1.45 / 0.66 first, then a `0.2.0rc1` pre-release, then `0.2.0`. The owner wrote, verbatim:

> 2 - it can all move together, i would prefer a v0 to v1 upgrade to be a hard cutover, so it's clearly intentional rather than something the user is shoehorned into

The session asked (multiple choice) what the v1 release should look like, since a hard cutover overrides DEC-80 (root v1, v0's names lazy, v0's deps core until 1.0.0), offering "1.0.0, v0 deleted (Recommended)", "1.0.0, v0 only under .v0" and "1.0.0, keep DEC-80 as is". The owner answered, verbatim:

> good point, i think it shouldn't be completely broken at v1.0 but i'm not sure how to make that true while also recommending a hard cutover - maybe aliasing instrument_decorate and all?

The session proposed: at 1.0.0 v0's code and its heavy core dependencies are deleted; each old root name stays as a thin alias onto v1 per README's upgrade table (instrument_decorate -> @otel, instrument_fastapi_app(app) -> otel.instrument(app), instrument_sqlalchemy() -> otel.instrument(sqlalchemy), instrument_sqlalchemy_engine(e) -> otel.instrument(e), instrument_requests/logging/system_metrics/all -> otel.instrument(...)); each alias prints one stderr line naming its replacement on first use (as DEC-81); instrument_dataclasses() warns and does nothing (DEC-42); instrument_logging's old options are ignored with a warning; the aliases are deleted at 2.0. Options: "Yes, aliases at 1.0.0 (Recommended)" (1.0.0 with v0 deleted, the aliases, the lean install, OTel caps at 1.45/0.66, all in one release with no rc; supersedes DEC-80 and DEC-44's minor-bump plan; OTW_IMPL=v0 leaves the gate, tests/v0 keeps running under v1), "Aliases, but they raise", "Aliases, no warnings". The owner answered, verbatim:

> yes aliases at 1.0 as you recommend, but why would we want instrument_dataclasses() to and do nothing? i thought that decision was about not  auto-instrumenting as a default when we instrument everything? i vaguely recall there was something about excessive instrumentation, or only dataclasses created after calling the function being instrumented?

The session explained that DEC-42 dropped global dataclass instrumentation outright (patching `dataclasses.dataclass` reaches only dataclasses decorated after the call and misses `from dataclasses import dataclass` imported before it; v0's `__getattribute__` patching caused several v0 bugs; `@otel` on each dataclass replaces it), and asked what the alias should do: "Warn, do nothing (Recommended)" or "Patch, but onto v1's @otel". The owner chose, verbatim:

> Warn, do nothing (Recommended)

Read as: the first v1 release is 1.0.0, a hard cutover, with no pre-release. In it: v0's code and v0's core dependencies are deleted (the lean install: integrations as extras, no gRPC); v0's root names are thin aliases onto v1 that warn once on stderr naming the replacement; `instrument_dataclasses()` warns and does nothing; `instrument_logging`'s old options are ignored with a warning; the OTel caps move to 1.45 / 0.66 in the same release. The aliases go at 2.0. No release is cut until the owner says so (DEC-85).
