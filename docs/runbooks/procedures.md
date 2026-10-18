---
type: Runbook
title: "Procedures: every procedure's steps in order, the engine command and the by-hand step side by side"
source: FRAMEWORK §6, P16
created: 2026-10-12
mode: replaced
liveness: LIVING
---

# Procedures

The **order** of each procedure lives here and nowhere else. FRAMEWORK §6 says what each procedure must
achieve, its guards and its reasons; this file says what to do, in what order. Each step gives:

- **§**: its item number in that FRAMEWORK §6 subsection (`—` if it has none). These numbers are
  stable (P3): records cite them, and they are labels, not the order. The order is the order of
  the rows.
- **Engine**: the `context-engine` command (`<engine-python> -m context_engine ...`, with
  `CE_ACTOR` and `CE_SESSION` set). Over MCP the same operation is the tool
  `mcp__context-engine__<group>_<verb>` (`init` is `mcp__context-engine__init`, `why` is
  `mcp__context-engine__why`), except `baton expire`, which is
  `mcp__context-engine__hk_expire_batons`, and `decision index`, which is
  `mcp__context-engine__hk_regen_index`; from the Claude Code plugin the prefix is
  `mcp__plugin_context-engine_engine__` instead. `—` means the step is not an engine operation.
- **By hand**: the same step without the engine, as a link into
  [manual-mode.md](manual-mode.md), which does every operation by hand and says why.
- **Why**: what the step protects, so a session whose engine erred knows what the right result
  was.

