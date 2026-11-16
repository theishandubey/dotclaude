---
name: diagnose
description: Use when a bug's cause is not obvious, a failure is intermittent, a test is flaky, or something regressed or got slow.
---

# Diagnose

One loop finds most bugs: a command that fails because of this bug, evidence gathered against it, and a fix at the first place things went wrong.
Reading code to build a theory before that command exists is the failure this skill prevents.

## 1. Build a failing check

Find one command that goes red on this bug and will go green once it is fixed.
Try these in order and stop at the first that reaches the bug:

1. A failing test at whatever level reaches it.
2. A script against the running thing: an HTTP call, a CLI run with a fixture, a headless browser.
3. A replay of a captured request, payload or log through the code path.
4. A small harness that calls the suspect code with its dependencies stubbed.
5. Two runs of the same input (old and new version, two configs) with the outputs diffed, or `git bisect run` when a good state is known.

The check must assert the symptom the user reported, not "it did not crash".
Make it fast and deterministic: narrow the scope, pin the clock, seed randomness, isolate files and network.
Run it once and keep the command and its output.
If no check can be built, stop, list what you tried, and ask for access, a captured artifact or permission to add temporary logging.

## 2. Shrink it

Remove inputs, callers, config and steps one at a time, rerunning after each cut.
Stop when removing anything else makes the check pass.

## 3. Rank hypotheses, then test them

Write three to five candidate causes before testing any.
Each one states what it predicts: "if X is the cause, changing Y makes the failure disappear".
A candidate with no prediction is dropped.
Test the one that splits the remaining space most, change one thing per run, and read real state through a debugger or a targeted log.
Tag every temporary log line with one unique prefix so a single search removes them all.
For a slowdown, measure a baseline and bisect; logs rarely find it.

## 4. Fix where it first went wrong

The symptom is where a bad state became visible.
Ask "why" until the answer is a wrong decision in the code, not a consequence of an earlier one.
Then ask whether the state that broke things is allowed to exist.
If it is, the code that broke on it is the cause and handling it there is the fix.
If it is not, a guard at the crash site hides the bug: find what produced the state.
Guards, retries, swallowed errors, clamped values and discarded state are the usual ways a bug gets hidden.
Search for the same fault elsewhere and fix every instance.

When two fixes resting on the same belief have both failed, stop writing fixes.
Write that belief down in one sentence, find an observation that would differ if it were false, and make it.

## 5. Land it in order

1. Commit the failing check as a test, when there is a level that exercises the real pattern; if there is none, say so, because that gap is a finding.
2. Apply the smallest fix the evidence justifies. Anything added because it "might help" does not ship.
3. Rerun the test, then the original unshrunk check.
4. Delete the tagged logs and any harness.
5. State the cause in the commit message.

## Flaky tests

A flake is a real bug in the test, the code or the environment.

- Measure the failure rate first: run it 50 times alone, then inside the suite, then in parallel, and record failures out of runs.
- Fails only in the suite: order or shared state. Rerun with the failing order and halve the list of earlier tests until one remains.
- Fails only in parallel: a shared port, file or database.
- Fails alone: time, randomness or a race. Vary the timezone, the clock (midnight, month end, DST), CPU load and the temp dir, and see which one moves the rate.
- Never fix one with a retry, a sleep, a longer timeout or a skip. Waiting is fine only when it waits for the actual condition.
- Fix one cause, measure again, and look for a second.
- To claim the rate is below X you need about 3/X clean runs in a row. Ten green runs say little about a 5% flake.

## Evidence log

Keep one line per step, each with the command and the number it produced: the rate before, each cause and how it was shown, the fix, the rate after.
Replace secrets with `<REDACTED>` in anything you show.
The reply states what was broken, the cause, the fix, and the failing-then-passing output.
