# context-engine feedback

LIVING. Feedback on the framework and the engine from this repo, its second adopter (the first is adhoc, CE-7), for
the engine repo (`averykhoo/context-engine`). Every session appends at its clean close (`CLAUDE.md` § Framework
feedback): after-action reviews, frictions, tokens spent on ceremony, engine bugs and refusals with a bad remedy,
and simplifications that would help. Newest first; each entry dated, with its session key.

## 2026-10-18: adoption (engine `7fd3997`, framework 0.5)

The adoption itself: a dry run on a throwaway clone, then a full migration of `HANDOFF.md`, `PLAN.md` (84 KB) and
`TODO.md` into records. How it went is summarised in `docs/evidence/adoption-map-2026-10-18.md`.

### What worked

- `init` on an existing repo was clean: 22 files, nothing overwritten, the hook written to a new
  `settings.local.json`, `.context-engine/` appended to `.gitignore`. Lint afterwards named exactly what disagreed
  (HANDOFF over its caps and without a liveness line), each with a usable remedy.
- The repo's own gate ran unchanged as `[gate] command` (`gate run`: 203 passed, 23 xfailed, 24 s), and the scoped
  gate's idea (docs edits don't make the code gate stale) fits a repo whose tests take tens of seconds.
- A CRLF checkout (`core.autocrlf=true`, Windows) leaves lint green: G-D0 does not trip on line endings.
- `orient` is short and to the point (about 25 lines on a fresh board).

### Friction

- **Encoding:** on Windows (cp1252 console) the CLI prints `§` as `�` unless `PYTHONIOENCODING=utf-8` is set. One
  more variable in every command, besides `CE_ACTOR` and `CE_SESSION`. Suggest the CLI reconfigure stdout to UTF-8
  itself (`sys.stdout.reconfigure(encoding="utf-8", errors="replace")`).
- **Command length:** every call is `PYTHONIOENCODING=utf-8 CE_ACTOR=... CE_SESSION=... .context-engine/env/Scripts/
  python.exe -m context_engine ...`, about 120 characters of preamble per operation, repeated across ~150 calls in
  this migration. A `.context/session` file that the CLI reads for the key and actor (written by `session start`,
  cleared by `session close`) would remove two of the four, and the plugin's launcher could cover the interpreter.
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
- **Bulk record creation and milestone commits:** `record new` with an owner actor is a milestone, so creating many
  back-filled records one by one gives one engine commit each, sweeping every pending op line into it. For a
  migration that wants a reviewable history, `decision import` (one write, not a milestone) was the only way to get
  ~70 decisions into one commit.
- **No board importer and no parent task:** the 13 workstreams, the v1 epic and the leftover TODO items were each a
  `task new` plus a `task set aliases=...` plus sections. An epic is a task with `deps` on its children and a label;
  the board shows it as blocked forever. A `parent:` field (or `children:`) with a rollup in `task show` would read
  better.
- **The correctness chain cannot start with `planned` criteria only:** setting `[guards] tests` while no test claims
  anything is red (`claim matched nothing`), so G-T2 stays off until the first criterion is tested.
- **The README that PyPI renders cannot carry a `LIVING` line**, so it goes in `liveness_given`; fine, but the
  template could say so for README files generally.
