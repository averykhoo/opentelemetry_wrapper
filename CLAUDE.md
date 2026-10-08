# CLAUDE.md

## Python

Always use this repo's conda env, `opentelemetry_wrapper` (Python 3.12), never the system Python:

```
C:\Users\avery\anaconda3\envs\opentelemetry_wrapper\python.exe
```

e.g. `"C:/Users/avery/anaconda3/envs/opentelemetry_wrapper/python.exe" -m pytest -q` from the repo root.

## Scratch space

`.scratch/` is gitignored. Use it for anything throwaway: experiment scripts, downloads, generated output. Prefer it over
the system temp dir so things stay findable. Never reference `.scratch/` from tracked code or docs.

## After every push: babysit CI

Whenever you push, launch a background agent with the **Haiku** model (`Agent` tool, `model: "haiku"`) to watch the
GitHub Actions run for the pushed commit on `averykhoo/opentelemetry_wrapper`, and carry on with other work meanwhile.
Tell the agent to:

- find the run(s) for the pushed branch and commit SHA and poll until they complete (sensible interval, give up after
  ~30 min). If no run appears within a few minutes, report "no CI run triggered" instead of waiting (there may be no
  workflow for that branch; `.github/workflows/` didn't exist as of 2026-10-07);
- on failure, fetch the failing job's log and report the failing job/step and the relevant error lines verbatim;
- only watch and report: no code changes, no re-runs, no pushes.

`gh` is not installed: use `curl` against the GitHub REST API as described under "GitHub CI logs" in the global
`~/.claude/CLAUDE.md`. Pass the token through the environment (`GH_TOKEN`); never write it into this repo.
