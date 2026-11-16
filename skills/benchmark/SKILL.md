---
name: benchmark
description: Use when measuring speed or cost, comparing two versions or options for performance, or about to report a speedup or a regression.
---

# Benchmark

A performance number is a claim: under these conditions A takes this long, and B differs by this much, give or take this much.
Answer each question below with evidence from a run, not a guess about the code.

For a quick ballpark the user asked for, one run is enough: still check questions 4 and 7 and say it was one run.
A choice between options is never a ballpark.

## Before running

- Write the claim you expect to make, in the words you would ship: "export is 30% faster at p50 on the 60k-row dataset".
- Decide what is measured: throughput or latency, which percentile, cold or warm, and what size of difference matters.
- Read the measurement script and note what it times, counts and ignores.
- Check the machine: load average, core count, power state. If it is busy and cannot be quieted, interleave the sides and say so.
- Use the ecosystem's own tool when it is installed (`hyperfine`, `pyperf`, `go test -bench` with `benchstat`, `criterion`), since it handles warmup and statistics.

## The questions

1. **What limits it?** Name the limiter with a profiler, CPU per process, I/O wait or syscall counts, in a run you do not report.
   Watch the load generator too: if it saturates first, you measured the load generator.
   If a change did not move the number, the limiter says why.
2. **Was each side tuned?** Run every side the way production runs it: release build, production flags, the same data and versions, caches as warm as production sees them.
   One side on defaults means you compared configurations.
   A limiter that is a setting (a commit per row, a debug build, a missing index) means that side is untuned: tune it and measure again before naming a winner.
3. **Did it break a limit?** Do the arithmetic against disk and network bandwidth, cores, and the share of time the changed part took.
   Removing a part that takes 10% of the run makes the run at most about 11% faster.
   A result past a limit measured a cache, a no-op or a bug.
4. **Did it error?** Count failures and check that outputs are correct and the same on every side, not merely present.
   Rejections are fast; timeouts and retries are slow.
5. **Does it reproduce?** At least five runs per side, alternating A, B, A, B so warmup, caches and drift favor neither.
   A gap smaller than the run-to-run spread is no measurable difference.
6. **Does it matter?** Next to a micro result, measure the path a user waits on with realistic sizes and concurrency, and give the micro result as a share of it.
7. **Did the work happen?** Confirm inside the timed region that the request arrived, the rows were written, the result was used.
   Lazy iterators, unawaited promises, discarded results and timeouts all produce numbers for work that never ran.
   Compare against an empty version of the program to see that the work is larger than startup cost.

For latency under load, send requests at a fixed rate and time each from its intended send time.
A loop that waits for each reply before sending the next hides the pauses.
Report the tail, not just the mean.

## Report

- Lead with the verdict: faster, slower, no measurable difference, or inconclusive.
- Give the number with its unit, the run count, the spread and the limiter:
  "p50 41 ms to 33 ms, median of 7 runs per side, range 32 to 35 ms after, bound by JSON parsing on one core".
- Include the exact command, the machine and whether the numbers are warm or cold.
- Never report from a single run or from means alone.
- The verdict is inconclusive when you cannot name the limiter, when a side ran untuned, or when questions 4 and 7 could not be checked. Name the gap.
