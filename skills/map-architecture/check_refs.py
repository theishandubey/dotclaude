#!/usr/bin/env python3
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

PIN = re.compile(r"^Commit:\s*`?([0-9a-f]{7,40})`?", re.M)
REF = re.compile(r"`([^`\s:]*[./][^`\s:]*):(\d+)(?:-\d+)?`")
FENCE = re.compile(r"^```mermaid\n(.*?)^```", re.M | re.S)
TRANSITION = re.compile(r"^\s*(\[\*\]|[\w.-]+)\s*-->\s*(\[\*\]|[\w.-]+)\s*(?::.*)?$", re.M)
SEPARATOR_CELL = re.compile(r"^:?-+:?$")


def line_count(repo, commit, path, cache):
    if path not in cache:
        shown = subprocess.run(["git", "-C", repo, "show", f"{commit}:{path}"], capture_output=True)
        cache[path] = shown.stdout.count(b"\n") + 1 if shown.returncode == 0 else None
    return cache[path]


def broken_references(text, repo, commit):
    cache, broken, checked = {}, [], 0
    for path, line in sorted(set(REF.findall(text))):
        checked += 1
        lines = line_count(repo, commit, path, cache)
        if lines is None:
            broken.append(f"{path}:{line} - no such file at {commit}")
        elif int(line) < 1 or int(line) > lines:
            broken.append(f"{path}:{line} - the file has {lines} lines at {commit}")
    return checked, broken


def sections(text):
    return re.split(r"^#{1,6} .*$", text, flags=re.M)


def cells(row):
    return [c.strip().strip("`") for c in row.strip().strip("|").split("|")]


def transition_tables(section):
    tables, rows = [], []
    for line in section.splitlines() + [""]:
        if line.lstrip().startswith("|"):
            rows.append(cells(line))
            continue
        if rows:
            header = [c.lower() for c in rows[0]]
            if "from" in header and "to" in header:
                source, target = header.index("from"), header.index("to")
                body = [r for r in rows[1:] if not all(SEPARATOR_CELL.match(c) for c in r)]
                tables.append({(r[source], r[target]) for r in body if len(r) > max(source, target)})
            rows = []
    return tables


def state_diagrams(section):
    return [set(TRANSITION.findall(body)) for body in FENCE.findall(section) if body.lstrip().startswith("stateDiagram")]


def state_mismatches(text):
    count, problems = 0, []
    for section in sections(text):
        diagrams, tables = state_diagrams(section), transition_tables(section)
        for index, drawn in enumerate(diagrams):
            count += 1
            if index >= len(tables):
                problems.append("a state diagram has no transition table in its section")
                continue
            for source, target in sorted(drawn - tables[index]):
                problems.append(f"{source} --> {target} is drawn but has no table row")
            for source, target in sorted(tables[index] - drawn):
                problems.append(f"{source} --> {target} has a table row but is not drawn")
    return count, problems


def render_failures(text):
    blocks = FENCE.findall(text)
    if shutil.which("mmdc") is None:
        return f"diagrams: {len(blocks)} not rendered (mmdc is not installed)", []
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        for number, body in enumerate(blocks, 1):
            source = os.path.join(tmp, f"{number}.mmd")
            with open(source, "w", encoding="utf-8") as f:
                f.write(body)
            run = subprocess.run(["mmdc", "-q", "-i", source, "-o", os.path.join(tmp, f"{number}.svg")],
                                 capture_output=True, text=True)
            if run.returncode != 0:
                first_line = (run.stderr.strip().splitlines() or ["mmdc failed"])[0]
                failures.append(f"diagram {number} ({body.split()[0]}) does not parse: {first_line}")
    return f"diagrams: {len(blocks)} rendered with mmdc, {len(failures)} failed", failures


def main(argv):
    parser = argparse.ArgumentParser(description="Check an architecture document against the code it cites.")
    parser.add_argument("document")
    parser.add_argument("--repo", default=".", help="the repository the path:line references point into")
    args = parser.parse_args(argv)
    with open(args.document, encoding="utf-8") as f:
        text = f.read()
    pin = PIN.search(text)
    if not pin:
        print("error: the document has no 'Commit: <sha>' line", file=sys.stderr)
        return 1
    commit = pin.group(1)
    if subprocess.run(["git", "-C", args.repo, "cat-file", "-e", f"{commit}^{{commit}}"], capture_output=True).returncode != 0:
        print(f"error: commit {commit} is not in {args.repo}", file=sys.stderr)
        return 1
    checked, broken = broken_references(text, args.repo, commit)
    diagrams, mismatches = state_mismatches(text)
    rendered, failures = render_failures(text)
    print(f"references: {checked} checked at {commit}, {len(broken)} broken")
    print(f"state tables: {diagrams} diagrams, {len(mismatches)} mismatches")
    print(rendered)
    problems = broken + mismatches + failures
    for problem in problems:
        print(f"  {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
