---
name: prototype
description: Use when a design question (does this state model hold, which layout, which approach behaves better) can be answered faster by throwaway code than by discussion.
---

# Prototype

A prototype is throwaway code that answers one question.
The rigor goes into choosing the right design cheaply, not into the code.

## 1. Name the question

Write the question and the decision it feeds in one or two lines at the top of the prototype.
No decision to make means no prototype: build the real thing instead.
Pick the shape from the question:

- **Does this logic or state model hold?** A small pure module (a reducer, a state machine, a few functions over plain data) with a thin shell that drives it.
- **What should this look like?** Several clearly different variants of one screen behind one switcher.
- **Which approach behaves better?** The smallest script that exercises each approach and prints what you are deciding on.

If the question is unclear and nobody can answer, choose by the surrounding code and state the assumption.

## 2. Build it to be thrown away

- Keep it out of the product's code path, in a scratch directory or a file whose name says prototype.
- One command starts it, or one file opens by double-click.
- State lives in memory. If the question is about storage, use a scratch database or file named so nobody mistakes it for real.
- No tests, no abstractions, no error handling beyond what makes it run.
- No production framework when plain HTML or a script will show the idea.

For logic, keep the module pure: the shell calls into it and nothing flows back.
That module is the one part that may be lifted into real code later.
Label buttons and state in the words the business uses, so someone who does not read code can drive it.

For layout, default to three variants and never more than five.
Mount them where the real thing will live, next to real data and real surrounding UI; a variant alone on an empty page always looks fine.

## 3. Show the state

After every action or variant switch, print or render the full relevant state so the change is visible.
For logic, include the cases that are hard to reason about on paper: the normal path, an awkward edge, and something that should be refused.

## 4. Observe, then decide

The observation is the test: drive each variant, take the screenshot, print the timing, read the output.
Suggest a variation the user did not ask for when the evidence points to one.
Throw an approach away and try another without ceremony.

## 5. Report and remove

State, in this order:

1. the question;
2. what was tried;
3. what was observed, with the output, timing or screenshot;
4. the tradeoffs and your recommendation.

Then delete the prototype, or leave it at a path you name and say plainly that it is throwaway.
Only the decision goes into the product; the real build starts from it, not from the prototype's code.
