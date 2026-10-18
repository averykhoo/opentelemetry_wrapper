---
type: Runbook
title: "Release: tag, publish, confirm, and the fresh-user install trial"
source: FRAMEWORK §7.5, §6.8
created: 2026-10-13
mode: replaced
liveness: LIVING
---

# Release

How a version reaches its users and is shown to work for a stranger. A tag push is a push: its
order (ask, gate, push, watch) is [procedures.md § Push and CI](procedures.md#push-and-ci-68),
and this file adds only what a release needs on top. The repo's values (its version file, build
and publish steps, package index, distribution name and declared floor) are in its `CLAUDE.md`.
A repo that publishes nothing keeps this file unused.

## Tag, publish, confirm

| Do | Why |
|---|---|
| Before tagging: CI is green on exactly the commit to be tagged | a tag on an unverified commit releases it |
| The version is new. A version already on the index is never reused, and a pushed tag is never moved | users and caches already hold what that version meant |
| Push the tag as procedures.md § Push and CI says; key the watcher on the tagged commit and the tag name, and have it follow the release run through its upload step | a release run that fails at upload can look like success from the tag |
| Confirm the version is live on the index (PyPI: `https://pypi.org/pypi/<dist>/<version>/json` returns 200) | a green run is not yet a published release |

## The fresh-user install trial

Every published release, once it is live, gets a background agent that installs the published
artifact the way a stranger would. Its brief says:

- **A blank environment** at the declared floor (the oldest supported runtime); install
  `<dist>==<version>` from the index and nothing else, and record what the installer pulled in.
- **Outside the repo,** and confirm the package loads from that environment, not the checkout.
- **Only what a user has:** the index page, the README, `--help` or `help()`, docstrings and
  error messages. Run the quickstart verbatim, then a realistic first hour: the main uses, saving
  and reopening, bad input, the documented options. Reading the repo is allowed only to confirm a
  suspected bug, and is labelled.
- **Probes as files,** kept beside a report written as it goes ([fan-out.md](fan-out.md)).
- **Every finding classed** `BROKEN` (with a minimal repro), `CONFUSING / DOC GAP`, or `WORKS`.
- **Clean up:** remove the environment, confirm it is gone, delete the temp directory, and leave
  nothing running.

## After the trial

| Do | Why |
|---|---|
| Re-run every `BROKEN` repro first-hand against the source | an agent's report is evidence, not a finding |
| Put the trial in a tracked evidence doc the same hour, and file a board item for each `BROKEN` or `CONFUSING` finding | scratch is throwaway space: anything kept only there is lost (P10) |
| Fix everything `BROKEN` and release it as the next patch version | a published version cannot be repaired in place |
