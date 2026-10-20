---
type: Decision
id: DEC-98
title: Releases move to PyPI trusted publishing; the owner stops using flit publish; push now
actor: owner
decision_status: PROVISIONAL
tasks: [OTW-26]
tags: [release, process]
decided: 2026-10-20
session: 2026-10-20b
body_sha: sha256:060e29257cf585f59a384c07aa2d0e480fd8377b032a35b42fab5a8eeceb5028
---

Owner, 2026-10-20 (session 2026-10-20b), verbatim, after the 2026-10-20a digest asked to push 21 commits and the local `v0.1.25` tag, and noted that the release (OTW-26) waits for the owner's word and that `flit` is not installed in the env:

> We'll have to migrate to pypi trusted publishing, I will stop using flit. That's not set up yet right? So you can push for now

Read as: releases move to PyPI trusted publishing (a GitHub Actions workflow publishing through OIDC) instead of the owner's `flit publish` with a `~/.pypirc` token; that is not set up yet (the repo has only `.github/workflows/tests.yml`), so the 1.0.0 release (OTW-26) waits for it. Permission to push this session's commits and the `v0.1.25` tag now. The build backend (`flit_core` in `pyproject.toml`) is not named; ASK-27 asks.
