# cma-mcp

[![tests-mcp](https://github.com/Clarethium/cma/actions/workflows/tests-mcp.yml/badge.svg?branch=main)](https://github.com/Clarethium/cma/actions/workflows/tests-mcp.yml)
[![codeql](https://github.com/Clarethium/cma/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/Clarethium/cma/actions/workflows/codeql.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://pypi.org/project/cma-mcp/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](https://github.com/Clarethium/cma/blob/main/LICENSE)
[![Companions](https://img.shields.io/badge/org-Clarethium-blue.svg)](https://github.com/Clarethium)

The Model Context Protocol distribution layer for [cma](https://github.com/Clarethium/cma#readme),
Clarethium's executable compound practice loop.

## Where this lives

cma-mcp is one component of the [cma project](https://github.com/Clarethium/cma).
The repository root holds the canonical bash cma reference
implementation; this `cma-mcp/` subdirectory holds the Python
wrapper that exposes the same loop to MCP-compatible AI clients.
The two components release independently:

- **bash cma**: see the [parent README](https://github.com/Clarethium/cma#readme) for the CLI
  surface, install, and Claude Code / shell hook integrations.
- **cma-mcp**: this README, focused on the PyPI installation and
  MCP client configuration.

Cross-cutting governance (license, citation, security, strategy,
contribution) lives at the repository root.

## What this is

Most MCP servers expose new capability. cma-mcp exposes an
existing capability (bash cma's seven primitives) to a wider set
of operator environments: Claude Desktop, Cursor, Cline,
Continue.dev, and any other MCP-compatible client. The contribution
is reach. Drift is the named enemy: cma-mcp invokes the canonical
bash cma binary as a subprocess for every captured action, so
cma-mcp picks up cma's evolution automatically and never diverges
from the 1.0 reference implementation.

## Quickstart

cma-mcp wraps the canonical bash cma binary. Install bash cma first
from the [parent repository](https://github.com/Clarethium/cma#readme), then confirm it is on
`PATH`:

    cma --help

Install cma-mcp from PyPI:

    pip install cma-mcp

Point your MCP client at the installed entry point. For Claude
Desktop, add to `claude_desktop_config.json`:

    {
      "mcpServers": {
        "cma": {
          "command": "cma-mcp"
        }
      }
    }

Restart the client. Then in any conversation: *"Record a miss: I
claimed verified without testing the cross-tenant write path"*, or
*"What active rejections do I have?"*, or *"What does cma stats
show for prevention/miss ratio over the last 30 days?"*

For Cursor, Cline, Continue.dev, and other MCP-compatible clients,
the same pattern applies (point the client at the `cma-mcp`
command; the stdio handshake runs).

## What it exposes

**Seven tools** mirroring bash cma's seven primitives:

| Tool | Wraps | When the agent invokes it |
|---|---|---|
| `cma_miss` | `cma miss` | A failure happened that may recur |
| `cma_decision` | `cma decision` | A non-trivial architectural choice was made |
| `cma_reject` | `cma reject` | An option was eliminated and should not be silently rebuilt |
| `cma_prevented` | `cma prevented` | A surfaced warning actually changed behavior |
| `cma_distill` | `cma distill` (modes: default / retire / review) | Promote, retire, or preview a distilled learning |
| `cma_surface` | `cma surface` | Pull relevant prior captures before acting (logs surface event for leak detection) |
| `cma_stats` | `cma stats` (views: default / leaks / recurrence / preventions / rejections / behavior) | Inspect loop-closing evidence |

**Four resources** for read-only context:

| URI | Reads |
|---|---|
| `cma://decisions` | Active decisions in the last 180 days |
| `cma://rejections` | Active rejections in the last 30 days |
| `cma://core` | Active core learnings (retired filtered) |
| `cma://stats` | Default stats summary |

## Three-section payload

Every tool response and resource read returns a JSON payload with
three top-level sections:

    {
      "analysis":       { ... data and stdout },
      "agent_guidance": { what to tell the user, how to cite },
      "provenance":     { server_version, license, cost: 0.0, ... }
    }

The `agent_guidance` and `provenance` sections exist because an
agent passing cma-mcp output to a user without attribution would
strip the reproducibility that makes the loop's evidence worth
citing. Surfacing "how to cite faithfully" inside the payload is
the structure that carries that integrity forward. This convention
is established by [frame-check-mcp](https://github.com/Clarethium/frame-check-mcp);
cma-mcp inherits it. Adversarial tests in
`tests/test_payload_determinism.py` pin the structure.

## Approach

**Subprocess over reimplementation.** cma-mcp invokes bash cma as
a subprocess for every captured action. cma-mcp does not
reimplement cma's seven primitives in Python. See
[DECISIONS.md](https://github.com/Clarethium/cma/blob/main/DECISIONS.md) AD-001 for the rationale.

**Methodology-agnostic substrate.** cma stores `--fm` (failure
mode) as an opaque string. cma-mcp does not bundle any
methodology's failure-mode catalog. Operators tag captures with
their methodology's vocabulary (Lodestone's FM-1..10 or otherwise)
by passing the tag through; for autoclassification, set
`CMA_FM_CLASSIFIER` per cma's plugin convention.

**No external runtime dependencies.** cma-mcp implements MCP
directly in-repo using JSON-RPC 2.0 over stdio. No third-party MCP
SDK; no pip-installed runtime requirements beyond the Python
standard library. (Test-time deps: pytest.)

## Platform support

Linux and macOS native. Windows operators run cma-mcp under WSL
because cma-mcp shells out to the bash cma binary. This is
deliberate (project notes DD-3): canonical-cma
alignment beats standalone Python reach. Any operator running an
MCP-compatible AI client on Windows is reasonably expected to have
WSL available.

## Install fingerprint

    cma-mcp --version

Emits a one-line JSON fingerprint with `server_version`,
`protocol_version`, `git_sha` (with `+dirty` flag if the working
tree has uncommitted changes), `cma_binary_version` (probed from
`cma --version`), `python` version, and `script` path. Lets an
operator confirm the cma-mcp install configured in their MCP
client is the expected one.

## Offline sanity check

    cma-mcp --test

Prints the full three-section payload for a `cma_stats` (default
view) call against the operator's `~/.cma/` data. Useful to verify
pipeline wiring and that the cma binary is reachable.

## Documentation

Project-level (repository root):

- [README.md](https://github.com/Clarethium/cma#readme): cma's CLI overview
- project notes: durable decisions
- [DECISIONS.md](https://github.com/Clarethium/cma/blob/main/DECISIONS.md): architectural decisions log
- [GOVERNANCE.md](https://github.com/Clarethium/cma/blob/main/GOVERNANCE.md): BDFL governance, named curator
- [CONTRIBUTING.md](https://github.com/Clarethium/cma/blob/main/CONTRIBUTING.md): contribution mechanics, DCO sign-off
- [SECURITY.md](https://github.com/Clarethium/cma/blob/main/SECURITY.md): threat model and reporting
- [LICENSE](https://github.com/Clarethium/cma/blob/main/LICENSE) (Apache-2.0), [NOTICE](https://github.com/Clarethium/cma/blob/main/NOTICE), [CITATION.cff](https://github.com/Clarethium/cma/blob/main/CITATION.cff)

cma-mcp specific (this directory):

- [CHANGELOG.md](CHANGELOG.md): cma-mcp release history
- [docs/MCP_SERVER.md](docs/MCP_SERVER.md): protocol reference
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): module layout, data
  flow, contracts; reading map for new contributors
- [docs/FAQ.md](docs/FAQ.md): conceptual questions, install gotchas,
  cross-client config patterns
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md): symptoms and
  fixes; the diagnostic loop is the four-command sequence at the top
- [docs/ANTICIPATED_CRITIQUES.md](docs/ANTICIPATED_CRITIQUES.md):
  self-enumerated adversarial readings of cma-mcp's design
- [docs/VALIDATION_PROGRAM.md](docs/VALIDATION_PROGRAM.md): empirical
  validation plan for whether the loop closes through MCP exposure

## Running tests

From this directory:

    pip install -e .[test]
    python3 -m pytest -q

The suite covers MCP protocol conformance, three-section payload
determinism, JSONL parsing tolerance, and subprocess-wrapper
isolation (argv-array discipline, timeout discipline). Tests that
require the bash cma binary skip when it is not on `PATH`.

## Issues

Bug reports and feature requests at
[github.com/Clarethium/cma/issues](https://github.com/Clarethium/cma/issues).
Use the `cma-mcp` label or include `[cma-mcp]` in the title to
disambiguate from bash cma issues.

Security issues go to `hello@clarethium.com` per
[SECURITY.md](https://github.com/Clarethium/cma/blob/main/SECURITY.md).
