# cma-mcp

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://pypi.org/project/cma-mcp/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)

The Model Context Protocol layer for cma, an executable compound
practice loop: capture failures, surface them at the moment of action,
track decisions and rejections, and check whether warnings actually
prevented repeats.

cma-mcp wraps the canonical `cma` command-line tool and exposes its
seven primitives to MCP-compatible AI clients. It does not reimplement
the loop; it shells out to the `cma` binary, so it never diverges from
the reference implementation.

## Status

cma-mcp 0.1.2 is the current release. `pip install cma-mcp` pulls it
from PyPI. The changelog is bundled with the wheel (`CHANGELOG.md`).

## What this is

Most MCP servers expose new capability. cma-mcp exposes an
existing capability (bash cma's seven primitives) to a wider set
of environments: Claude Desktop, Cursor, Cline,
Continue.dev, and any other MCP-compatible client. The contribution
is reach. Drift is the named enemy: cma-mcp invokes the canonical
bash cma binary as a subprocess for every captured action, so
cma-mcp picks up cma's evolution automatically and never diverges
from the 1.0 reference implementation.

## Quickstart

cma-mcp shells out to the `cma` command-line tool, so that binary must
be installed and on your `PATH` first. Confirm it:

    cma --help

Then install cma-mcp:

    pip install cma-mcp

The `cma-mcp` console script lands on PATH after install. Confirm:

    cma-mcp --version

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
is the same one Frame Check uses;
cma-mcp inherits it. Adversarial tests in
`tests/test_payload_determinism.py` pin the structure.

## Approach

**Subprocess over reimplementation.** cma-mcp invokes bash cma as
a subprocess for every captured action. cma-mcp does not
reimplement cma's seven primitives in Python; that is a deliberate
subprocess-over-reimplementation decision.

**Methodology-agnostic substrate.** cma stores `--fm` (failure
mode) as an opaque string. cma-mcp does not bundle any
methodology's failure-mode catalog. You tag captures with
your methodology's vocabulary (Lodestone's FM-1..10 or otherwise)
by passing the tag through; for autoclassification, set
`CMA_FM_CLASSIFIER` per cma's plugin convention.

**No external runtime dependencies.** cma-mcp implements MCP
directly in-repo using JSON-RPC 2.0 over stdio. No third-party MCP
SDK; no pip-installed runtime requirements beyond the Python
standard library. (Test-time deps: pytest.)

## Platform support

Linux and macOS native. On Windows, run cma-mcp under WSL
because cma-mcp shells out to the bash cma binary. Routing every
tool call through the same canonical binary on every platform is
how cma-mcp avoids drift; a parallel Python implementation would
require keeping two surface definitions in sync forever. If you
run an MCP-compatible AI client on Windows, you likely already
have WSL available.

## Install fingerprint

    cma-mcp --version

Emits a one-line JSON fingerprint with `server_version`,
`protocol_version`, `git_sha` (with `+dirty` flag if the working
tree has uncommitted changes), `cma_binary_version` (probed from
`cma --version`), `python` version, and `script` path. Lets you
confirm the cma-mcp install configured in your MCP
client is the expected one.

## Offline sanity check

    cma-mcp --test

Prints the full three-section payload for a `cma_stats` (default
view) call against your `~/.cma/` data. Useful to verify
pipeline wiring and that the cma binary is reachable.

## Documentation

Bundled with the wheel:

- `CHANGELOG.md`: cma-mcp release history
- `docs/MCP_SERVER.md`: protocol reference
- `docs/ARCHITECTURE.md`: module layout, data flow, contracts
- `docs/FAQ.md`: conceptual questions, install gotchas, cross-client config
- `docs/TROUBLESHOOTING.md`: symptoms and fixes
- `LICENSE` (Apache-2.0), `NOTICE`, `CITATION.cff`

## Running tests

From this directory:

    pip install -e .[test]
    python3 -m pytest -q

The suite covers MCP protocol conformance, three-section payload
determinism, JSONL parsing tolerance, and subprocess-wrapper
isolation (argv-array discipline, timeout discipline). Tests that
require the bash cma binary skip when it is not on `PATH`.

## Issues

Bug reports, feature requests, and security reports: `hello@clarethium.com`.
