# cma-mcp FAQ

Common questions about cma-mcp, ordered roughly by where operators
hit them in setup. For symptoms-and-fixes, see
[`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).

---

## Conceptual

### What does cma-mcp give me that bash cma doesn't?

Reach. Bash cma already integrates with Claude Code (via the
PreToolUse and SessionStart hooks) and with shell environments
(zsh native preexec, bash via bash-preexec). cma-mcp brings the same
seven primitives to MCP-compatible AI clients that have no shell
hook surface: Claude Desktop, Cursor, Cline, Continue.dev, and
others. The contribution is which audiences can run the loop, not
new loop semantics. STRATEGY DD-1.

### Does cma-mcp add LLM cost?

No. cma-mcp is a deterministic subprocess wrapper. Every response
carries `provenance.cost_usd: 0.0` and `provenance.deterministic:
true`. The agent that calls cma-mcp is the only LLM in the path,
and it pays its own normal token cost; cma-mcp does not call any
model.

### Where does my data live?

In `~/.cma/` (the canonical location used by bash cma). cma-mcp
never owns or relocates data; it shells out to bash cma which writes
to the operator's `~/.cma/` per its DATA.md schema. On WSL, that is
the WSL home (`/home/<user>/.cma/`), not the Windows side.

The operator can override via `CMA_DIR=/some/other/path` and bash
cma honors it — cma-mcp passes the env through subprocess
inheritance.

### Is cma-mcp methodology-specific?

No. cma stores `--fm` as an opaque string. Operators using
[Lodestone](https://github.com/Clarethium/lodestone) tag captures
with FM-1..10; operators using a different methodology tag with
that catalog. cma-mcp does not validate, expand, or interpret the
tag. Tool descriptions reference Lodestone as the canonical
methodology but bundle no vocabulary. STRATEGY DD-4.

---

## Install

### Do I need bash cma installed before installing cma-mcp?

Yes. cma-mcp wraps the canonical bash cma binary as a subprocess.
On startup, every tool call invokes `cma <verb> ...`. Without the
binary on `PATH`, every call returns `isError: true` with
`reason: missing_binary`. Install bash cma first per the
[parent README](https://github.com/Clarethium/cma#readme), then
`pip install cma-mcp`.

### Where do I put the MCP client config?

| Client | Config path | Block name |
|---|---|---|
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS), `%APPDATA%\Claude\claude_desktop_config.json` (Windows) | `mcpServers.cma` |
| Cursor | `~/.cursor/mcp.json` (or via Cursor settings UI) | `mcpServers.cma` |
| Cline | VS Code settings UI → Cline → MCP servers | `cma` |
| Continue.dev | `~/.continue/config.json` | `mcpServers.cma` |

The block content is the same across clients — point at the
installed `cma-mcp` entry point:

```
{
  "mcpServers": {
    "cma": {
      "command": "cma-mcp"
    }
  }
}
```

### Can I run cma-mcp without a virtualenv (`pipx install`, etc.)?

Yes. `pipx install cma-mcp` puts `cma-mcp` on the user-level PATH
and the MCP client config above works unchanged. `uv tool install
cma-mcp` works the same way. The wheel ships the `cma-mcp` console
script as the only entry point.

### Why isn't there a Windows-native install?

bash cma is the canonical implementation and uses `/bin/bash`.
Windows operators run cma-mcp under WSL, which gives them the same
binary on `PATH`. STRATEGY DD-3 documents the platform stance.
Operators on a pure Windows host with no WSL cannot run cma-mcp
today; that is the deliberate trade-off between canonical-binary
alignment and standalone Python reach.

---

## Operation

### How do I know cma-mcp is wired up correctly?

Run `cma-mcp --version` directly in a terminal. It emits a one-line
JSON fingerprint with `server_version`, `protocol_version`,
`git_sha`, `cma_binary_version`, `python` version, and `script`
path. If `cma_binary_version` is `null`, bash cma is missing or
silent — fix that first.

For a deeper check, run `cma-mcp --test`. It emits a full
three-section payload for `cma_stats` (default view) against your
real `~/.cma/` corpus — the same shape an MCP client would see for
that tool call, without needing to spin up a client.

### Why does my agent paraphrase cma's output instead of quoting it?

The agent guidance section of every payload includes
`how_to_cite_faithfully`: a one-line instruction telling the agent
exactly how to quote without smoothing the numbers. If the agent
still paraphrases, surface the issue with the agent's prompt
configuration rather than cma-mcp's payload — the discipline lives
in the agent's reading, not in the wire format.

### Can I use cma-mcp and the bash hooks at the same time?

Yes. They are independent integration paths over the same
underlying corpus (`~/.cma/*.jsonl`). The PreToolUse hook in Claude
Code surfaces priming context before tool calls; cma-mcp tools
surface or capture on demand from any MCP-compatible client. Both
write through bash cma's atomic-write discipline — captures from
either path interleave correctly.

### How fast is each MCP call?

Lightweight calls (ping, tools/list, resources/list) round-trip in
under 5ms. Subprocess-bound calls inherit bash cma's latency:
~50ms for `cma_stats` (default), ~5–15ms for `cma_surface` and
`cma_miss`. Run `python3 bench.py` from the cma-mcp directory for
numbers against your machine. The MCP wrapper itself adds
essentially zero overhead.

### Is the schema stable across releases?

The three-section payload contract (`analysis` + `agent_guidance` +
`provenance`) is stable across cma-mcp 0.x. Tool argument schemas
are stable within a major version (`SERVER_VERSION` — see
`mcp_server.py`). bash cma's JSONL data schema is stable across
the `1.0` line per its DATA.md. Schema changes that are not
backwards-compatible bump the relevant major version explicitly.

---

## Limits

### What's not in cma-mcp 0.1?

- **Wire-protocol fuzzing.** v0.1 ships subprocess roundtrip tests
  (`tests/test_mcp_wire.py`); broader fuzzing of the JSON-RPC
  parser is a v0.2 target.
- **Structured stdout parsing** for capture verbs. cma-mcp passes
  `cma_stdout` through unchanged; v0.2 may extract structured
  records from verbs whose output format is stable. ANTICIPATED_
  CRITIQUES C-5.
- **Cancellation / progress notifications.** cma calls are
  sub-second; the MCP cancellation surface and `progress`
  notifications are out of scope for the current call shape.
- **Native Windows install.** WSL is the documented path.

### Does cma-mcp validate that captures are well-formed?

It validates the MCP-side input schema (every argument's type per
the `inputSchema` in `mcp_schema.py`) and surfaces validation
errors as `isError: true` with reason. It does not enforce
methodology rules (which `--fm` values are legal, what shapes a
"good" miss has). That belongs in the methodology layer
(Lodestone), not the substrate. STRATEGY DD-4.

### What happens if cma writes to a corrupted JSONL line?

Resource reads use a tolerant parser
(`cma_jsonl.read_jsonl`) that skips malformed lines and counts the
parse failures. The count surfaces in
`provenance.data_source.parse_failures` so the caller knows what
the trust signal is. This matches bash cma's own tolerant-read
discipline. ANTICIPATED_CRITIQUES C-9.

---

## Citation

### How do I cite cma-mcp?

Every response carries `provenance.citation`:

> `cma-mcp 0.1.0 (Clarethium, 2026). https://github.com/Clarethium/cma/tree/main/cma-mcp`

Also in `CITATION.cff` at the repository root and in the project's
PyPI metadata. Once a Zenodo DOI is allocated, the citation will
include it.

### Can I publish a paper using cma-mcp?

Yes; the project is Apache-2.0 licensed and the methodology canon
(Lodestone) is CC-BY-4.0. Cite cma-mcp via the field above and
Lodestone separately if you reference its vocabulary.

---

## Where things live

- **Operator-facing reference:** [`MCP_SERVER.md`](MCP_SERVER.md) —
  every tool argument, every resource URI, the exact response
  shapes.
- **Architecture map:** [`ARCHITECTURE.md`](ARCHITECTURE.md) —
  module layout, data flow, contracts.
- **Validation plan:** [`VALIDATION_PROGRAM.md`](VALIDATION_PROGRAM.md) —
  what claims this project makes and how they are tested.
- **Self-criticism:** [`ANTICIPATED_CRITIQUES.md`](ANTICIPATED_CRITIQUES.md) —
  the strongest readings against the design, named openly with
  positions and trade-offs.
- **Symptoms and fixes:** [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).
