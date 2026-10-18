# context-engine feedback

LIVING. Feedback on the framework and the engine from this repo, its second adopter (the first is adhoc, CE-7), for
the engine repo (`averykhoo/context-engine`). Every session appends at its clean close (`CLAUDE.md` § Framework
feedback): after-action reviews, frictions, tokens spent on ceremony, engine bugs and refusals with a bad remedy,
and simplifications that would help. Newest first; each entry dated, with its session key.

## 2026-10-18k: OTW-2's canaries, interleaving tests, benchmark and CI

### What worked

- **The item's Traps and the frozen evidence doc were enough to start.** `task show OTW-2` plus the evidence doc
  named every canary; no other orientation read was needed beyond `CLAUDE.md` and the harness.
- **The sabotage runbook's fresh-bytecode trap was easy to honour** with `PYTHONPYCACHEPREFIX=$(mktemp -d)` per run,
  and running the breaks in a scratch worktree kept the shared tree clean. One break was mis-aimed (it targeted a
  dedup mechanism upstream does not use) and stayed green: reading why led to a correct break and a better comment.

### Friction

- **`task set --set brief=...` refused at 137 characters with "cut it to 120"**: a good remedy, but the limit is not
  in `task set --help`, so the first try is a guess.
- **The `commit` trailer gap (2026-10-18j) still applies:** the message had to carry `Co-Authored-By:` itself.

## 2026-10-18j: building starts; OTW-2 split (DEC-78); the OTW_IMPL adapter

### What worked

- **The trap that named the design-review threshold made the split happen.** Before writing the review, the
  session looked at what it would cover and found that the self-acting automation had nothing to act on yet (no OTel
  pins until OTW-13), so the owner split the item off rather than reviewing a design against pins that don't exist.

### Friction

- **`record new decision` refused for a missing `decision_status`** without naming its allowed values or a default.
  Every owner decision here is `PROVISIONAL` at first: a default, or the enum in the remedy, would save a round trip.
- **`commit` adds `Session:` but not the harness's `Co-Authored-By:` trailer**, so an agent commit through it lacks
  the attribution the harness asks for (574b025 here) unless the message carries it. The contract says the trailer
  paragraph holds both; `commit` could take `--trailer` or keep a `Co-Authored-By:` line the message ends with.
- **Lint's G-D1 width check found a long line only after a commit attempt**, twice in a row, because the line was
  wrapped by hand. A `lint --fix` for prose width, or the engine reporting every over-wide line rather than the
  first, would save a cycle.

## 2026-10-18i: fast-forward main, prune merged branches, push

### Friction

- **Close and push pull in opposite orders.** The close writes and commits the ledger entry and the banner, so a
  push before the close leaves those commits unpushed (the stray state the owner asked to clear), and a push after it
  means the ledger entry is written before the watcher's verdict exists. This session closed first and reported the
  verdict only in chat. A `session close --pushing` that leaves one line for the verdict, filled in after the push,
  would fix it.

## 2026-10-18h: the charter trimmed and the criteria aligned (DEC-77)

### Simplifications that would help

- **Lint could check the charter's measures against the criteria.** A goal's "How it is measured" column and the
  criteria's Story column drifted apart (four mismatches found by the 2026-10-18g review), and this session checked
  them with a throwaway script. When stories map one-to-one onto goals, lint could check that G-n's AC list equals
  the rows citing its story.

## 2026-10-18g: open items and a parsimony review for the owner

### What worked

- **Pushing the parsimony review into one subagent** (about 100k tokens of reading) kept the session's own context
  to the verdicts; the session checked two findings first-hand before filing them.

### Friction

- **"Are there any open decisions?" has no direct answer.** `PROVISIONAL` means "signed off, not built", so 53 of the
  77 decisions look open to anyone who greps statuses; finding the real open ones took reading the adoption map
  (proposals 3-11 signed off) and the charter's own "the agent's placement" notes. A `decision find --open` (owner
  confirmation pending), or a status that separates "proposed by the agent" from "accepted, unbuilt", would answer it
  in one call. Agent placements recorded inside an owner decision (DEC-73, DEC-76) are invisible to any query.
- **CLI inconsistencies cost retries:** `task comment` takes the message positionally while `task close` takes `-m`;
  `task new` checked the brief cap and the tier cap one at a time, so one filing took three calls.
- **The close in the same turn as the questions:** the owner asked to "think through" the open items, and the
  contract closes before the reply, so their answers will start a new session. That was the 2026-10-18f friction again.

## 2026-10-18f: G-13, then merge and push

### Friction

- **A one-goal follow-up right after a close needed a whole new session**: start, housekeeping, intake, close,
  banner, about 15 engine calls for one goal, one story, one decision and one criterion. "More work after the close
  starts a new session" is costly when the owner just answers the close's own "for you" line. Letting a session
  reopen its own close for the items its digest raised would cut that.
- **Push and CI without a workflow:** the runbook says to do CI's run by hand in a fresh environment
  (`pip install -e ".[dev]"`). This repo's owner wants installs confirmed, and the push changed only records (the
  code scope's id was the same as at the last push), so the fresh run was skipped and the gate ran in the usual env.
  The runbook could let a push whose code scope id matches an already-verified push skip the fresh run.

## 2026-10-18e: charter and story review with the owner

### What worked

