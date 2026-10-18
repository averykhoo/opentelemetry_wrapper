---
type: Runbook
title: "Sabotage: seeing every new test, guard or refusal fail before believing it"
source: FRAMEWORK §7.5, P7, P17
created: 2026-10-13
mode: replaced
liveness: LIVING
---

# Sabotage

No guard is believed until it has been seen to fail (FRAMEWORK P7); a repo's contract may ask the
same of every new test and refusal, and tie a criterion's `tested` status to it. This is the
procedure. The repo's `CLAUDE.md` names where its scripted probes are kept and, once the
framework's mutation guard (G-T5) is built and run there, this file is its fallback (P16).

## The procedure

| # | Do | Why |
|---|---|---|
| 1 | Name, in one line, what the new check protects | a break of something else proves nothing |
| 2 | Break exactly that: edit the code it guards, corrupt the fixture, drop the check, or plant the bad input (a missing file, a copy out of step, a forbidden id) | the cheapest break the check exists to catch |
| 3 | Run the check and watch it go red for the right reason: read the failure, not only the exit code | a check red for an import error or a typo guards nothing |
| 4 | Restore, run it again, and see it green; compare each file with the copy or hash saved before the break (`git diff --exit-code` alone passes an untracked file whatever it holds) | a check left sabotaged is worse than none |
| 5 | Record it in the commit message: `Sabotage: <what was broken> -> <test> red` (with the engine, in the task close's: `task close <id> -m "<msg>" --body-file <lines.md>`, once the work is committed) | the next reader can repeat it, and a repo that ties `tested` to sabotage reads it here |

## Traps

- **A fresh bytecode cache for every scripted sabotage** (Python: `PYTHONPYCACHEPREFIX=<a new
  temp dir>`). Python trusts a cached `.pyc` whose source has the same size and the same
  modification second, so a same-length break written just after a restore can run the old code
  and pass: a false green.
- **Sabotage where no other session can commit the broken file:** a worktree or a scratch copy,
  not a tree other sessions share (P12).
- **A guard must not pass by finding nothing.** Sabotage its input as well as its logic: an empty
  source, a renamed section or a pattern that matches nothing has to turn it red, not green.
- **A check that cannot be made to fail is a finding:** fix it or remove it, never keep it as
  assurance.
- **Prefer a check to a warning** (P17): when a rule can be enforced, write the check, then
  sabotage it.
- **Keep scripted probes as evidence** where the repo's routes say, until a mutation guard
  replaces them.
