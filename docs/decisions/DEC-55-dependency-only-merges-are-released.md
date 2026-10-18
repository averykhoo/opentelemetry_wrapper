---
type: Decision
id: DEC-55
title: Dependency-only merges are released automatically as a patch release to PyPI
actor: owner
decided: 2026-10-18
session: 2026-10-18a
decision_status: PROVISIONAL
imported_from: docs/evidence/decision-log-import-2026-10-18.md
body_sha: sha256:25ccc8698c96beb0bb69777f04cb1876482cc388d0d7cf74ed37fe5eda430df3
tags: [process]
tasks: [OTW-2, OTW-21]
---

- **Auto-release of dependency-only bumps** (decided 2026-10-18): when such a PR merges, a release workflow bumps the
  patch version and publishes to PyPI (trusted publishing, no stored token). Only for merges that change nothing but
  dependency specifiers; anything else is released by hand. A patch release (not `.postN`) is the conventional
  signal, and both are picked up by default. If a bump should ever be opt-in, publish it as a pre-release (`rcN` /
  `.devN`), which pip skips unless asked (`--pre` or an explicit pre-release specifier); *verified* with `packaging`'s
  filtering. Local versions (`+tag`) can't be uploaded to PyPI.

*Imported at adoption (2026-10-18) from `PLAN.md` § Workstreams § 0. Tests, as committed at `24a0430`; now at `docs/archive/PLAN.md`.*
