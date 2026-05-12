# cma-mcp Server Reference

This document is the authoritative reference for cma-mcp's MCP
protocol surface: the initialize handshake, tools/list, tools/call,
resources/list, resources/read, ping, and notifications. It covers
the request and response shapes a client sees.

For the rationale behind these choices, see [`DECISIONS.md`](../../DECISIONS.md)
at the repository root.

## Transport

Stdio. Each line on stdin is one JSON-RPC 2.0 request or
notification; each response is one line on stdout. Stderr is
reserved for cma-mcp's logs (timestamp + level + key=value); MCP
protocol traffic never touches stderr.

## Initialize handshake

Request:

    {
      "jsonrpc": "2.0",
      "id": 1,
      "method": "initialize",
      "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "claude-desktop", "version": "1.x"}
      }
    }

Response:

    {
      "jsonrpc": "2.0",
      "id": 1,
      "result": {
        "protocolVersion": "2024-11-05",
        "capabilities": {
          "tools":     {"listChanged": false},
          "resources": {"listChanged": false, "subscribe": false}
        },
        "serverInfo": {"name": "cma-mcp", "version": "0.1.0"},
        "instructions": "cma-mcp distributes the cma compound practice loop ..."
      }
    }

The `instructions` field carries cross-tool orientation prose for
agents and for MCP clients whose UI surfaces the field. Names the
use case, the default invocation pattern, and the methodology-canon
boundary (Lodestone owns vocabulary; cma stores `--fm` opaque).

## Tools

`tools/list` returns seven tools. Each tool definition has
`name`, `title`, `description`, and `inputSchema`. The full schema
shapes are in `mcp_schema.py`.

### Common shapes

All tool results have `content` (a one-element array of `{type:
"text", text: <stringified JSON>}`) and `isError` (boolean).

The text payload is always a three-section JSON document:

    {
      "analysis":       { ... },
      "agent_guidance": { ... },
      "provenance":     { ... }
    }

`isError` is true when the analysis block carries an error (cma
binary missing, subprocess timeout, validation failure on a
required field). The error detail and reason are inside
`analysis.error` / `analysis.reason` / `analysis.detail`.

### Surface labels

The seven tools accept `surface` as an optional `string` parameter
(min 2, max 20 chars). cma's data substrate stores it as an opaque
label. Canonical examples used by the bash cma reference
implementation: `auth`, `db`, `docs`, `ui`, `infra`, `general`,
`git`. Custom values are accepted (e.g., `test`, `ml`, `frontend`,
`mobile`, `ops`). cma-mcp does not enforce a closed enum.

### Failure-mode tags (`fm`)

`cma_miss` and `cma_prevented` accept `fm` as an optional opaque
string. cma-mcp does not bundle Lodestone's FM-1..10 catalog
(DECISIONS AD-006); operators using a methodology with a canonical
catalog (such as Lodestone) pass that methodology's tag here.
Operators who want autoclassification at capture time wire the
`CMA_FM_CLASSIFIER` plugin per cma's CLI convention; cma-mcp
inherits the wiring transparently.

### Tool list

| Tool | Required params | Optional params |
|---|---|---|
| `cma_miss` | `description` (string, min 8) | `surface`, `fm`, `files`, `intended`, `corrected`, `excerpt` |
| `cma_decision` | `description` (string, min 15) | `surface`, `applies_when` |
| `cma_reject` | `description` (string, min 8) | `surface`, `revisit_when` |
| `cma_prevented` | `description` (string, min 8) | `miss_id`, `warning_id` |
| `cma_distill` | `mode` (enum: default / retire / review) | `description` (mode=default), `pattern` (mode=retire), `scope`, `surface` |
| `cma_surface` | (none) | `surface`, `file`, `type`, `limit` (int 1..50) |
| `cma_stats` | (none) | `view` (enum: default / leaks / recurrence / preventions / rejections / behavior) |

## Resources

`resources/list` returns four resources:

| URI | mimeType | Lookback | Scope |
|---|---|---|---|
| `cma://decisions` | application/json | 180 days | All projects (cma 1.0 is single-project) |
| `cma://rejections` | application/json | 30 days | All projects |
| `cma://core` | application/json | indefinite | All scopes; retired filtered |
| `cma://stats` | application/json | per-view | All projects |

`resources/read` returns the same three-section JSON shape as tool
calls, wrapped in `contents[0].text`.

The `analysis.records` array on `cma://decisions`, `cma://rejections`,
and `cma://core` carries raw JSONL records as cma wrote them. The
`provenance.data_source` block reports parse outcomes:

    "data_source": {
      "file": "/home/.../misses.jsonl",
      "exists": true,
      "records_parsed": 200,
      "corrupt_lines_skipped": 0,
      "legacy_records_no_schema_version": 12,
      "unknown_schema_versions": []
    }

## Error envelope

JSON-RPC 2.0 errors. Standard codes:

| Code | Meaning |
|---|---|
| -32700 | Parse error (malformed JSON) |
| -32600 | Invalid request (not a JSON-RPC 2.0 envelope) |
| -32601 | Method not found |
| -32602 | Invalid params |
| -32603 | Internal error |

MCP-specific:

| Code | Meaning |
|---|---|
| -32002 | Resource not found |

When a tool dispatch produces a logical error (cma binary missing,
subprocess timeout, invalid argument), the response is a normal
`tools/call` result with `isError: true` rather than a JSON-RPC
error envelope. This matches the MCP spec recommendation: protocol
errors are for protocol violations; tool errors live in the tool's
content.

## Pinned conformance

`tests/test_mcp_server.py` and `tests/test_payload_determinism.py`
pin the surface contracts. The following are breaking changes that
require a CHANGELOG entry and a major or minor SERVER_VERSION bump:

- Tool name added or removed
- Tool input schema changes (added required field, removed field,
  changed type)
- Resource URI added or removed
- Three top-level payload sections changed in name or required
  presence
- Provenance dropped any of: `server_name`, `server_version`,
  `protocol_version`, `license`, `cost_usd`, `citation`,
  `deterministic`, `timestamp`
- isError semantics for any tool

Server version follows semver:

- patch: bug fix, no schema change
- minor: new optional field in tool responses, new tool/resource
- major: any item from the breaking-changes list above

## Install fingerprint (`--version`)

`cma-mcp --version` emits one JSON line with:

    {
      "server_name": "cma-mcp",
      "server_version": "0.1.0",
      "protocol_version": "2024-11-05",
      "git_sha": "abc12345" or "abc12345+dirty" or null,
      "cma_binary_version": "<output of cma --version>" or null,
      "python": "3.12.3",
      "script": "/abs/path/to/cma-mcp/mcp_server.py"
    }

`cma_binary_version` is null when cma is not on `PATH` or
`cma --version` returns non-zero. The MCP server still runs in that
case; tool calls that need cma fail with a structured error.
