# Shared Rules

These apply to every session and agent, in every project.
Each rule is a default with its reason: set it aside when the reason does not hold.
None of them forbids a built-in agent, skill or command.

## Writing

- Never use an em dash; use a plain dash "-".
- Do not write comments or docstrings in code, in any language.
  Make the code carry the reason instead, in this order: a name, a small helper or a type; then the commit message body.
  Only when neither can show a constraint the code depends on (a deadlock, a platform or library quirk, an external API's behavior) write one line saying why.
  Never write comments that say what the code does, section headers, TODOs or commented-out code.
  When you change code, delete the comments this rule does not allow in the lines you touch, and move any reason they carried into the places above rather than losing it.
  Machine-read directives are allowed when the tooling requires them: shebangs, encoding lines, license headers the project mandates, and linter, type-checker or compiler pragmas.
- Never edit CHANGELOG.md files or files marked as auto-generated.
- In long Markdown files, put each sentence on its own line and keep normal Markdown structure.

## Orchestration

The main session decides how to execute each plan.
There is no fixed route or ladder: the right shape depends on the plan, the codebase and what is running on the machine, and the session that holds the plan is best placed to judge.

The decision is yours:

- For each plan, choose how to execute it: do it yourself, fork, start fresh subagents, run parallel worktree streams, use `/batch`, or use an agent team.
  Mix them within one plan when its parts differ.
  A scripted workflow runs only when the user has asked for one.
- Choose again when the facts change: a slice that turns out to be coupled, a stream that keeps failing, or a machine running short of memory.
- Before starting, say in one or two lines what shape you chose and why, so the user can redirect before tokens are spent.
  When the plan has the shape a workflow suits, say so there with a rough agent count, then proceed with the next best shape unless the user answers "use a workflow".

Defaults for where work runs:

- Plan in the main session.
  A small change, or one that depends on what you have already read, you do yourself.
- A self-contained slice with known files and a proving command goes to `worker` (Sonnet, high effort).
  Pass `model: opus` on the dispatch when a slice has failed its proving command twice or turns out to need a design decision.
  A running worker can ask you questions mid-task; answer them so it does not guess.
- A side task that needs your context is a fork.
  A fork runs on your model, so on Fable prefer a `worker` with a complete brief.
- Codebase search goes to the built-in Explore agent with `model: sonnet` and `effort: medium`; left alone it runs on Opus.
- For a stronger opinion mid-task, consult the advisor: before a hard-to-reverse design, after two fixes resting on one belief have failed, or on a real technical toss-up.
  It reads the whole conversation at its own model's rate on every call, so use it at those points and not for routine questions.
- For an independent critique of a cross-cutting or hard-to-reverse plan, send the plan to `domain-advisor` (Opus, high effort) with the domain to review it as.
  It reviews a plan; it does not write one.
- When a plan was written on Fable and the build runs on Opus, suggest starting the build in a fresh session from the plan file after a long planning session, and switching model in place after a short one.
  Caches are per model, so a switch re-reads the whole conversation once.

Facts to weigh, not rules:

- A fresh subagent starts without your context, re-reads what you already know, and does not produce a better answer than you would.
  It buys parallelism or an independent view.
- A fork shares your prompt cache, so it is the cheap way to run a side task that needs what you already know.
- Parallelism pays only when the pieces are independent.
  Pieces that share files or a changing contract cost more to merge than they save.
- Worktree streams must be merged back and the merged result verified; that integration is part of the cost.
- `/batch` splits into 5 to 30 units and opens a PR per unit; it suits one mechanical change across many files.
- Agent teams let workers see each other's in-progress decisions, at several times the token cost.
- A workflow runs a fixed script of many agents, with a verify stage per item.
  It suits one pipeline over many independent items, and costs the most tokens of any shape.
- A review is worth more from something that has not seen your reasoning.

What the user cares about, in order: a correct result, then token spend, then wall-clock time.

Fixed regardless of the shape chosen:

- "Stop" means stop every running agent and background task at once, then report where each one was.
- Whoever is briefed gets file paths relative to the repo and the command that proves their part.

## Plans

- Use plan mode for anything non-trivial or ambiguous, and skip a plan for a bounded change.
- A plan describes the work, not who does it: the slices, which depend on which, the files each one owns, and the command that proves each one.
- A home repo is a workspace folder whose `CLAUDE.md` has an "Other repos" section.
  Plans, specs, briefs, decision notes and architecture docs belong in the home repo's `.claude/` when there is one, and are committed there.
  Without a home repo, plan-mode files stay at the default `~/.claude/plans/` and other notes go in the repo's own ignored `.claude/`.
  Never commit one inside a product repo unless the user asks for it there.
  A skill that names another place for these files follows this rule instead.
- In a home repo, read the "Other repos" section before reaching into a child repo, read that child's own rules file before changing it, and run git for a child from inside the child.

## Working in a repo

- Notes you keep for a git repo go in its `.claude/` directory, created when you first write one.
- If nothing under `.claude/` is tracked, ignore the whole directory with a `.claude/` line in `.git/info/exclude`, which keeps it out of git without changing a tracked file.
- If the repo already tracks files under `.claude/` (shared settings or skills), leave those tracked and ignore only `.claude/settings.local.json` and `.claude/plans/`.
- The home repo is the exception: its `.claude/` is committed.
- Scratch files still go in the session scratchpad, not in `.claude/`.

## Done means

These are the outcomes a finished change must have.
When and in what order to reach them is the main session's call.

- A bug was reproduced with a command before it was fixed, and that command now passes.
- Changed logic has unit tests.
  End-to-end tests exist only if the user asked for them.
- The build, lint and test suite passed on the final state of the code, run as few times as that takes.
  After a failure, the failed check is rerun alone first.
- The changed thing was run once for real.
  For a UI change, each acceptance case was checked through `/run` and reported pass or fail.
- A non-trivial change was reviewed by something that did not write it (`/code-review`, not at `max` or `ultra` unasked).
  Findings whose failure scenario reproduces are fixed, style findings are skipped, and a second round needs the user's yes.
- A speed or cost claim is backed by the `benchmark` skill's method.
- Lint, type and build failures are fixed or reported with exact output, whether or not this change caused them.

## Shipping

- When asked to ship, run the build, lint and test suite once, then make the atomic commits, then open the PR.
- Stage files by name.
  Outside a home repo, never stage plans, briefs, scratch files or anything the task did not change.
- Write PR bodies and anything else a person will read through the `unslop` skill.

## Learning

- When the user corrects how you work, save it to memory with what was said and why.

## Safety

- Before any command that deletes recursively, rewrites or force-pushes history, drops a database or destroys infrastructure, show the exact command and wait for the user's yes, even when the permission mode would let it through.
- When a permission prompt or classifier blocks a command, do not work around it; tell the user what you wanted to run.

## Environment

- The shell tool is `Bash`; call only the tools in your own tool list.
- Put scratch files in the session scratchpad when one is given, otherwise in a `mktemp -d` directory, never inside a repository, and leave them for the OS to clean.
- Never poll with `sleep` followed by a read.
  Run a long command in the foreground with a timeout, or in the background and wait for its completion notice.

## Principles

- Default to subtraction: remove dead code, redundant validators and stubs before building on the simpler base.
  Make the smallest change that solves the problem, and add no abstraction, layer, guard or option the current need does not demand.
- Keep each decision in one place and pass its result along, instead of repeating the same choice in several places.
- When you replace an internal API, migrate every caller and delete the old one in the same change, unless external users depend on it.
- In a planned rewrite or migration, converge on the target design instead of keeping every intermediate step working with throwaway compatibility code.
  Declare where temporary breakage is acceptable and verify everything at the end.
- When the same correction or instruction comes up a second time, including one already saved in memory, encode it as structure (a lint, type, check or script) instead of more text.
  Only when it needs judgment, make the instruction more prominent and add an example of the failure.

## Commits and branches

- Make atomic commits: one logically complete change each, each building and passing on its own.
- Commit messages, branch names and PR titles describe the change only: no plan numbers, milestone labels, task numbers or step references.
  Name a branch for what it changes, in the repo's branch convention or short kebab-case: `add-top-limit` or `fix-login-redirect`, never `plan-003`, `milestone-2` or `step-4`.
- When a change makes a decision the code cannot show, explain it in the commit message body.
- Never add an agent or Claude co-author trailer.
