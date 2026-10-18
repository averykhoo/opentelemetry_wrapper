# context-engine feedback

LIVING. Feedback on the framework and the engine from this repo, its second adopter (the first is adhoc, CE-7), for
the engine repo (`averykhoo/context-engine`). Every session appends at its clean close (`CLAUDE.md` § Framework
feedback): after-action reviews, frictions, tokens spent on ceremony, engine bugs and refusals with a bad remedy,
and simplifications that would help. Newest first; each entry dated, with its session key.

## 2026-10-18a: adoption (engine `7fd3997`, framework 0.5)

The adoption itself: a dry run on a throwaway clone, then a full migration of `HANDOFF.md`, `PLAN.md` (84 KB) and
`TODO.md` into records (`docs/evidence/adoption-map-2026-10-18.md`): 70 decisions, 10 stories, 27 criteria,
18 tasks and a question, about 410 engine writes, nearly all scripted. An independent audit agent then re-checked the
whole migration against the originals; its findings are folded in.

### What worked

- `init` on an existing repo was clean: 22 files, nothing overwritten, the hook written to a new
  `settings.local.json`, `.context-engine/` appended to `.gitignore`. Lint afterwards named exactly what disagreed
  (HANDOFF over its caps and without a liveness line), each with a usable remedy.
- The repo's own gate ran unchanged as `[gate] command` (`gate run`: 203 passed, 23 xfailed, 24 s), and the scoped
  gate's idea (docs edits don't make the code gate stale) fits a repo whose tests take tens of seconds.
- A CRLF checkout (`core.autocrlf=true`, Windows) leaves lint green: G-D0 does not trip on line endings.
- `orient` is short and to the point (about 25 lines on a fresh board).
- `decision import` from a generated log was the right tool: bodies copied by line range stayed verbatim
  (the audit diffed all 69), `aliases` kept Q-n, and the heading notes made the supersede links both ways.
- The plugin's launcher works on Windows through git's `sh`: quiet when the local hook exists, orient otherwise.
- `record correct` (a bracketed insertion that keeps `body_sha`) fixed a truncated quote without rewriting it.

### Friction

- **Encoding:** on Windows (cp1252 console) the CLI prints `§` as `�` unless `PYTHONIOENCODING=utf-8` is set. One
  more variable in every command, besides `CE_ACTOR` and `CE_SESSION`. Suggest the CLI reconfigure stdout to UTF-8
  itself (`sys.stdout.reconfigure(encoding="utf-8", errors="replace")`).
- **Command length:** every call is `PYTHONIOENCODING=utf-8 CE_ACTOR=... CE_SESSION=... .context-engine/env/Scripts/
  python.exe -m context_engine ...`, about 120 characters of preamble per operation, repeated on every write in
  this migration. A `.context/session` file that the CLI reads for the key and actor (written by `session start`,
  cleared by `session close`) would remove two of the four, and the plugin's launcher could cover the interpreter.
  This migration made about 410 engine writes (94 `set`, 69 `import`, 67 `link`, 36 `section`, 30 `new`, 28 `dep`);
  only scripting them kept the token cost down.
- **Prefix defaults lag DEC-38:** the kit still writes `D`, `S`, `T`, `BTN`, `PAU`, while the engine repo's owner
  decision (DEC-38, PROVISIONAL, CE-56) and the kit README § 3 say `DEC`, `STORY`, `BATON`, `PAUSE`. Adopting the
  standard took five `--prefix` flags, and a repo that runs `init` without them picks ids it can never rename.
