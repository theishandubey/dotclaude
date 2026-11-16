---
name: spec
description: Use when a feature request is too vague to build, to interview the user and turn the answers into acceptance cases, a test plan and thin slices.
---

# Spec

Turn a vague request into something that can be built and checked.
The output is a spec file; no product code is written here.

## 1. Find the facts yourself

Read the code the request touches before asking anything.
What exists, how it behaves and what it would cost are facts, and finding facts is your job.
When a fork can be settled by running something (behavior, timing, output, layout), run it and let the result decide.
Ask the user only for decisions: what they want, what they prefer, what they will trade.

## 2. Challenge the request once

Before designing, state the premises the request rests on as short sentences the user can agree or disagree with:

- the problem being solved, and for whom;
- what happens if nothing is built;
- what existing code already solves part of it.

A premise the user rejects changes the problem; go back to step 1.

## 3. Interview in rounds

Treat the open decisions as a tree: some can only be asked once others are settled.
Each round, ask every question whose prerequisites are already settled, and no question that depends on another in the same round.

- Number the questions.
- Give your recommended answer with each one, and word the question so "yes" accepts it.
- When a question is a real choice between approaches, show two or three: the smallest that works, the one you would want in a year, and what each costs.
- Wait for the answers, then work out the next round.

Stop when no open decision is left and nothing is silently assumed.
Confirm the shared understanding in a few lines before writing.

## 4. Write the spec

Use the project's own words for things, and keep file paths and code out of it unless a snippet states a decision more exactly than prose can.

- **Problem**: from the user's side.
- **Outcome**: what is true when this is done.
- **Acceptance cases**: numbered, each one observable as pass or fail: "given X, when Y, then Z".
  Include the awkward cases the interview surfaced, and what must not happen.
- **Decisions**: each choice made and why, including interfaces, data shape and contracts.
- **Test plan**: where behavior is tested (the highest existing level that reaches it), which acceptance cases each test covers, and similar tests already in the codebase.
- **Out of scope**: what was discussed and left out.

## 5. Slice it

Break the work into thin slices, each cutting through every layer it needs and checkable on its own.

- A slice names the acceptance cases it makes pass and the command that proves it.
- A slice lists the slices that block it; one with no blockers can start now.
- Preparatory refactoring comes first, as its own slice.
- One mechanical change that touches the whole codebase is not sliced vertically: add the new form beside the old, move callers in batches, then delete the old form.

Show the slices and their blockers to the user and adjust until they agree on the size and order.

## Where it goes

Write the spec where the project keeps its specs.
If it has no such place: `.claude/specs/` in the home repo when the workspace has one, otherwise `.claude/specs/` in the repo, left uncommitted.
End by naming the file, the number of acceptance cases and slices, and any decision that is still the user's to make.
