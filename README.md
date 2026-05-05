# cma

Executable compound practice loop. The terminal-side companion to [Lodestone](https://github.com/Clarethium/lodestone).

## What this is

cma is the operator's tool for running the compound practice loop on the local machine. It captures failures, surfaces warnings at the moment of action, tracks decisions, and detects recurrence patterns. It is the executable instantiation of the practice defined in Lodestone.

The methodology lives in Lodestone. cma is what running that methodology looks like in a terminal.

## Status

cma 1.0 reference implementation. All seven primitives fully functional: `cma miss`, `cma decision`, `cma reject`, `cma prevented`, `cma surface`, `cma distill` (default + `--review` + `--retire`), and `cma stats` (default + `--rejections` + `--preventions` + `--recurrence` + `--leaks` + `--behavior`). Action-time injection (Claude Code hook + shell wrapper). Texture preservation on misses. Test suite (77 cases) covers functional paths, edge cases, JSON validity, the leak-detection join, hook integration, and shell wrapper modes.

The full surface is specified in [DESIGN.md](DESIGN.md). Additive features (action-time injection, texture preservation, counterfactual capture, recurrence detection) layer on without changing the locked surface.

## Quick start

Clone the repository and add the script to your `PATH`:

```bash
git clone https://github.com/Clarethium/cma.git
ln -s "$(pwd)/cma/cma" ~/.local/bin/cma   # or copy to anywhere on PATH
```

Capture a failure:

```bash
cma miss "fix removed the error message instead of addressing the defect" \
    --surface infra --fm speed-over-understanding
```

For richer capture (texture preservation), add the situational fields:

```bash
cma miss "missed JWT expiration in middleware" \
    --surface auth --fm assumption-over-verification \
    --intended "patch only the failing test" \
    --corrected "trace upstream defect, fix at root" \
    --excerpt-from /tmp/conversation-excerpt.txt
```

The texture fields (`--excerpt`, `--intended`, `--corrected`) preserve the conditions of the failure so future surfacing can match by situation, not just keywords.

Captures are written to `~/.cma/` as JSON Lines files (one record per line, append-only). The data directory can be overridden with `CMA_DIR=/path/to/data cma ...`.

Run `cma --help` for the full command surface.

## Action-time injection

cma surfaces relevant prior captures automatically when an operator (or AI assistant) is about to act. The five-stage architecture (interception, context extraction, query, injection, logging) is documented in [ARCHITECTURE.md](ARCHITECTURE.md). Two reference integrations ship in this repository.

### Claude Code

Two hooks for Claude Code: a `PreToolUse` hook for per-action surfacing and a `SessionStart` hook for session-priming context.

**Per-action surfacing** (`hooks/claude-code-pre-tool-use.sh`): when Claude is about to use a tool that touches a file or runs a command, the hook detects surface heuristically from the tool input, queries `cma surface`, and writes matched captures to stdout. Claude Code injects them as additional context. Silent for non-relevant tools (`Read`, etc.) and when no captures match.

**Session-priming context** (`hooks/claude-code-session-start.sh`): at the start of each session, surfaces recurring failure patterns and active rejections so the assistant has orientation before the first tool call. Configurable via `CMA_SESSION_START_SECTIONS` (default `recurrence,rejections`; set to `all` for `recurrence,rejections,behavior`).

Install both:

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

`hooks/cma-pre` is a wrapper for shell environments. Surface detection uses the same heuristics as the Claude Code hook, so behavior is consistent across integrations.

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

Both integrations log surface events to `~/.cma/surface_events.jsonl`. `cma stats --leaks` later joins these events against subsequent misses to flag failures that occurred despite a relevant warning being surfaced — the validation evidence that the loop closes.

## Testing

```bash
./test.sh
```

Tests cover all capture verbs (normal and edge cases including special characters, missing arguments, unknown flags) and the operational-verb stubs.

## The Clarethium body

cma sits alongside three reference artifacts published by Clarethium:

- **Touchstone** validates work against quality standards.
- **Whetstone** sharpens craft.
- **Lodestone** orients practice.

cma is the executable companion to Lodestone. The doctrine is in Lodestone; the running code is here.

## Architecture

cma's action-time injection layer follows a five-stage architecture (interception, context extraction, query, injection, logging). The pattern, reference implementations, data contracts, and validation framework are specified in [ARCHITECTURE.md](ARCHITECTURE.md). Read it before writing a new integration; conform to its contracts so downstream analysis tooling stays consistent.

### Performance

ARCHITECTURE.md Section 6 specifies <50ms typical latency for action-time injection. Measured against a synthetic 100-capture data set (`./bench.sh`):

| Operation | Median | p95 |
|-----------|--------|-----|
| `cma-pre --check` (no match) | 6ms | 10ms |
| `cma-pre --check` (matched surface) | 36ms | 43ms |
| `cma surface --surface <s>` | 27ms | 31ms |
| `cma stats --recurrence` | 26ms | 31ms |
| `cma stats` (default summary) | 8ms | 9ms |

All operations stay under the 50ms target at p95. Cold-start invocations (first call in a fresh shell) may run higher; the wrapper warms up after a few hooks fire.

## Roadmap

The 1.0 surface is locked (see [DESIGN.md](DESIGN.md)) and all seven primitives are functional. Action-time injection is implemented for Claude Code (see [Action-time injection](#action-time-injection-claude-code) above), with a shell wrapper integration in development per the architecture in [ARCHITECTURE.md](ARCHITECTURE.md).

Beyond 1.0: shell wrapper (zsh, bash with bash-preexec) for non-AI-client operators, counterfactual capture analysis tooling, per-project data scoping, recency-weighted surface ranking. See [CHANGELOG.md](CHANGELOG.md) for the full pending list.

## License

Apache 2.0. See [LICENSE](LICENSE).

## Author

L. Lucic. Published under Clarethium.