- **Decision aliases:** an alias can come only from `decision import` (and only as the log's hyphenated id: PLAN's
  `Q15` had to be written `Q-15`, so `why Q15` does not resolve) or from `record new --set aliases=[...]`.
  `decision set` refuses `aliases`, and the importer's own remedy ("drop it from that record: `task set <id> --set
  aliases=[...]`") points at an operation that refuses decisions ("DEC-15 is a decision, not a board item").
  Suggest `decision set` accept `aliases` (checked by G-D2's rule), and the importer accept an id-to-alias map.
- **Mixed id series in one log:** PLAN.md had Q1-Q16 and proposals 1-11 in one document. The importer keeps each
  number, so the two series clash (`Q-3` and `P-3` would both be `DEC-3`): the proposals had to be renumbered by hand
  in the copy, keeping their old number only in prose.
- **Bulk record creation and milestone commits:** every `record new` is a milestone, even an agent's reconstructed
  story (`actor: agent (reconstructed from ...)`, `unconfirmed`), so the ten back-filled stories made ten engine
  commits, each sweeping in every pending op line. `decision import` (one write, not a milestone) was the only way to
  get the decisions into one commit. Suggest: reconstructions are not milestones, or a `record import` for stories.
- **`imported_from` leaks the log's path, and an import cannot be undone:** the first import read a log generated
  in `.scratch/`, so all 69 records said `imported_from: .scratch/decision-log.md`, a path this repo's rules forbid
  in tracked files and that no clone has. Undoing the uncommitted import meant deleting the records and the index
  and truncating `ops.jsonl` by hand. Suggest `decision import --source <label>`, and a refusal (or a warning) for a
  log outside the tree or in a gitignored path.
- **The id map freezes the import's default statuses:** the dry run prints every entry as BUILT, the evidence doc is
  saved before the statuses are reviewed, so the frozen map reads as if 66 v1 decisions were built. Suggest the map
  say "status as imported, before review", or `import` take a status column.
- **`task new --body` drops the skeleton's sections:** without `--body` a task gets `## Traps` and `## Read first`;
  with it, neither, and `task section` appends them in call order (Read first landed above Traps once). Suggest
  `--body` replace only the summary.
- **The actor names a model:** the contract asks for `CE_ACTOR=claude-code/<model-id>`, which writes a model name into
  every record, ledger line and op line. This repo forbids model names in committed artifacts, so it uses
  `claude-code/<Claude Code version>` (the OKF actor check accepts it). Suggest the contract allow that form.
- **Nothing links a decision to its task by default:** after the import no decision had `tasks:`, so `why OTW-4`
  found nothing until 66 `decision link` calls. A task body's "Decisions:" line could be parsed, or `task new`
  could take `--decisions`.
- **The gate command names a machine path:** `[gate] command` must name the conda env's interpreter by absolute path
  in a tracked file (`{python}` is the engine's own). A pointer file like `.context-engine/engine-python` for the
  test interpreter would keep machine paths out of `context.toml`.
- **The kit omits `.gitattributes`** (`docs/ledger/ops.jsonl merge=union`, CE-53): added by hand.
- **The runbooks are expensive to read:** FRAMEWORK.md is 158 KB, manual-mode 97 KB, procedures 36 KB, and the
  procedures tables put each step in a single row of 500-plus characters. An adopter greps rather than reads; a short
  "adopting an existing repo" checklist with the commands in order would have saved most of the reading.
- **No board importer and no parent task:** the 13 workstreams, the v1 epic and the leftover TODO items were each a
  `task new` plus a `task set aliases=...` plus sections. An epic is a task with `deps` on its children and a label;
  the board shows it as blocked forever. A `parent:` field (or `children:`) with a rollup in `task show` would read
  better.
- **The correctness chain cannot start with `planned` criteria only:** setting `[guards] tests` while no test claims
  anything is red (`claim matched nothing`), so G-T2 stays off until the first criterion is tested.
- **The README that PyPI renders cannot carry a `LIVING` line**, so it goes in `liveness_given`; fine, but the
  template could say so for README files generally.

### After-action review

- **Worked:** a dry run on a throwaway clone before touching the repo; generating the import log, the evidence docs
  and the task bodies by script from line ranges of the originals, so every copy is verbatim and re-checkable; an
  independent audit agent at the end, which found 11 real defects (a false fact in HANDOFF, decisions no task
  builds, a missing dependency, stale test comments, a test that contradicted a criterion).
- **Improve:** write the adoption map first and generate from it, rather than after: half the audit's findings were
  the map and the records drifting apart. Link decisions to tasks as the tasks are created. Never generate import
  inputs in a gitignored path.
- **Simplify (proposal for the engine):** an `adopt` subcommand that takes the old docs' line-range map (a small TOML
  of "this range becomes that record") and does the import, the evidence docs, the tasks and the links in one go,
  printing the adoption map; most of this session's ~410 writes were exactly that.
