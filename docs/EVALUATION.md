# Evaluation proposal

Status: proposal. Nothing described here is built.

## What is and is not measured today

cma captures failures, surfaces matching ones before an action, logs each surfacing, and joins those logs into counts (`cma stats --evidence`, `--leaks`, `--recurrence`). Those counts are self-reported: a prevention is your note that a warning helped, and a miss is a failure you chose to record. They show that the loop runs. They do not show that surfacing a warning makes the same failure less likely to happen again, because there is no comparison against sessions where nothing was surfaced.

This document proposes the smallest experiment that would answer that question.

## Design

Run sessions with the Claude Code `PreToolUse` hook on or off, chosen at random when each session starts (a coin flip, recorded before any work happens). Strict alternation also works, but a coin flip avoids lining up with weekly patterns such as "Mondays are refactor days".

Hold everything else constant across both arms. In particular, the `SessionStart` hook also surfaces recurring failures, so either keep it off in both arms or on in both arms for the whole experiment.

## Outcome

The outcome is a **repeat**: a new miss whose `(surface, fm)` pair matches a miss that was captured before the session started. This is the same pairing `cma stats --leaks` already uses. The comparison is the repeat rate per session (or per 100 tool calls, if session length varies a lot) in the on arm versus the off arm.

Preventions are not the outcome. They are recorded only when a warning appeared, so the off arm cannot produce them and the comparison would be rigged.

## What to log

Most of the data already exists:

- `misses.jsonl`: timestamp, `surface`, `fm` for every captured failure.
- `surface_events.jsonl`: what was surfaced and when, in the on arm.

Three additions are needed, per session:

- a session id, start and end time, and the arm (`on` or `off`);
- the number of tool calls, as an exposure measure;
- in the off arm, a shadow record of what the hook would have surfaced (computed but not shown). Without it you cannot tell whether an off session ever touched a captured failure shape, and sessions that never touch one carry no information in either arm.

Claude Code passes a session id to hooks on stdin, so the hook is the natural place to write these records.

## How much data

Repeats are rare, so the sample has to be larger than intuition suggests. A rough guide for comparing two per-session rates at the usual thresholds (5% false-positive rate, 80% chance of detecting a real effect):

| Baseline repeats per session | Effect to detect | Sessions per arm |
|---|---|---|
| 0.3 | halved (0.3 to 0.15) | about 160 |
| 0.3 | cut by a third (0.3 to 0.2) | about 400 |
| 0.1 | halved (0.1 to 0.05) | about 470 |

Measure the baseline first: the off-arm repeat rate over the first 30 or so sessions tells you which row you are in. As a floor, do not read the result before both arms together contain at least 30 repeats; below that, one bad week decides the outcome. Count only sessions that touched a captured failure shape (from the surface events and shadow records), and analyze per session rather than per miss, since misses within one session are not independent.

## Threats to validity

- **Self-report.** Repeats are still misses you choose to record. If you know which arm a session is in, you may record more carefully in one of them. Mitigate by keeping the arm out of view during the session (the assistant sees the warnings; you need not), by deciding in advance what counts as a miss, and by reviewing captures for a session before revealing its arm.
- **Selection.** Only failures you noticed and captured can repeat. Shapes that are easy to notice will dominate the outcome, and failures you never recorded are invisible to both arms. Random assignment keeps this balanced between arms, but limits the result to the kinds of failure you capture.
- **Novelty.** Early on, the act of capturing failures makes you more careful in both arms, and repeat rates may fall for reasons unrelated to the hook. Run long enough to see the rates settle, and check whether the difference between arms holds in the second half on its own.
- **Contamination.** You remember warnings from on sessions during off sessions, and other memory (project notes, assistant memory files) can carry the same lessons. This biases the result toward no difference, so a positive finding is conservative; a null finding is weaker.
- **Scope.** Fewer repeats of captured shapes is not the same as better work. This experiment tests one link in the chain: whether surfacing a warning reduces the repeat it warns about.