- **The owner asks for this one to be carried upstream:** "the higher goal wins". The adoption agent made it up for
  the charter's principles; PLAN.md's list had no ranking. The owner kept it as a rule, because it settles conflicts
  ahead of time (this session: scrubbing fails, so never crash beats telemetry output, which beats no secrets).
  Suggestion: the charter template states it, and the bootstrap and adopt procedures ask the owner to rank the
  goals, not just list them.
- Raising each owner-only uncertainty as an `ask` with a recommendation worked: both (ASK-18, ASK-19) came back as
  "okay with your recommendation", and `ask answer` turned each into a decision and unblocked its task in one step.
- `record new story` checking the goals against the charter caught nothing, but made the order (goal first, then
  story, then criterion) obvious.

### Friction

- **No operation confirms an unconfirmed story.** The owner's "okay" went in as an amendment, then `story_status` was
  hand-edited from `unconfirmed` to `live` (G-I2 says no operation owns that move). A `record confirm <id> --file
  <words>` that does both would remove a hand edit on a stamped record.
- `doc freeze` refuses a new doc with no liveness line, telling you to write `FROZEN ...` by hand. For a doc born
  frozen, it could write the line itself.
- `ask new` refused at NEXT because the tier was full (5 of 5), so a question being raised in chat right now went to
  LATER. A question raised this session is not backlog: questions could sit outside the NEXT cap.
- The `--brief` cap (120 chars) took one retry; the refusal was clear.
- Ceremony vs work: about 40 engine calls for a review that changed one charter, 12 stories, four criteria and four new
  decisions. Most were one-shot milestones that each made their own commit (26 commits this session).
  Batching milestones within a turn would make the history easier to read.

## 2026-10-18c: verification, push to main, scratch cleanup

### What worked

- The plugin's MCP server came up after the restart: `session_start`, `ask_raised` and `lint` answered, so the
  CLI's per-command env (`CE_ACTOR`, `CE_SESSION`, `PYTHONIOENCODING`) was needed only for `gate run` and `commit`.
- Five Sonnet checkers, each followed by a Sonnet skeptic for its non-nit findings, re-verified the whole migration in
  about 5 minutes (850k subagent tokens). Nothing was lost; 6 of 11 non-nit findings survived the skeptics. The
  skeptic pass mattered: it threw out a "commits name a model" finding and three "AC drops a clause" findings, each
  of which was covered elsewhere.
- `gate status --require code` let the push reuse the session-start gate run after prose-only edits.

### Friction

- A frozen evidence doc (the adoption map) can't take an erratum in place. Its wrong citation and missing row went to
  a board item (OTW-19) instead. A correction path for frozen docs (`record correct` works only for stamped records)
  would keep errata next to the text they fix.
- `git push -u origin HEAD:main` from the topic branch set the topic branch to track `origin/main`. The push runbook
  could say to push without `-u` when the target is another branch.

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
- **Prefixes: the kit, the README and DEC-38 disagree, and two prefixes can't be set at all.**
  - The kit's `init` writes `D`, `S`, `T`, `BTN`, `PAU`. The kit README § 3 says `DEC` for decisions in an existing
    repo, and the engine repo's own owner decision (DEC-38, still PROVISIONAL, CE-56) says `DEC`, `STORY`, `AC`,
    `ASK`, `RISK`, `GOAL`, `BATON`, `PAUSE`. This repo followed DEC-38 with five `--prefix` flags
    (`decision=DEC story=STORY task=OTW baton=BATON pause=PAUSE`). A repo that runs plain `init` gets ids it can
    never rename (ids are never renumbered), so the default matters more than any other config value: make the kit
    write DEC-38's set, or make `init` refuse to run without explicit prefixes until it does.
  - Goals and register entries are hardcoded: the charter's goal rows must read `G-n` (`guards.py` `GOAL_RE`), and
    the residual-risk register numbers `INV-n` (`review.py`). DEC-38 renames them `GOAL` and `RISK`, partly because
    `G-` collides with guard names (`G-D3`, `G-W5`), but neither is a `[kinds.*]` prefix, so a repo can't follow
    DEC-38 there. This repo's charter uses `G-1` to `G-10`, so a later move to `GOAL-n` will need an alias path.
  - Old ids from a design doc rarely fit the importer: PLAN.md's `Q15` had to become `Q-15` to import, so the alias
    is `Q-15`, not the `Q15` every old commit and comment uses (see "Decision aliases" below).
  - Questions and old question numbers: the framework maps `Q8` to `ASK-8`, but here Q1-Q16 were all answered, so
    they became decisions (DEC-1 to DEC-16, alias `Q-n`). The first new question was given `--id ASK-17`, by hand, so
    `ASK-n` can never be mistaken for the old `Qn` with the same number; `ask new` would have picked `ASK-1`. A note
    in the kit README § 3 on numbering questions after an import would help.
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
- **Committing the plugin settings didn't install the plugin:** `.claude/settings.json`'s `extraKnownMarketplaces`
  and `enabledPlugins` were in place, but nothing was installed until `claude plugin marketplace add` and
  `claude plugin install --scope project` ran by hand (which also reformatted the settings file). Its MCP server
  then connected first time. The kit README could say the settings alone don't install it on an existing machine.
- **The close's gate receipt is typed by hand:** `session close --guards` takes free text, and the engine already
  holds the run in `.context/gate/runs.jsonl`. In 2026-10-18b the receipt was typed before the run finished and
  recorded the wrong timings (fixed by hand in the ledger). Suggest `--guards last-gate` filling it from the run.
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
