# cma

[![tests](https://github.com/lluvr/cma/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/lluvr/cma/actions/workflows/test.yml)
[![tests-mcp](https://github.com/lluvr/cma/actions/workflows/tests-mcp.yml/badge.svg?branch=main)](https://github.com/lluvr/cma/actions/workflows/tests-mcp.yml)
[![codeql](https://github.com/lluvr/cma/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/lluvr/cma/actions/workflows/codeql.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

Record a failure against the file where it happened. The next edit of that file can show it again, including the Instead line when you stored one. cma runs entirely on your machine. It records nothing until you capture it.

## What this is

cma stores failures, decisions, and ruled-out paths on your machine. With the Claude Code hook installed, the next edit of a file shows the captures that name that file. It does not watch the work and capture by itself. Whether a warning changes the next edit is unmeasured.

cma is methodology-agnostic. It stores the notes and stays out of the vocabulary you use to classify them. Pair it with whatever failure-mode catalog your practice already uses.

## Status

The commands `miss`, `decision`, `reject`, `prevented`, `surface`, `distill`, and `stats` store notes and can show a stored note on a later edit. A corrected note is shown as an Instead line. The numbers those commands print are counts of notes you recorded. Whether a warning changes the next edit is unmeasured. The test suite covers capture, surfacing, and the joins that produce those counts.

The command surface is specified in [DESIGN.md](docs/DESIGN.md).

## Quick start

**Requirements:** bash 3.2 or newer (Linux, macOS native, and Windows-WSL all work; the `cma` binary uses no bash 4+ features so macOS's system `/bin/bash` is sufficient), and `python3` 3.10 or newer. Python is used for JSON encoding and JSONL queries; it is a hard runtime dependency, not a package-manager dependency. CI exercises Python 3.10, 3.11, and 3.12.

Clone the repository and add the script to your `PATH`:

```bash
git clone https://github.com/lluvr/cma.git
mkdir -p ~/.local/bin
ln -s "$(pwd)/cma/cma" ~/.local/bin/cma   # or copy to anywhere on PATH
cma init                                   # create the data directory with a README
```

If `cma --version` reports "command not found", add `~/.local/bin` to your `PATH`.

In the examples below, `"<failure-shape>"` is a placeholder: replace it with your own tag, keeping the quotes.

Capture a failure:

```bash
cma miss "fix removed the error message instead of addressing the defect" \
    --surface infra --fm "<failure-shape>" \
    --files src/parser.py \
    --corrected "fix the defect the error was reporting"
```

For richer capture (texture preservation), add the situational fields:

```bash
cma miss "missed validation in middleware" \
    --surface auth --fm "<failure-shape>" \
    --intended "patch only the failing test" \
    --corrected "trace upstream defect, fix at root" \
    --excerpt-from /tmp/conversation-excerpt.txt
```

`--corrected` is shown on the next matching edit as an Instead line. `--intended` is kept for `cma stats --behavior` and is not shown on that edit. Surfacing matches that file's own name, then falls back to auth, payments, or db. A capture stored as `src/parser.py` surfaces for `parser.py`. A capture stored as `MyButton.tsx` does not surface for `Button.tsx`. A miss with no `--files` is not shown on the next edit of that file, unless the surface is one of those three. It does not match by situation. Two files that share a basename, in different projects, still share a note.

The `--fm` value is an opaque string from your perspective; cma stores it without interpretation. When using a methodology with a canonical failure-mode catalog, tag with the methodology's canonical names so analysis tooling can interpret them. cma is methodology-agnostic; the catalog and its meaning live in the methodology, not in cma.

Captures are written to `~/.cma/` as JSON Lines files (one record per line, append-only). The data directory can be overridden with `CMA_DIR=/path/to/data cma ...`. The full schema, atomicity guarantees, and migration policy are documented in [DATA.md](docs/DATA.md).

Run `cma --help` for the full command surface.

## The compound loop in four commands

cma is built on a chain: captured failures become surfaced warnings, surfaced warnings change what you do next, and the record of both can be computed over. cma does the capturing, the surfacing, and the computing. Whether the warnings change behavior is the part it does not yet measure: the numbers it reports are counts of what you recorded (see [What the numbers are](#what-the-numbers-are)). The full chain in one walkthrough:

```bash
# 1. Capture a failure so future similar work can see it.
cma miss "claimed verified without testing the cross-tenant path" \
    --surface auth --fm "<failure-shape>"

# 2. Show the auth notes. The PreToolUse hook does this for a file
#    whose basename matches, or for auth, payments, and db when that
#    file has no capture. Manual invocation works too.
cma surface --surface auth

# 3. The warning fires. If it changed what you did, record that
#    and link it to the original miss so cma can attribute it.
#    `cma id miss` returns the most recent miss id; use it to chain
#    without scrolling back through terminal output.
cma prevented "almost claimed verified again; ran the cross-tenant test instead" \
    --miss-id "$(cma id miss --surface auth)"

# 4. Read the evidence.
cma stats --evidence
#    Preventions captured:        1
#      of which linked to a miss: 1
#      of which evidenced:        1
#    Leaks:                       0
#    Loop closure rate:           100%  (1/1)
#      self-attested: 1 evidenced prevention(s) you recorded, 0 leak(s)
```

`cma stats --evidence --json` emits the structured record for downstream consumers.

### What the numbers are

Every number above is a count of records you wrote, or a rate computed from those counts.

- A **prevention** is your own report that a warning changed what you did. cma checks one thing about it: that the linked miss was actually surfaced between the miss and the prevention. A prevention with that surface event is counted as evidenced; one without it is still captured but stays out of the rate.
- A **leak** is a miss you captured after a warning for the same surface and failure mode had been surfaced.
- The **loop closure rate** is evidenced preventions divided by evidenced preventions plus leaks. It is self-reported, and the output labels it that way: it moves with what you choose to record, and it does not compare against what would have happened without the warning.

What works and is checked by the test suite: capture, action-time surfacing, the surface-event log, and the joins that produce these counts. What is not yet measured: whether surfaced warnings reduce repeat failures. [EVALUATION.md](docs/EVALUATION.md) specifies that comparison. `CMA_EVAL=1` records the arm and the off-arm shadow, and `cma eval status` counts repeats. It withholds the comparison until 30 repeats, and no such run has been scored.

## Action-time injection

The Claude Code hook shows a matching note when an edit or a shell command is about to run. It queries the file basename first, then auth, payments, or db if that file has no capture. Read and other tools stay silent. The five-stage layout is documented in [ARCHITECTURE.md](docs/ARCHITECTURE.md). Two reference integrations ship in this repository.

### Claude Code

Two hooks for Claude Code: a `PreToolUse` hook for per-action surfacing and a `SessionStart` hook for session-priming context.

**Per-action surfacing** (`hooks/claude-code-pre-tool-use.sh`): when Claude is about to use a tool that touches a file or runs a command, the hook queries `cma surface` by that file's name first. If the file has no capture, it falls back to a surface only for auth, payments, and db. A component, a markdown file, a route, or a test is not labeled as one shared bucket. It prints matched captures as a JSON object with `hookSpecificOutput.additionalContext`, the form Claude Code adds to the assistant's context for `PreToolUse` hooks. Silent for non-relevant tools (`Read`, etc.) and when no captures match; a surface event is logged only when captures were actually handed to the assistant.

**Session-priming context** (`hooks/claude-code-session-start.sh`): at the start of each session, surfaces recurring failure patterns and active rejections so the assistant has orientation before the first tool call. Configurable via `CMA_SESSION_START_SECTIONS` (default `recurrence,rejections`; set to `all` for `recurrence,rejections,behavior`).

Install both hooks with one command:

```bash
cma install-hook --claude-code
```

This merges the SessionStart and PreToolUse blocks into `~/.claude/settings.json` (or `./.claude/settings.json` with `--scope project`). It is idempotent, preserves any other hooks you have configured, and writes a backup of the prior file at `settings.json.bak`. Preview without writing via `--dry-run`.

Verify the per-action hook fires by feeding it the payload Claude Code would send (run from the directory you cloned into):

```bash
cma miss "example: skipped the token expiry check" --surface auth --files src/auth/login.ts
echo '{"tool_name":"Edit","tool_input":{"file_path":"src/auth/login.ts"}}' \
    | bash cma/hooks/claude-code-pre-tool-use.sh
# additionalContext starts with "Previous failures that matched this edit."
```

No output means no capture matched or `cma` is not on the `PATH` the hook sees. Then restart Claude Code so it picks up the new settings.

If you prefer to wire it manually, the JSON blocks the command produces look like:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash /path/to/cma/hooks/claude-code-session-start.sh"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash /path/to/cma/hooks/claude-code-pre-tool-use.sh"
          }
        ]
      }
    ]
  }
}
```

Together the two hooks cover both ends of the action-time injection theme: priming context at session start, relevant captures at each action.

### Shell (zsh, bash)

`hooks/cma-pre` is a wrapper for shell environments. It uses the same three surfaces as the Claude Code hook (auth, payments, db) and does not read a filename out of the command, so a miss stored only against a file is shown by the Claude hook and not by this wrapper.

**zsh** (native preexec). Add to `~/.zshrc`:

```bash
preexec() { /path/to/cma/hooks/cma-pre --check "$1"; }
```

**bash** (requires [bash-preexec](https://github.com/rcaloras/bash-preexec)):

```bash
source /path/to/bash-preexec.sh
preexec_functions+=("cma_pre_hook")
cma_pre_hook() { /path/to/cma/hooks/cma-pre --check "$1"; }
```

**Manual wrapping**:

```bash
/path/to/cma/hooks/cma-pre git commit -m "fix auth bug"
# Surfaces relevant captures, then runs the command
```

Triggers fire on commands likely to warrant surfacing: editors (`vim`, `nvim`, `emacs`, `code`, `subl`), version control (`git`), language toolchains (`npm`, `cargo`, `python`, `node`), and build tools (`make`, `gradle`, `mvn`). Override the trigger list with `CMA_PRE_TRIGGERS` (space-separated).

Failure isolation: if cma is missing, errors, or times out (default 5 seconds), the wrapped command still runs cleanly. The wrapper never blocks an action on its own failure.

Both integrations log surface events to `~/.cma/surface_events.jsonl`. `cma stats --leaks` later joins these events against subsequent misses to flag failures that occurred despite a relevant warning being surfaced. A leak shows where a warning did not prevent a repeat; the leak and prevention counts are self-reported and do not by themselves show that warnings prevent repeats (see [What the numbers are](#what-the-numbers-are)).

## MCP distribution (cma-mcp)

The bash CLI and shell hooks above cover Claude Code and any
shell environment. For builders reaching the same notes
through other MCP-compatible AI clients (Claude Desktop, Cursor,
Cline, Continue.dev), the same command ships as a
Python MCP server at [`cma-mcp/`](cma-mcp/). It is a subprocess
wrapper around this binary, keeps the methodology-agnostic
substrate intact, and preserves the three-section payload
discipline.

```bash
pip install cma-mcp
```

See [`cma-mcp/README.md`](cma-mcp/README.md) for the MCP-specific
quickstart and tool surface. The architectural decisions governing
the wrapper are recorded in [DECISIONS.md](docs/DECISIONS.md).

## Testing

```bash
./scripts/test.sh
```

Tests cover all capture verbs (normal and edge cases including special characters, missing arguments, unknown flags) and the operational verbs (`surface`, `distill`, `stats`).

## Methodology integration

cma is methodology-agnostic. The `--fm` field on captures is an opaque string; cma stores it without interpretation. When using a methodology with a canonical failure-mode catalog, tag with the methodology's canonical names. The methodology owns the vocabulary and its meaning; cma owns the data substrate.

For automatic classification at capture time, set `CMA_FM_CLASSIFIER` to a command that reads the description on stdin and emits the failure-mode tag on stdout:

```bash
export CMA_FM_CLASSIFIER=/path/to/your-classifier

cma miss "skipped verification before deploying"
# Classifier auto-tags the --fm value based on the description.
```

The classifier is external to cma; you provide the command. It can map descriptions to a specific methodology's catalog, or be generic. cma invokes it as an opaque command. Failure-isolated: if the classifier errors, is missing, or times out (5s), the capture proceeds without an `--fm` value. See [ARCHITECTURE.md Section 9](docs/ARCHITECTURE.md) for the full integration pattern.

## Architecture

cma's action-time injection layer follows a five-stage architecture (interception, context extraction, query, injection, logging). The pattern, reference implementations, data contracts, and validation framework are specified in [ARCHITECTURE.md](docs/ARCHITECTURE.md). Read it before writing a new integration; conform to its contracts so downstream analysis tooling stays consistent.

### Performance

docs/ARCHITECTURE.md Section 6 specifies <50ms typical latency for action-time injection. The `./scripts/bench.sh` harness measures each operation 100 times after 3 warmup runs against a synthetic 100-capture data set, and reports min / p50 / p95 / p99. The text run prints a table; `./scripts/bench.sh --json` emits a machine-readable record (operation name, percentile latencies, host kernel/CPU/filesystem, timestamp) suitable for tracking over time.

On commodity Linux and macOS the hot operations (`cma-pre --check`, `cma surface`, `cma stats` default summary) come in at p95 under 50ms. p99 is noisier and occasionally crosses the target on busy hosts; the architecture target is "typical" latency, not worst-case. Sub-50ms work is inherently sample-sensitive; re-run on the target host before citing numbers, and prefer the JSON output over a single text run.

## Roadmap

The 1.0 surface is locked (see [DESIGN.md](docs/DESIGN.md)) and all seven primitives are functional. Action-time injection ships for Claude Code (PreToolUse and SessionStart hooks) and for shell environments (zsh native preexec, bash via bash-preexec). Both follow the five-stage architecture in [ARCHITECTURE.md](docs/ARCHITECTURE.md).

Beyond 1.0: counterfactual capture analysis tooling, per-project data scoping, recency-weighted surface ranking. See [CHANGELOG.md](CHANGELOG.md) for the full pending list.

## License

Apache 2.0. See [LICENSE](LICENSE).

## Author

L. Lucic.
