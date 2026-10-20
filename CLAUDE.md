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

**Id prefixes:** tasks `OTW-n` (workstreams also by alias, `WS0` to `WS11` and `WS5b`), decisions `DEC-n`, stories
`STORY-n`, criteria `AC-n`, owner questions `ASK-n`, batons `BATON-n`, pause records `PAUSE-n`, goals `G-n`. Never reuse
or renumber an id. The pre-adoption design ids (PLAN.md's Q1-Q16, proposals 1-11, workstreams 0-11) map to records in
`docs/evidence/adoption-map-2026-10-18.md`; `Q-n` resolves as an alias of `DEC-n`.

## Overrides of the global rules (owner, 2026-10-18, DEC-70)

- **Commits:** the engine commits its own writes at milestones (`[engine] commit = "milestones"`), and a session
  commits its work through `context-engine commit <paths> -m ...` whenever the contract or the procedures say to,
  without asking. This overrides the global "commit and push only when I ask" for commits. **Pushes still need the
  owner's yes** (contract § Rules).
- **Package installs** into `.context-engine/env/` (the engine's env) need no confirmation; the conda env's
  dependencies still do (global rule).
- **Actor** (not from DEC-70: it follows the harness rule that pushed artifacts name no model): records and commits
  name no model, so `CE_ACTOR` is `claude-code/<Claude Code version>`, not the
  contract's `<harness>/<model>`.

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
  reruns `context-engine init` after building the env. Committing the settings does not install it: once per
  machine, `claude plugin marketplace add averykhoo/context-engine`, then `claude plugin install
  context-engine@context-engine --scope project` (done here 2026-10-18; `claude mcp list` shows
  `plugin:context-engine:engine` connected), then restart Claude Code. Without its tools, use the CLI.
- **The conda env** (2026-10-18; OTel upgraded 2026-10-20 for the 1.0.0 caps, OTW-25): Python 3.12.15, opentelemetry
  1.45.1 / 0.66b1 (which brought upstream's new `opentelemetry-exporter-http-transport` and
  `opentelemetry-exporter-otlp-common`; `logfire` 5.1.1 now declares a conflict with sdk 1.45), sqlalchemy 2.0.54,
  fastapi 0.142.2, pydantic 2.13.5. Besides `requirements.txt` it holds `pytest`, `flake8`, `mypy`, `types-requests`,
  `logfire` (only for the Q15 comparison, DEC-15), and, for the scrubbing benchmark (DEC-16) only, `greenery`,
  `interegular`, `regex`, `google-re2` and `hyperscan` (greenery 4.2.2, interegular 0.3.3, regex 2026.9.29, google-re2
  1.1.20251105, hyperscan 0.9.1), and `aiosqlite` 0.22.1 for the AsyncEngine tests (DEC-91, 2026-10-19). `flit` (for
  releases) is not installed.


## Gate

`"C:/Users/avery/anaconda3/envs/opentelemetry_wrapper/python.exe" -m pytest -q tests && context-engine lint`, from
the repo root. Run it as `context-engine gate run` (`[gate]` in `context.toml`, scope `code`: everything but the
records and the prose); before a commit touching code or tests, `context-engine gate status --require code`.

- **Baseline:** `1047 passed, 4 skipped` in about 110 s on this machine (2026-10-20a, the 1.0.0 cutover, OTW-25,
  merged; about `1151 passed, 5 skipped, 23 xfailed` before it, with v0 still in). v0 is deleted (DEC-96) and the
  suite runs v1 only: there is no `OTW_IMPL` any more. `tests/v0` stays, as the characterization of what v1 keeps from v0 (AC-8): its tests
  reach the package through the adapter `tests/impl.py`, which maps v0's neutral names onto v1; the tests that pinned v0
  details v1 changes (`v0_specific`) and those of v0's internals went with v0. The root's warn-once aliases of v0's
  names are `tests/v1/test_v1_aliases.py`. Global OTel state is isolated by running scenarios in subprocesses
  (`tests/v0/_harness.py`).
- **Canaries** (`tests/upstream`, marker `upstream`, set by `tests/conftest.py`): one test per upstream behaviour or
  semi-private API v1 relies on (AC-23); `pytest -m upstream tests` runs just them. They build their own providers or
  run in scenarios.
- **CI** (DEC-56): `.github/workflows/tests.yml` on push and pull requests, Linux, Python 3.12 / 3.13 / 3.14; the
  steps are `ci/test.sh`. `requirements.txt` pins nothing yet, so CI tests the latest upstream releases.
- **Outside the gate** (by hand, repo root on `PYTHONPATH`; the scripts ported to v1 and checked 2026-10-20a, OTW-25;
  they also run in `tests/v0/test_v0_example_scripts.py` and `tests/v0/test_v0_fastapi.py`):

| Check | Expected |
|---|---|
| `python experiment_otel_logging.py` | exit 0 (final assert passes); console spans 89x `__main__.bitshift`, 4x `__main__.multiply`, 2x `__main__.square`, 2x `asgiref.sync.AsyncToSync.__call__`, all OK, one trace; every log's `otelSpanID` matches a span |
| `python setup_otel_logging.py` | exit 0, 9x `__main__.A.__new__` and 9x `__main__.A.__init__` spans (plus `A.c`, `A.e`, ...), all status OK, every log inside a span |
| `python log_weird_things.py` | exit 0, every stderr line is valid one-line JSON |
| `python sqlalchemy_example.py` | exit 0, the three `is_sqlalchemy_*` lines (True, True, False) **and** a `SELECT :memory:` span in stdout (no `connect` span: `otel.instrument(engine)`, DEC-1) |
| `python fastapi_main.py` | `/hello-hello` returns `"hello hello"`, `/metrics` and `:9464` return 200 (of the 2 workers one serves `:9464`, the other warns) |
| `flake8 --max-line-length 119 ./opentelemetry_wrapper/` | 1 finding, pre-existing (`v1/_prometheus.py:99`, E501) |
| `mypy ./opentelemetry_wrapper/` | 11 errors, all pre-existing (in v1) |
| `python benchmarks/overhead.py` | a table of ns per call; 2026-10-20a (v1): bare OTel span ~37 µs, decorated ~59 µs (no processor) |

## Release (by hand; `docs/runbooks/release.md` is the method)

The distribution is `opentelemetry_wrapper` on PyPI (flit; `requires-python = ">=3.12"` from 1.0.0, the first release
that ships v1 and the hard cutover from v0, DEC-44, DEC-96; the 0.x releases were v0, `">3.8.0"`). `pip install flit`
into the env first. `~/.pypirc` holds a `[pypi]` section with `username = __token__` and the PyPI token. Bump
`__version__` in `opentelemetry_wrapper/__init__.py` (which must keep its docstring), `flit publish`, then check the
release installs: `pip download opentelemetry_wrapper==X.Y.Z` in an empty directory. The automated release for
dependency-only bumps is planned (DEC-55, OTW-2).

## Scratch space

`.scratch/` is gitignored. Use it for anything throwaway: experiment scripts, downloads, generated output. Prefer it
over the system temp dir so things stay findable. Never reference `.scratch/` from tracked code or docs.

## After every push: babysit CI

Whenever you push, launch a background agent with the **Haiku** model (`Agent` tool, `model: "haiku"`) to watch the
GitHub Actions run for the pushed commit on `averykhoo/opentelemetry_wrapper`, and carry on with other work meanwhile.
Tell the agent to:

- find the run(s) for the pushed branch and commit SHA and poll until they complete (sensible interval, give up after
  ~30 min). If no run appears within a few minutes, report "no CI run triggered" instead of waiting (there may be no
  workflow for that branch; `.github/workflows/tests.yml`, added 2026-10-18k, runs on every push to any branch);
- on failure, fetch the failing job's log and report the failing job/step and the relevant error lines verbatim;
- only watch and report: no code changes, no re-runs, no pushes.

`gh` is not installed: use `curl` against the GitHub REST API as described under "GitHub CI logs" in the global
`~/.claude/CLAUDE.md`. Pass the token through the environment (`GH_TOKEN`); never write it into this repo.

## Framework feedback (owner, 2026-10-18, DEC-70)

This repo is the engine's second adopter, so its friction is worth recording. **At every clean close, append to
`context-engine-feedback.md`** (newest first, dated, with the session key) anything the session noticed: an
after-action review (what worked, what to improve), friction with the engine or the procedures, tokens spent on
ceremony rather than work, engine bugs or refusals with a bad remedy, and simplifications that would help. Nothing
noticed: write nothing. Engine bugs also go there, not to the engine repo's board.
