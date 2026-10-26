---
name: testing
description: How implementers and fixer test their changes - unit tests for every change, end-to-end tests only when the user asks, the shape of each, setting up a harness, how to run them and output discipline. Preloaded by implementer, parallel-implementer and fixer.
user-invocable: false
---

# Testing

Every change gets unit tests.
End-to-end tests are written and run only when the task says the user asked for them.
Test and browser output is the main cost of testing, so the output rules below are binding.

## Unit tests, always

- Test the logic your change adds or alters: parsing, normalizing, ordering, validation rules, calculations, error handling.
- Call the code through its public functions or classes, the way the rest of the codebase calls it.
  Never mock code the repo owns, never assert on private attributes, and never restructure production code only to reach it.
  Stub only what you cannot run in a test: the network, third-party services, the clock, randomness.
- Cover the behavior's boundaries and invalid input, and put variations of one check in a single table-driven test (parametrize, or a loop over cases) instead of one test each.
- Take expected values from the spec or worked examples, never by recomputing them the way the code does.
- Each test has a plain-language name and passes in any order.
- No mutation checks, model-based tests or forced-interleaving tests unless the spec asks for them.
- Use the repo's existing test runner, directory, fixtures and naming exactly; if it has none, add the language's standard runner with the minimum configuration and list it in your report.

## End-to-end tests, only when asked

Write them only when the task says the user asked for end-to-end tests; otherwise write and run none, and leave existing ones as they are.
When asked:
- Cover each user flow the change adds or alters through the entry point its users use, asserting only what they can observe:
  - Web UI: Playwright, with role-based locators (`getByRole`, `getByLabel`).
  - HTTP or RPC service: real requests to the running server.
  - CLI: the real command as a subprocess, asserting on output, exit code and files written.
- Include what only a real request shows: server-side handling of input the browser would block, escaping of values echoed back to the page, and the errors a user sees.
- Each test creates its own data and waits on visible conditions, never on fixed sleeps.
- Use the repo's existing harness exactly; if it has none, add the minimum and list it in your report: for a web app, `@playwright/test` as a dev dependency through the project's package manager, a `playwright.config` whose `webServer` uses the dev script, and one e2e directory.
- Read the markup or templates to learn a page; use `agent-browser` to map it only when its roles and labels are not clear from the code and it is installed (`agent-browser skills get core` loads its guide), with compact snapshots of the interactive elements only.

## Running

- Run the unit tests you wrote and the ones covering the files you changed after each edit; run the whole unit suite once before reporting.
- When end-to-end tests were asked for, run the affected specs while finishing and the whole end-to-end suite once before reporting.
- Send output to a file and read only the summary and failures: `<test command> > "$LOG" 2>&1; tail -n 60 "$LOG"`, with `LOG` under `mktemp -d`; for Playwright, prefix `PLAYWRIGHT_HTML_OPEN=never` and pass `--reporter=line`.
- Never paste traces, HTML dumps, screenshots or server logs into your report; give their paths.
- Start a dev server only if nothing answers at the base URL, and stop it when you finish.

## Failures

- A test that fails because of your change: fix the change.
- A test that fails because the test is wrong or the behavior changed on purpose: fix the test.
- A bug that predates your change: leave the test out, and report the bug with the failing command.

## Report

List each test you added, the commands you ran, and passed and failed counts per suite.
