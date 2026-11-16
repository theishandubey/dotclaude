# <Workspace name>

This folder is a home repo.
It holds the notes, plans and architecture docs for the repos cloned inside it.
Those repos are ignored by this repo's git and keep their own history, remotes and rules files.

## Other repos

Read this before reaching into a child repo.
Read the child's own rules file before changing it, and run git for a child from inside the child.

<!-- other-repos:start -->
| Repo | Remote | Default branch | Notes |
|---|---|---|---|
<!-- other-repos:end -->

## Where things go

- `.claude/plans/` - plan-mode plans.
- `.claude/specs/` - specs and briefs.
- `.claude/architecture/<repo>.md` - one architecture document per repo.
- `.claude/decisions/` - decisions that are hard to reverse and would surprise a later reader.

Everything under `.claude/` here is committed, except local settings and worktrees.
