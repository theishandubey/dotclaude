---
name: map-architecture
description: Use when starting in an unfamiliar codebase or asked to document how a system works, to produce one architecture document with diagrams where every fact points at the code.
---

# Map architecture

Produce one Markdown document with Mermaid diagrams.
Every node, edge, state and transition carries a `path:line` reference read at one pinned commit.
A wrong map is worse than none, so nothing goes in that was not seen in code or in a run.

Work read-only on the code.
Never run migrations, deploys, or anything that touches a shared database or real credentials.

## Where it goes

Unless the user names a path: `.claude/architecture/<repo>.md` in the home repo when the workspace has one, otherwise `.claude/architecture.md` in the repo, left uncommitted.
When the user wants a page to look at or share, publish the same content as a page instead of a second format.

## Method

1. **Pin the commit.** Record `git rev-parse --short HEAD` in the document's `Commit:` line and read everything at that commit.
2. **Orient from cheap signals.** Read the README, the manifests, the CI file (the one build recipe known to work), and the entry points: mains, servers, routes, CLI commands, jobs.
   Write the one-paragraph purpose now, before reading more.
3. **Read the data model before the logic.** Migrations or schema files, or the main data shapes when there is no database.
   Name the three to seven core entities and how they relate.
4. **Follow a connected slice.** From entry points and registrations, follow imports and call sites until each responsibility reaches its input, its output or its side effect.
   An edge is a real call or write site and the condition that permits it.
   A function that is exported but never called on the normal path is not an edge.
5. **Trace one real request by running it.** Pick the user action that matters most, get it running the way CI does, put a stack dump or breakpoint at the final write or response, trigger it once, and read the stack from the bottom up.
   Stub paid or external services at the edge.
   Record each hop as `path:line` and what happens there.
6. **Draw state machines from a table, never from memory.** For each entity with a status field, search for every assignment and update of that field.
   List each write as a row: from, to, guard, `path:line`.
   Draw the diagram from the table.
   A state with no inbound transition, a state with no way out that is not terminal, and a status value the schema allows but no code writes are findings: list them.
   Retry and recovery appear only when they are real transitions in the code.

## The document

Follow [template.md](template.md).
Include a section only when the code has something to show for it.

| Section | Diagram | Drawn from |
|---|---|---|
| System context | `flowchart`: the system, its users, external services | Manifests, entry points, outbound clients, config |
| Components | `flowchart` with boundaries by ownership, trust and deployment | Module layout, imports, registrations |
| Request trace | `sequenceDiagram` of one real request | The run in step 5 |
| State machines | one `stateDiagram-v2` per stateful entity | The transition table in step 6 |
| Data model | `erDiagram` with keys and cardinality | Migrations or schema files |
| Data flow | `flowchart` of stages where data changes form or owner | Call and write sites |

Keep each diagram to what one screen holds: about 12 nodes, about 8 states on the main path.
Split by subsystem or entity instead of shrinking.
Mark what you saw happen as **ran**, and what you concluded without confirming as **inferred**.
End with what was not traced.

## Check it

```
python3 check_refs.py <document> --repo <repo>
```

Run it by its path in this skill's folder.
It fails when a `path:line` does not resolve at the pinned commit, when a state diagram and its transition table disagree, or when a Mermaid block does not parse (checked only if `mmdc` is installed).
Fix every failure and rerun.

## Report

Give the path and a five-line summary, then say what kind of confidence each part has: references checked by script, behavior read or run by you, diagrams rendered or not.