When the engine errors, or refuses what it should allow, do that step by hand and fix the engine
([manual-mode § When the engine and this runbook disagree](manual-mode.md#when-the-engine-and-this-runbook-disagree)).
A refusal with a sensible remedy is not an error: follow the remedy. `<gate>` below is the repo's
gate: its own test command, then `context-engine lint`, as its contract states. With the engine's
Claude Code plugin, each procedure below except session start is also a skill that names its section
here and holds no steps of its own: the few lines it adds are quoted from that section word for
word, and the engine's gate fails when a quote stops matching (kit README § Claude Code plugin).

## Where each part of FRAMEWORK §6 is done

| FRAMEWORK | Steps |
|---|---|
| §6.1 Session start | § Session start; § Resume |
| §6.2 Intake | § Intake |
| §6.3 Clean close | § Clean close |
| §6.4 Pause | § Pause; § Resume |
| §6.5 Decision recording | § Intake (a decision is recorded there, with its actor) |
| §6.6 Delegation and build rounds | no steps: a way of working, not a sequence of steps; its method is [fan-out.md](fan-out.md), its rules FRAMEWORK §6.6 |
| §6.7 Promotion and demotion | § Clean close (items 4, 5a and 5b: freeze, archive, promote) and § Housekeeping (expiry) |
| §6.8 Push and CI | § Push and CI |
| §6.9 Bootstrap | § Bootstrap |
| §6.10 Humans working outside the procedures | § Reconciling foreign commits |
| §6.11 Housekeeping | § Housekeeping |
| §6.12 Keeping this document current | § Clean close (item 5a) |
| §6.13 Rollback and close | not designed yet: no steps |

## Session start (§6.1)

Orientation in one bounded read, work carried over from earlier sessions first. Do not re-rank the board now; that is
clean close's job (FRAMEWORK §5.2).

| § | Do | Engine | By hand | Why |
|---|---|---|---|---|
| 1 | The contract is loaded: global, repo (`CLAUDE.md`, `AGENTS.md`, and the framework contract `CLAUDE.md` imports) and subtree; in an adopted repo the `SessionStart` hook has put `orient`'s output in the context | — | read them if the harness did not; if no orient output is there, the hook did not run (it fails silently): run `orient` yourself after the next step and tell the owner | the rules come before the work |
| — | Mint the session key and reserve it with a `kind: open` stub; use the key as `CE_SESSION` | `context-engine session start` | [§ session start](manual-mode.md#context-engine-session-start) | two sessions never share a key, and a live session is visible to the others (§5.5) |
| — | Start-of-session housekeeping: stale stubs, foreign commits, hand-written receipts | — | § Housekeeping, at session start | what happened since the last session is reconciled before it is built on |
| 2–5 | Read the banner, open batons and pause records (yours first), other open sessions, the NEXT tier, the questions to raise, and the top item's brief, Traps and Read first | `context-engine orient` | [§ orient](manual-mode.md#context-engine-orient) | one capped read replaces opening a dozen files |
| — | Show the owner the other open sessions it lists, in chat, one line each: the key, when it opened and its newest commit; say "none" when there are none. Stop, close or abandon none of them without the owner's word | `context-engine orient` (its open-sessions section); `git log -1 --format='%h %cr' --grep='Session: <key>'` per key | [§ orient](manual-mode.md#context-engine-orient) item 3 | an open stub is either a live session in another window or one that died; only the owner knows which, and what to stop |
| 2 | Do the open batons and pause records it lists before anything else: finish each baton, resume each pause | `context-engine baton done`; § Resume | [§ baton done](manual-mode.md#context-engine-baton-done); § Resume | work carried over from earlier sessions is the most urgent and the easiest to lose |
| 3 | Raise every question it lists (NEXT tier and overdue) in chat, one line each, with any flags from background checks; then mark them raised | `context-engine ask raised <ids>` | [§ ask raised](manual-mode.md#context-engine-ask-raised) | marking them raised restarts the overdue clock, and the stub line is the receipt the close checks (G-W8) |
| 4 | Show the top item, or the one the owner assigned (an assignment overrides the ranking) | `context-engine task show <id>` | [§ task show](manual-mode.md#context-engine-task-show) | the item is the unit of work; its body says how to start |
| 5 | Read that item's `## Read first` list | — | open each file it names | the item's author knew what is needed to start |
| 6 | Read the rest of the orientation note (`HANDOFF.md`) only if needed; remember what you read for the close's `read:` receipt | — | open `HANDOFF.md` | the receipt measures how cheap orientation is |

Background check agents (FRAMEWORK §6.1, tier 1 and 2) are optional. A repo that runs them fires
them right after session start; they report only, and the session triages their flags in step 3.

## Resume (§6.1, §6.4)

When `orient` lists an open pause record of your own session's line of work, or the owner says
"continue".

| § | Do | Engine | By hand | Why |
|---|---|---|---|---|
| — | Read the pause record: what was in flight, the resume step, the branch, the uncommitted paths and the deferred steps | `context-engine orient` | [§ orient](manual-mode.md#context-engine-orient); open the record in the pause directory | the record, not memory, is the state to resume from |
| — | Re-check the tree against it: the branch (`git rev-parse --abbrev-ref HEAD`) and the uncommitted paths (`git status --porcelain=v1 --untracked-files=all`); explain every difference before going on | — | git | another session may have committed, moved or lost those paths since |
| — | Do the resume step, then the deferred steps (gate, commit of the work, re-ranking, banner, runbook filing) | — | as each step's own section says | a pause defers these; it never drops them (FRAMEWORK §6.4) |
| — | Mark the record resumed | `context-engine pause resume <id>` | [§ pause resume](manual-mode.md#context-engine-pause-resume) | `orient` stops listing it, and the record says who picked it up |

## Intake (§6.2)

The owner gives intent. Record it before acting on it.

| § | Do | Engine | By hand | Why |
|---|---|---|---|---|
| 1 | Record the words **verbatim, now**: words that describe behaviour, as a new story or an amendment; words that make a choice, as a decision with `actor: owner`, or a charter edit; an answer to an open question through `ask answer`. Write the words to a file with an editor, not a shell heredoc. Tell the owner in one line which it became | `context-engine record new story "<title>" --file <words.md> --set actor=owner ...`; `context-engine record amend <id> --file <words.md>`; `context-engine record new decision ...`; `context-engine ask answer <id> --file <words.md> --title "<title>"` | [§ record new](manual-mode.md#context-engine-record-new); [§ record amend](manual-mode.md#context-engine-record-amend); [§ ask answer](manual-mode.md#context-engine-ask-answer) | owner words exist only in one transcript until recorded, and each of these writes is a milestone, which the engine commits at once (FRAMEWORK §5.5 rule 4); a stamped record cannot drift (G-D10); heredocs can mangle quotes and backslashes |
| 2 | Link it to the charter goals (`goals: [G-n, ...]` on a story); if none fits, ask: it may be a new goal | `context-engine record new story ... --set goals=[G-n]` | [§ record new](manual-mode.md#context-engine-record-new) | every story traces to a goal, or the charter is missing one |
| 3 | Draft the criteria, live by default; show the owner a digest of three to seven lines, never files. A story marked `sign-off: required` keeps them `planned` until the owner signs them off | — | edit the criteria file | the owner sees what "correct" will mean before it is built |
| 4 | Every owner-only uncertainty becomes a question on the board, with a recommendation, where one can be reached cheaply and held with reasonable confidence (FRAMEWORK §5.3); raise it in chat this session | `context-engine ask new "<question>"`; `context-engine ask raised <ids>` | [§ ask new](manual-mode.md#context-engine-ask-new); [§ ask raised](manual-mode.md#context-engine-ask-raised) | never guess at what only the owner can decide (P8) |
| 5 | If it contradicts an existing decision or criterion, say so at once, and record the outcome as a decision that supersedes or amends the old one. If the owner withdraws a story, or a new story replaces one, retire the old story with the owner's words | `context-engine record new decision ...`, then `context-engine decision supersede <old> <new>`; `context-engine record amend <id> "<text>"`; `context-engine record retire <id> --by owner --file <words.md> [--superseded-by <new>]` | [§ record new](manual-mode.md#context-engine-record-new); [§ decision supersede](manual-mode.md#context-engine-decision-supersede); [§ record amend](manual-mode.md#context-engine-record-amend); [§ record retire](manual-mode.md#context-engine-record-retire) | a silent contradiction is drift nobody chose; a story retired by hand records neither who retired it nor why (G-I2) |
| 6 | On a design change, run a criteria census (each criterion in scope: KEEP, rewrite or retire, with the work assigned) and keep it as an evidence doc | — | write the evidence doc | criteria made stale by a design change are found together, not one failure at a time |

An agent's own decision of consequence is recorded the same way, with its own actor from the
FRAMEWORK §6.5 vocabulary (`agent (<model-id>)`, `owner asked`, ...). Never `actor: owner` on the
agent's own call.

## Clean close (§6.3)

A natural stopping point. **Close eagerly: as soon as every task you were asked for is done, in
that same turn, before the final reply.** Never ask whether to close, and never wait for more
instructions; what is left for the owner goes in the digest (item 8). Stay open only when the
owner says so, and pause (§ Pause) at an awkward stop.
More work asked for after the close starts a new session (§ Session start). The records come
first, then the gate, then the ledger entry that carries the gate's result, then the commit of
what the engine did not commit (it commits at milestones, each task's close and the session's
close among them, and each such commit takes with it what was still uncommitted before it).

| § | Do | Engine | By hand | Why |
|---|---|---|---|---|
| 0 | Every owner word given this session is recorded | as § Intake, step 1 | § Intake | the most easily lost thing of all |
| 1 | Lint, to see which failures earlier sessions left, before adding any of your own | `context-engine lint` | [§ lint](manual-mode.md#context-engine-lint) | a failure you did not cause must not be mistaken for one you did, or hidden under yours |
| 4 | The board: close what is done, once its work is committed (gate green, `context-engine commit`): first freeze each ACTIVE-PLAN doc whose items all close with it (the close refuses until then, naming each); the close's commit carries the freeze and `Closes: <id>`, and `--body-file` puts the `Sabotage:` and receipt lines in it (a reviewed item files its residual risks in the register); comment on what moved, re-rank, file new items; rewrite the summary, `## Traps` and `## Read first` of every NOW and NEXT item you touched | `context-engine doc freeze <doc>`; `context-engine task close <id> -m "<message>" [--body-file <lines.md>]`; `context-engine task comment`; `context-engine task touch`; `context-engine task promote <id> <tier>`; `context-engine task new`; `context-engine task section` | [§ doc freeze](manual-mode.md#context-engine-doc-freeze); [§ task close](manual-mode.md#context-engine-task-close); [§ task comment](manual-mode.md#context-engine-task-comment); [§ task touch](manual-mode.md#context-engine-task-touch); [§ task promote](manual-mode.md#context-engine-task-promote); [§ task new](manual-mode.md#context-engine-task-new); [§ task section](manual-mode.md#context-engine-task-section) | the board is what the next session reads first; the ledger's `rows:` names these items, so they come before it; a plan left ACTIVE-PLAN after its item closes turns G-D4 red (§6.7) |
| 6 | Anything skipped becomes a baton | `context-engine baton add "<step>" --why "<why>"` | [§ baton add](manual-mode.md#context-engine-baton-add) | a sentence in a banner the next close overwrites is lost; a record is not (§5.4) |
| 5a | Durable rules go into the contract; method lessons into a method runbook ([gate.md](gate.md), [sabotage.md](sabotage.md), [fan-out.md](fan-out.md), [release.md](release.md)); a change to how the framework works goes into FRAMEWORK.md in place | — | edit the files | a lesson left in a transcript is relearned (§6.7, §6.12) |
| 5b | Walk the rest of FRAMEWORK §6.7's table: scratch worth keeping into an evidence doc, a conclusion reached into a decision; a doc lint reports over its cap (G-D1) is archived whole, or pruned by hand into an archive file | `context-engine doc archive <doc> --why "<why>"`; `context-engine record new decision ...` | [§ doc archive](manual-mode.md#context-engine-doc-archive); [§ record new](manual-mode.md#context-engine-record-new) | a promotion left to memory does not happen; an archive keeps what was moved findable through its directory's redirect table (§7.3) |
| 6a | Pre-close housekeeping: carry out what this session recorded but did not finish | `context-engine baton expire` (MCP: `hk_expire_batons`); `context-engine record stamp` | [§ baton expire](manual-mode.md#context-engine-baton-expire); [§ record stamp](manual-mode.md#context-engine-record-stamp); the rest of § Housekeeping, before close | recorded intent that is not carried out is forgotten; its operation list goes into the digest |
| 2 | Run `<gate>` (as `context-engine gate run` where `[gate]` names it, so step 7 can read its result); then write the ledger entry over your stub: `rows` (the items touched), the summary (the digest, at most 7 lines), the receipts (`guards` = the gate result verbatim, `read`, `asked`) and `Still owed` | `context-engine gate run`; `context-engine session close --rows ... --summary ... --guards ... --read ... --asked ... --owed ...` | [§ gate run](manual-mode.md#context-engine-gate-run); [§ session close](manual-mode.md#context-engine-session-close) | the close is what the next session trusts; it refuses a receipt that misses an open question (G-W6, G-W8) |
| 3 | Replace the banner: read it and keep its hash, then write yours with that hash; if refused, another session wrote it: read theirs, merge, retry | `context-engine banner show`; `context-engine banner set --seen <hash> --file <banner.md>` | [§ banner show](manual-mode.md#context-engine-banner-show); [§ banner set](manual-mode.md#context-engine-banner-set) | the banner is the one paragraph every session reads; it must never silently erase another session's banner (§5.5) |
| 7 | Lint, then the gate status of the scope `[gate] require` names: green means step 2's run still covers the code; red means the code changed since, so run the gate first. Where the scope names `readers`, require `<scope>+readers` instead, and `gate run --readers` when the readers are red: the close's own writes since step 2 (the ledger entry, the banner) change files they read. Without `[gate] require`, lint and `<gate>` again. Then commit by path what the engine did not, never the whole tree, never `git stash`: through `commit`, which takes the op lines still uncommitted and the records they name with your paths and adds the `Session: <key>` trailer. The engine has committed its milestones, and an operation whose reply said `not committed:` named what is left (with `[engine] commit = "off"`, everything except a pause, which the engine still commits); push only with permission (§ Push and CI) | `context-engine lint`; `context-engine gate status --require <scope>[+readers]`; `context-engine gate run [--readers]`; `context-engine commit <paths> -m "<id>: <what changed>"` | [§ lint](manual-mode.md#context-engine-lint); [§ gate status](manual-mode.md#context-engine-gate-status); [§ gate run](manual-mode.md#context-engine-gate-run); [§ commit](manual-mode.md#context-engine-commit); [§ What every write does](manual-mode.md#what-every-write-does) | lint and the scope's id prove this close: since step 2 the close has written only records, which lie outside the code scope, so a second test run would test the same code (FRAMEWORK §8.5 G-V1), but the readers read those records (a banner can break one, and lint does not check what they check), so they alone run again; a code change since moves the id, and status stays red until the gate runs again (`commit` runs no gate, and refuses a code path no green run covers); committing by path never sweeps up another session's work, and a plain `git commit -o` of a record whose op line is still uncommitted fails lint on a clean checkout (G-W7) |
| 8 | The owner digest in chat, at most 7 lines | — | — | inform-and-proceed only works if the owner sees what was decided (§5.6) |

## Pause (§6.4)

An awkward stopping point; the work continues next session. Only the cheap steps that guard
against an unrecoverable loss are mandatory.

| § | Do | Engine | By hand | Why |
|---|---|---|---|---|
| 0 | Every owner word given this session is recorded | as § Intake, step 1 | § Intake | they exist only in this session's transcript |
| 1 | Move evidence out of `.scratch/` into a tracked doc (a rough, dated ACTIVE-PLAN doc is fine) | — | write the doc | scratch is ignored by git, so anything only there is already lost |
| 3 | The pause record: what is in flight, the resume step, the branch, every uncommitted path and the deferred steps; committed by path at once | `context-engine pause open --in-flight "<what>" --resume "<first step>" --deferred "<steps>"` | [§ pause open](manual-mode.md#context-engine-pause-open) | the next session resumes from the tree's real state, and a committed record cannot be swept away by another session's close |
| 2 | The ledger entry, `kind: pause`: rows and deferred steps | `context-engine session pause --rows ... --deferred ...` | [§ session pause](manual-mode.md#context-engine-session-pause) | one ledger entry per session without exception; too many pauses in a row fail G-W2 |
| — | The ledger and op log are committed by path: the pause and the ledger entry are milestones, so the engine commits each with what was still uncommitted; commit by hand what a `not committed:` reply named (with `[engine] commit = "off"`, the ledger entry and the op log) | — | [§ What every write does](manual-mode.md#what-every-write-does), **Commit the write** | the entry is the evidence the session existed, and a clean checkout of the commit passes lint |

Deferred, not dropped: the gate, the commit of the work itself, re-ranking, the banner and
runbook filing. The next session does them (§ Resume).

## Push and CI (§6.8)

| § | Do | Engine | By hand | Why |
|---|---|---|---|---|
| — | Ask the owner; push only with permission. A push hold, if any, is a line at the top of the contract | — | — | a push reaches other people; it is the owner's call |
| — | `<gate>` green on exactly the commit being pushed | `context-engine lint` | [§ lint](manual-mode.md#context-engine-lint) and the test command | never push red or unverified |
| — | Push, and note the pushed commit's hash (`git rev-parse HEAD`) | — | `git push` | the watcher finds runs by hash, not "the latest run", which may be another session's |
| — | Start a background CI watcher: it finds the runs for that hash (allowing about a minute for them to appear), waits for them to finish, and reports a verdict per run, with the failing step and the log lines around the first error for each failure. It writes its report to a file as it goes. It only watches: no fix, no re-run, no cancel, no push | — | the harness's background agent, or the CI web page | a re-run hides a flaky failure; a fix is the session's job, with the gate |
| — | Without CI (the repo has no workflow, or CI cannot run): do CI's run by hand. The contract's gate names the CI workflow file, if there is one | — | in a fresh environment at the declared Python floor (`requires-python`), clone or check out exactly the pushed commit, install the package with its dev extra only (`pip install -e ".[dev]"`), then `<gate>` | a fresh environment catches what a working one hides: a dependency that was installed by hand and never declared |
| — | A tag push that releases a version also follows [release.md](release.md): publish, confirm the version is live, then the fresh-user install trial | — | [release.md](release.md) | a release is not done until a stranger can install and use it |
| — | Report the verdict to the owner. The push is not done until the watcher reports, and a red run is never described as done | — | — | a push nobody watched is unverified |

## Bootstrap (§6.9)

A repo gets the framework. The engine's adoption kit (`kit/` in the installed package, and its
`README.md`) holds every file and the install, pin and upgrade steps.

| § | Do | Engine | By hand | Why |
|---|---|---|---|---|
| 1 | The owner gives, in chat, a charter (about a page), the first stories and any mandates | — | — | the charter is the root of the correctness chain |
| 2 | Install the engine into its own environment, pinned to a release tag or commit: a non-editable install in `.context-engine/env/` in the repo's root, gitignored (`init` adds the ignore line), never into the repo's environment; register the MCP server only if the repo wants it | — | the kit README § 1 | the repo never imports the engine, so the engine cannot break the repo's own environment; inside the repo's folder at a fixed ref, it is where every tool looks for it, and a kit change reaches the repo only when the pin moves |
| 3 | Write the kit into the repo: the layout, `context.toml`, the skeletons, these runbooks, the kit block appended to `CLAUDE.md`, the framework contract it imports, the `SessionStart` hook in the machine-local settings, and `.context-engine/` appended to the repo's `.gitignore` (created if absent). Nothing existing is overwritten | `context-engine init` | [§ init](manual-mode.md#context-engine-init) | every file the procedures expect exists from the first session, and an existing repo loses nothing |
| 3 | Fill the charter (goals get `G-n` ids) and the config, with a provenance note on every cap; check the id prefixes against ids the repo already uses; put the real test command into `CLAUDE.md` § Gate | — | edit `docs/charter.md`, `context.toml`, `CLAUDE.md` | a cap with no provenance cannot be revisited; a colliding prefix makes two things share an id |
| — | Lint is green, then commit the kit's files by path, before the first session | `context-engine lint` | [§ lint](manual-mode.md#context-engine-lint); `git add -- <the files init wrote>`, leaving out `.context/.gitignore` and `.scratch/.gitignore` (each holds `*`, so ignores itself, and `git add` refuses it), then `git commit -o <those files>` | the engine commits only where `context.toml` is tracked, so a clean checkout of its commits has the config |
| — | Lint is green, then open the first session | `context-engine lint`; `context-engine session start` | [§ lint](manual-mode.md#context-engine-lint); [§ session start](manual-mode.md#context-engine-session-start) | the first session starts from a clean record |
| — | An existing repo, in that first session (FRAMEWORK §11.4; the kit README § 3 in full): its ids take the framework's form, keeping each number, and each old id stays an alias. Dry-run the decision log's import and save the id map it prints as a FROZEN evidence doc; freeze the old log until the import is merged; import; review every entry it set BUILT by default; retire the old log and the repo's own instructions to append to it; commit the import by path. Carry board items and open questions over with `--id` when they have a number, then record each old id (several if the item had several) as an alias, on a question too | `context-engine decision import <log> --dry-run`, then without `--dry-run`; `context-engine decision set <id> --set decision_status=<status>`; `context-engine commit <paths> -m "<message>"`; `context-engine ask new "<title>" --id ASK-8`; `context-engine task set <id> --set aliases=[<old id>]` | [§ decision import](manual-mode.md#context-engine-decision-import); [§ decision set](manual-mode.md#context-engine-decision-set); [§ commit](manual-mode.md#context-engine-commit); [§ ask new](manual-mode.md#context-engine-ask-new); [§ task set](manual-mode.md#context-engine-task-set) | one homogeneous board and series, while every commit message, docstring and doc that cites an old id still resolves (`why`, `task show`, `decision show`) |
| 1 | Record the owner's charter words and first stories | as § Intake, step 1 | § Intake | the first stories are owner words like any other |
| 4 | Draft the criteria and show a digest; open the owner questions; build the first board, with the owner's pick of the first item at NOW (`task new` puts an item at LATER: then `task promote <id> NOW`) | `context-engine ask new`; `context-engine task new` | [§ ask new](manual-mode.md#context-engine-ask-new); [§ task new](manual-mode.md#context-engine-task-new) | the first board ranks the work the charter implies; while anything is open, NOW holds exactly its cap (one by default), or lint is red (G-W5) |
| 4 | Set `[guards]` `charter`, `stories` and `tests` so the correctness-chain guards run, now that the goals, the first stories and their criteria are recorded; lint is green | `context-engine lint` | edit `context.toml`; [§ lint](manual-mode.md#context-engine-lint) | set earlier, a guard is red on a source that is still empty (a goal no story serves, no criterion row), so the first session could not open on a green lint |
| 5 | The first clean close (§ Clean close): the gate is green, the ledger entry is `kind: close`, and the first banner is written with `--seen none` | `context-engine session close ...`; `context-engine banner show`; `context-engine banner set --seen none --file <banner.md>` | [§ session close](manual-mode.md#context-engine-session-close); [§ banner show](manual-mode.md#context-engine-banner-show); [§ banner set](manual-mode.md#context-engine-banner-set) | `none` is the hash of "no banner yet", so the first write is as safe as every later one |

## Reconciling foreign commits (§6.10)

At session start, for commits made without the framework's procedures since the newest ledger
entry. Humans are never required to follow the procedures: the next agent session absorbs the cost.

| § | Do | Engine | By hand | Why |
|---|---|---|---|---|
| 2 | Find the foreign commits: those after the last commit that touched the ledger and carrying no `Session:` trailer | — | `git log --format='%h %an %s [%(trailers:key=Session,valueonly,separator=%x2C)]' <sha>..HEAD`, where `<sha>` is the newest commit touching the ledger that your session did not make (its `session start` stays uncommitted until its first commit): `git log -1 --format=%H --invert-grep --grep='Session: <your key>' -- <ledger>`; foreign ones show `[]`. A `[]` commit whose message still has a `Session: <key>` line (`git log -1 --format=%B <sha>`) is an agent's whose trailer was not in the last paragraph (an older layout: `Session:`, a blank line, then `Co-Authored-By:`): it is that session's, not foreign | an agent commit always carries the trailer (item 1), so a commit without one was made by hand; git reads trailers only from a message's last paragraph ([manual-mode § context-engine commit](manual-mode.md#context-engine-commit) gives the layout) |
| 2 | Write a ledger entry for them: mint the next key as session start does, and insert `## <key> · kind: foreign` at the top, with `- **commits:** <short sha> <author>: <what changed>; ...` and `- **reconciled by:** <your key>` | — | [§ session start](manual-mode.md#context-engine-session-start) for the key and the entry layout | the ledger has an entry for every change to the repo, so a human's work is visible to the next session |
| 2 | Check what they may have made stale: each criterion, prose passage or board item they may have made stale becomes a task or a comment | `context-engine task new`; `context-engine task comment <id> "<text>"` | [§ task new](manual-mode.md#context-engine-task-new); [§ task comment](manual-mode.md#context-engine-task-comment) | a hand edit that changes behaviour makes the text describing it stale |
| 2 | Check them for stated intent: a commit message or doc edit that states a feature or decision is recorded as a story or decision, `via: commit <sha>`, with the author as its actor (`human:<id>`) | `context-engine record new ...` | [§ record new](manual-mode.md#context-engine-record-new) | intent is recorded wherever it was stated, attributed to whoever stated it |
| 4 | A human commit that turned a guard red is not reverted: fix or reconcile it, and say so in the close's summary | `context-engine lint` | [§ lint](manual-mode.md#context-engine-lint) | fixing a guard that a human's commit turned red is the agent's job |

## Housekeeping (§6.11)

The repair pass for things that should happen and keep being forgotten. It **carries out intent
already recorded somewhere and never forms new intent**. Without housekeeping agents (or without
the engine), the main session does all of it, by tier-0 rules: every write is marked
`"mechanical": true` in the op log, with actor `process:housekeep` (or the session's own), and is
committed by path with a `Session: <key>` trailer, so `git revert` undoes it (a commit that says
it also included op lines another session left uncommitted is reverted by path). The operation list
goes into the owner digest.

**At session start** (reconcile what happened since the last session):

| § | Do | Engine | By hand | Why |
|---|---|---|---|---|
| — | A stale `kind: open` stub (another session's, older than the window the contract names; with none named, one with 3 or more closes or pauses after its last activity) becomes `kind: abandoned`: change the kind in its heading, keep its lines, add `- **abandoned:** <your key>: never closed or paused`, and file a baton for whatever it left in flight | `context-engine baton add "<step>" --why "<why>"` (the ledger edit is not an operation yet) | [§ session start](manual-mode.md#context-engine-session-start) for the entry layout; [§ baton add](manual-mode.md#context-engine-baton-add) | a dead session must not look live, and its unfinished work must reach someone (G-W11) |
| — | Foreign commits | — | § Reconciling foreign commits | a human's work enters the record |
| — | A close whose `asked:` receipt was written by hand (no `ask.raised` op line for it): set `last_asked` to that session's key on each question it names | — (not an operation yet) | [§ ask raised](manual-mode.md#context-engine-ask-raised) for the keys written | the overdue clock must restart when a question really was raised |
| — | Commits since the last session that name a board item in their title: a dated comment on the item | `context-engine task comment --mechanical <id> "<sha>: <subject>"` | [§ task comment](manual-mode.md#context-engine-task-comment) | the item's log shows its history without reading git |
| — | A pause record whose uncommitted paths are all committed now: mark it resumed, citing the commit | `context-engine pause resume <id>` | [§ pause resume](manual-mode.md#context-engine-pause-resume) | a pause whose work landed is no longer work carried over |

**Before close** (§6.3 item 6a: carry out what this session recorded but did not finish):

| § | Do | Engine | By hand | Why |
|---|---|---|---|---|
| — | Expire every baton and pause record with 2 or more closes or pauses after its session into a LATER task | `context-engine baton expire` (MCP: `hk_expire_batons`) | [§ baton expire](manual-mode.md#context-engine-baton-expire) | work carried over from earlier sessions must not drift for ever (G-W3) |
| — | Close each item named by a `Closes: <id>` trailer in a commit, citing the commit; anything else housekeeping would close is proposed to the session, never closed by it | `context-engine task close <id> -m "done in <sha> (Closes: trailer)"` | [§ task close](manual-mode.md#context-engine-task-close) | a close needs evidence; a mechanical close without it hides a judgement that nobody recorded |
| — | Stamp every append-only record whose body is final | `context-engine record stamp <ids>` | [§ record stamp](manual-mode.md#context-engine-record-stamp) | owner words in an unstamped record can still drift (G-D10) |
| — | Mark each item that housekeeping updated, so the update does not count as progress | `context-engine task touch --mechanical <id>` | [§ task touch](manual-mode.md#context-engine-task-touch) | a mechanical touch must not look like progress |
| — | Regenerate the decision index, where `[working] decision_index` is set (every engine write to a decision already does; a by-hand decision does not) | `context-engine decision index` (MCP: `hk_regen_index`) | [§ decision index](manual-mode.md#context-engine-decision-index) | a generated file is checked by byte equality, so a stale one is red (G-D6) |
| — | Raise every ratcheting floor to its current count and regenerate any other generated file, where the repo has them, as the guard that names each one says | — | regenerate or raise by hand | as above |
