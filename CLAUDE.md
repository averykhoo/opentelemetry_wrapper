# CLAUDE.md

<!-- context-engine kit 0.5 begin -->
framework: 0.5

This repo runs the context-engineering framework through `context-engine`. Its rules are the file
imported on the next line, which the framework owns: an upgrade replaces it whole, so it is never
edited here, and this repo's own rules go in this file, outside these markers. If those rules are
not in your context, read that file; if it is missing, run the engine's lint
(`<engine-python> -m context_engine lint`), which names the fix.

@docs/framework/contract.md
<!-- context-engine kit 0.5 end -->

Engine mode since 2026-10-18 (adopted on branch `adopt-context-engine`): the records, the board and the procedures run
through `context-engine`. What is true now and what is next live in `HANDOFF.md` and on the board
(`context-engine task list`); this file holds only what is durable. Where each component lives: `context-engine routes`.

**Id prefixes:** tasks `OTW-n`, decisions `DEC-n`, stories `STORY-n`, criteria `AC-n`, owner questions `ASK-n`,
batons `BATON-n`, pause records `PAUSE-n`, goals `G-n`. Never reuse or renumber an id. The pre-adoption design ids
(PLAN.md's Q1-Q16, proposals 1-11, workstreams 0-11) map to records in `docs/evidence/adoption-map-2026-10-18.md`;
`Q-n` resolves as an alias of `DEC-n`.

## Overrides of the global rules (owner, 2026-10-18)

- **Commits:** the engine commits its own writes at milestones (`[engine] commit = "milestones"`), and a session
  commits its work through `context-engine commit <paths> -m ...` whenever the contract or the procedures say to,
  without asking. This overrides the global "commit and push only when I ask" for commits. **Pushes still need the
  owner's yes** (contract § Rules).
- **Package installs** into `.context-engine/env/` (the engine's env) need no confirmation; the conda env's
  dependencies still do (global rule).

## Environment

- **Tests and scripts:** this repo's conda env, `opentelemetry_wrapper` (Python 3.12), never the system Python:
  `C:\Users\avery\anaconda3\envs\opentelemetry_wrapper\python.exe`, e.g.
  `"C:/Users/avery/anaconda3/envs/opentelemetry_wrapper/python.exe" -m pytest -q tests` from the repo root.
- **The engine** runs from its own env, `.context-engine/env/` (gitignored; never the conda env, never editable).
  `<engine-python>` is `.context-engine/env/Scripts/python.exe`, and `context-engine` below means
  `<engine-python> -m context_engine`. Set `PYTHONIOENCODING=utf-8`, `CE_ACTOR=claude-code/<Claude Code version>`
  (e.g. `claude-code/2.1.287`; records name no model) and `CE_SESSION=<key>` in every command: shell state does not
  persist between tool calls, and without the first the CLI prints `§` as `�` on this machine. Rebuild it (a fresh
  clone, or an upgrade: kit README § 4) with:
  `"C:/Users/avery/anaconda3/envs/opentelemetry_wrapper/python.exe" -m venv .context-engine/env`, then
  `<engine-python> -m pip install "context-engine @ git+https://github.com/averykhoo/context-engine@<ref>"`,
  at the ref of the latest ledger entry that names one (adopted at `7fd39975554a5a5edfb7a74e90ccbdcc5a0bd7e3`).
- **The Claude Code plugin** (`.claude/settings.json`, from the engine repo's marketplace) carries the procedures as
  skills (`/context-engine:intake`, `/context-engine:clean-close`, ...) and the MCP server, as
  `mcp__plugin_context-engine_engine__<group>_<verb>` tools; both run the pinned engine above. The orient hook is the
  machine-local one `init` wrote to `.claude/settings.local.json` (the plugin's stays quiet beside it); a new clone
  reruns `context-engine init` after building the env. Without the plugin's tools, use the CLI: nothing is lost.
- **The conda env** (2026-10-18): Python 3.12.15, opentelemetry 1.44.0 / 0.65b0, sqlalchemy 2.0.54, fastapi 0.142.2,
  pydantic 2.13.5. Besides `requirements.txt` it holds `pytest`, `flake8`, `mypy`, `types-requests`, `logfire`
  (only for the Q15 comparison, DEC-15), and, for the scrubbing benchmark (DEC-16) only, `greenery`, `interegular`,
  `regex`, `google-re2` and `hyperscan`.

## Gate

`"C:/Users/avery/anaconda3/envs/opentelemetry_wrapper/python.exe" -m pytest -q tests && context-engine lint`, from
the repo root. Run it as `context-engine gate run` (`[gate]` in `context.toml`, scope `code`: everything but the
records and the prose); before a commit touching code or tests, `context-engine gate status --require code`.

- **Baseline:** `203 passed, 23 xfailed` in about 22 s. `tests/v0` characterizes v0 so v1 can be checked against it:
  plain tests pin behaviour v1 keeps; known bugs are `xfail(strict=True)` tests asserting the correct behaviour, so
  they error once fixed; `@pytest.mark.v0_specific` marks v0 details v1 changes. Global OTel state is isolated by
  running scenarios in subprocesses (`tests/v0/_harness.py`).
- **Outside the gate** (by hand, repo root on `PYTHONPATH`; all passed 2026-10-04):

| Check | Expected |
|---|---|
| `python experiment_otel_logging.py` | exit 0 (final assert passes), every log's `otelSpanID` matches a span |
| `python setup_otel_logging.py` | exit 0, 9x `A.__new__` and 9x `A.__init__` spans, all status OK |
| `python log_weird_things.py` | exit 0, every stderr line is valid one-line JSON |
| `python sqlalchemy_example.py` | exit 0 **and** `connect` + `SELECT :memory:` spans in stdout |
| `python fastapi_main.py` | `/hello-hello` returns `"hello hello"`, `/metrics` and `:9464` return 200 |
| `python opentelemetry_wrapper/v0/utils/type_checking.py` | same output under pydantic 2 and pydantic 1 |
| `pytest --doctest-modules opentelemetry_wrapper/v0/config opentelemetry_wrapper/v0/utils/extract_json_header.py` | 4 passed |
| `flake8 --max-line-length 119 ./opentelemetry_wrapper/` | 26 findings, all pre-existing |
| `mypy ./opentelemetry_wrapper/` | 19 errors, all pre-existing |

## Release (v0, by hand; `docs/runbooks/release.md` is the method)

`~/.pypirc` holds a `[pypi]` section with `username = __token__` and the PyPI token. Bump `__version__` in
`opentelemetry_wrapper/__init__.py` (which must keep its docstring), `flit publish`, then check the release installs:
`pip download opentelemetry_wrapper==X.Y.Z` in an empty directory. The automated release for dependency-only bumps
is planned (DEC-55, OTW-2).

## Scratch space

`.scratch/` is gitignored. Use it for anything throwaway: experiment scripts, downloads, generated output. Prefer it
over the system temp dir so things stay findable. Never reference `.scratch/` from tracked code or docs.

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

## Framework feedback (owner, 2026-10-18)

This repo is the engine's second adopter, so its friction is worth recording. **At every clean close, append to
`context-engine-feedback.md`** (newest first, dated, with the session key) anything the session noticed: an
after-action review (what worked, what to improve), friction with the engine or the procedures, tokens spent on
ceremony rather than work, engine bugs or refusals with a bad remedy, and simplifications that would help. Nothing
noticed: write nothing. Engine bugs also go there, not to the engine repo's board.
