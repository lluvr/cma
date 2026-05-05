# cma

Executable compound practice loop. The terminal-side companion to [Lodestone](https://github.com/Clarethium/lodestone).

## What this is

cma is the operator's tool for running the compound practice loop on the local machine. It captures failures, surfaces warnings at the moment of action, tracks decisions, and detects recurrence patterns. It is the executable instantiation of the practice defined in Lodestone.

The methodology lives in Lodestone. cma is what running that methodology looks like in a terminal.

## Status

cma 1.0 reference implementation. All seven primitives fully functional: `cma miss`, `cma decision`, `cma reject`, `cma prevented`, `cma surface`, `cma distill` (default + `--review` + `--retire`), and `cma stats` (default + `--rejections` + `--preventions` + `--recurrence` + `--leaks`). Test suite (55 cases) covers functional paths, edge cases, JSON validity, and the leak-detection join.

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

## Action-time injection (Claude Code)

cma includes a PreToolUse hook for Claude Code in [`hooks/claude-code-pre-tool-use.sh`](hooks/claude-code-pre-tool-use.sh). When Claude is about to edit a file or run a command, the hook surfaces relevant prior captures automatically — the surfacing step of the compound loop without manual `cma surface` invocation.

Install:

1. Ensure `cma` is on your `PATH` (see Quick start above).
2. Add a hook entry to `~/.claude/settings.json`:

```json
{
  "hooks": {
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

The hook detects the relevant surface heuristically from the file path or command (`auth`, `payments`, `db`, `api`, `ui`, `docs`, `test`), then queries `cma surface --surface <s>` for matching captures. Output goes to the assistant's context. Non-matching tool calls and tools that don't touch files are silent.

Every fire is logged as a surface event, so `cma stats --leaks` can later flag failures that occurred despite a relevant warning being surfaced — the closing step of the compound loop turning into evidence.

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

## Roadmap

The 1.0 surface is locked (see [DESIGN.md](DESIGN.md)) and all seven primitives are functional. Action-time injection is implemented for Claude Code (see [Action-time injection](#action-time-injection-claude-code) above), with a shell wrapper integration in development per the architecture in [ARCHITECTURE.md](ARCHITECTURE.md).

Beyond 1.0: shell wrapper (zsh, bash with bash-preexec) for non-AI-client operators, counterfactual capture analysis tooling, per-project data scoping, recency-weighted surface ranking. See [CHANGELOG.md](CHANGELOG.md) for the full pending list.

## License

Apache 2.0. See [LICENSE](LICENSE).

## Author

L. Lucic. Published under Clarethium.
