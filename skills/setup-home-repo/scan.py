#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys

MANIFESTS = (
    "package.json", "pnpm-workspace.yaml", "pyproject.toml", "requirements.txt", "Cargo.toml", "go.mod",
    "Gemfile", "pom.xml", "build.gradle", "build.gradle.kts", "composer.json", "mix.exs", "Package.swift",
    "Makefile", "Dockerfile", "docker-compose.yml", "compose.yaml",
)
START = "<!-- other-repos:start -->"
END = "<!-- other-repos:end -->"
HEADER = ["| Repo | Remote | Default branch | Notes |", "|---|---|---|---|"]


def git(cwd, *args):
    run = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True)
    return run.stdout.strip() if run.returncode == 0 else None


def enclosing_repo(root):
    top = git(root, "rev-parse", "--show-toplevel")
    return os.path.realpath(top) if top else None


def default_branch(repo):
    head = git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    return head.split("/", 1)[1] if head else git(repo, "branch", "--show-current")


def child_repos(root):
    found = []
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name)
        if name.startswith(".") or not os.path.exists(os.path.join(path, ".git")):
            continue
        found.append({
            "name": name,
            "remote": git(path, "remote", "get-url", "origin"),
            "default_branch": default_branch(path),
            "manifests": [m for m in MANIFESTS if os.path.exists(os.path.join(path, m))],
            "has_claude_md": os.path.isfile(os.path.join(path, "CLAUDE.md")),
        })
    return found


def scan(root):
    enclosing = enclosing_repo(root)
    return {
        "root": root,
        "is_home_repo": enclosing == root,
        "inside_another_repo": enclosing if enclosing not in (None, root) else None,
        "repos": child_repos(root),
    }


def existing_notes(table_lines):
    notes = {}
    for line in table_lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and line.strip() not in HEADER:
            notes[cells[0].strip("`")] = " | ".join(cells[3:])
    return notes


def refreshed(text, repos):
    if START not in text or END not in text:
        raise ValueError(f"the file has no {START} and {END} markers")
    before, rest = text.split(START, 1)
    table, after = rest.split(END, 1)
    notes = existing_notes(table.strip().splitlines())
    rows = [f"| `{r['name']}` | {r['remote'] or 'none'} | {r['default_branch'] or 'unknown'} | {notes.get(r['name'], '')} |"
            for r in repos]
    dropped = sorted(set(notes) - {r["name"] for r in repos})
    return before + START + "\n" + "\n".join(HEADER + rows) + "\n" + END + after, dropped


def main(argv):
    parser = argparse.ArgumentParser(description="List the git repos directly inside a workspace folder.")
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--update", metavar="CLAUDE_MD",
                        help="rewrite the table between the other-repos markers in this file, keeping its Notes column")
    args = parser.parse_args(argv)
    result = scan(os.path.realpath(args.root))
    if args.update:
        try:
            with open(args.update, encoding="utf-8") as f:
                text, dropped = refreshed(f.read(), result["repos"])
        except (OSError, ValueError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        with open(args.update, "w", encoding="utf-8") as f:
            f.write(text)
        result["dropped_rows"] = dropped
    json.dump(result, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
