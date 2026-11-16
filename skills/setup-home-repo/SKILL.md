---
name: setup-home-repo
description: Turn a folder that holds several git repos into a home repo that versions their shared notes, plans and architecture docs, or refresh its list of repos.
disable-model-invocation: true
---

# Set up a home repo

A home repo is a small private git repo at the root of a workspace folder.
It commits a `CLAUDE.md` that lists the repos cloned inside it and a `.claude/` folder for plans, specs, architecture docs and decisions.
The child repos stay ignored and keep their own history.

Run the scripts and copy the template by their paths in this skill's folder.

## 1. Scan

```
python3 scan.py <workspace folder>
```

It prints JSON: `is_home_repo`, `inside_another_repo`, and one entry per child repo with its remote, default branch, manifests and whether it has a `CLAUDE.md`.

- `inside_another_repo` is set: stop. A home repo cannot live inside another repo; tell the user which repo encloses the folder.
- `is_home_repo` is true: this is a refresh; go to step 5.
- No child repos: stop and say so. There is nothing to be a home for.

## 2. Draft the notes

For each child repo, read its README and manifests and write one line: what it is and what it is for.
Show the lines to the user and take their corrections before writing anything.
Ask for the workspace's name if the folder name is not it.

## 3. Write the files

1. Copy `template/CLAUDE.md` to `<workspace>/CLAUDE.md` and set the title.
   If a `CLAUDE.md` already exists there, keep its content and add the "Other repos" section with its two marker comments instead.
2. Copy `template/gitignore` to `<workspace>/.gitignore`.
   It ignores everything at the root except `CLAUDE.md`, `.gitignore` and `.claude/`, so child repos and stray files never get staged.
3. Copy `template/claude/` to `<workspace>/.claude/`, without overwriting an existing `settings.json`; add `"plansDirectory": ".claude/plans"` to an existing one.
4. Fill the table:
   ```
   python3 scan.py <workspace folder> --update <workspace folder>/CLAUDE.md
   ```
   Then put each approved note in its row's Notes column.

## 4. Create the repo

```
git -C <workspace folder> init
git -C <workspace folder> add CLAUDE.md .gitignore .claude
git -C <workspace folder> status --short
```

Check that the staged list holds only those paths and no file from a child repo, then make one commit.
Do not add a remote or push; the home repo names private repos, so where it is hosted is the user's call.

## 5. Refresh

```
python3 scan.py <workspace folder> --update <workspace folder>/CLAUDE.md
```

It rewrites only the table between the markers, keeps every existing Notes cell, adds rows for new repos and reports `dropped_rows` for repos that are gone.
Write notes for the new rows as in step 2, tell the user which rows were dropped, and commit the change.

## Report

The path, the repos listed, anything skipped and why, and the commit made.
