# cma-mcp Architecture

This document is the orientation map for cma-mcp: how the modules fit
together, where the contracts live, and which structural decisions
hold the design in place. New contributors should read this before
editing code; reviewers should use it as the diff-against-claim
when evaluating changes.

For the protocol surface (every tool argument, every resource URI),
see [`MCP_SERVER.md`](MCP_SERVER.md). For the architectural
decisions that shaped this design, see [`DECISIONS.md`](../../DECISIONS.md)
at the repository root.

---

## What cma-mcp is

cma-mcp is a **subprocess wrapper** that exposes the seven primitives
of bash cma to MCP-compatible AI clients. It does not reimplement
the loop. It does not own a corpus. It does not interpret captures.
For every tool call it spawns the canonical `cma` binary with an
argv array, captures the result, and composes a three-section
payload (`analysis` + `agent_guidance` + `provenance`) that the
caller's agent passes through to its user.

The contribution is **reach**, not new capability. The
subprocess-over-reimplementation discipline keeps cma-mcp thin;
DECISIONS AD-008 locks same-repo-as-cma, and DECISIONS AD-001 locks
no-MCP-SDK-dependency.

---

## The five layers

```
                        MCP client (Claude Desktop, Cursor, Cline, ...)
                                  │  stdio (JSON-RPC 2.0 line-delimited)
                                  ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │  L1  protocol     mcp_protocol.py    Dispatcher, Request,        │
   │                                       parse_line, write_response  │
   ├──────────────────────────────────────────────────────────────────┤
   │  L2  schema       mcp_schema.py      seven tools + four          │
   │                                       resources, JSONSchema       │
   │                                       inputs, descriptions        │
   ├──────────────────────────────────────────────────────────────────┤
   │  L3  dispatch     mcp_server.py      _handle_* per method:        │
   │                                       initialize, tools/list,     │
   │                                       tools/call, resources/list, │
   │                                       resources/read, ping        │
   ├──────────────────────────────────────────────────────────────────┤
   │  L4  data path    cma_subprocess.py  argv-array invocation,      │
   │                   cma_jsonl.py        5s timeout, raw stdout      │
   │                   mcp_resources.py    capture; tolerant JSONL     │
   │                                       reader for read-only views  │
   ├──────────────────────────────────────────────────────────────────┤
   │  L5  composition  mcp_compose.py     three-section payload:       │
   │                                       analysis + agent_guidance + │
   │                                       provenance                  │
   └──────────────────────────────────────────────────────────────────┘
                                  │  spawn / read
                                  ▼
                         bash cma binary  (~/.cma/*.jsonl)
```

Plus two cross-cutting modules:

- `mcp_log.py` — stderr-only structured logging. Stdout is reserved
  for JSON-RPC.
- `_build_info.py` — auto-generated at build time by `setup.py`,
  bakes the git SHA into the wheel so `--version` reports a real
  value after `pip install` (see "Install fingerprint" below).

---

## Two execution modes

The `cli()` entry point in `mcp_server.py` routes by argument:

| Invocation | Path | Use |
|---|---|---|
| `cma-mcp` | builds dispatcher, runs `Dispatcher.serve()` blocking on stdin | normal MCP client startup |
| `cma-mcp --version` | `_emit_version_fingerprint()` prints one-line JSON, exits | operator confirms which install is wired up |
| `cma-mcp --test` | `_emit_test_payload()` runs a canned `cma_stats` against the operator's `~/.cma/`, prints the full three-section payload, exits | offline pipeline check without an MCP client handshake |
| `cma-mcp --help` | argparse default | discoverability |

Unknown flags exit non-zero with a usage message — the CLI never
silently swallows misconfiguration.

---

## Data flow: a tool call

```
1.  client writes a JSON-RPC line on cma-mcp's stdin:
       {"jsonrpc":"2.0","id":42,"method":"tools/call",
        "params":{"name":"cma_miss","arguments":{...}}}

2.  Dispatcher.serve() reads the line. parse_line() returns a
    Request. _dispatch_one() looks up the handler:
       _handle_tools_call(params)

3.  _handle_tools_call validates `name` against mcp_schema.TOOLS,
    raises ProtocolError(INVALID_PARAMS) if unknown. Routes to the
    per-tool handler:
       _handle_cma_miss(arguments)

4.  _handle_cma_miss (in mcp_server.py) calls
    _build_capture_argv("miss", arguments, ["surface","fm","files",
    "intended","corrected","excerpt"]). The result is an argv list
    like ["miss", "<description>", "--surface", "auth", "--fm",
    "FM-3"]. Operator-supplied values land in distinct argv slots
    only — never concatenated into a shell-interpreted string
    (DECISIONS AD-004).

5.  _wrap_cma_call invokes cma_subprocess.run_cma(argv) which calls
    subprocess.run([cma_binary] + argv, capture_output=True,
    timeout=5, shell=False). If cma is missing it raises CmaError
    with reason="missing_binary". If cma exits non-zero it raises
    with the stderr.

6.  On success, mcp_compose.compose_capture_response(...) builds
    the three-section payload:

       {
         "analysis":       {"tool": "cma_miss", "cma_stdout": "..."},
         "agent_guidance": {"what_this_tool_does": "...",
                            "what_this_tool_does_not_do": "...",
                            "how_to_cite_faithfully": "..."},
         "provenance":     {"server_version": "0.1.0",
                            "license": "Apache-2.0",
                            "cost_usd": 0.0,
                            "cma_argv": ["/usr/local/bin/cma",
                                         "miss", "<desc>", ...],
                            "cma_returncode": 0,
                            "cma_binary_version": "cma 1.0.0",
                            "git_sha": "abc123...",
                            "deterministic": true,
                            "timestamp": "2026-05-07T..."}
       }

7.  Dispatcher.write_response() encodes it as a tools/call result
    on stdout. The JSON-RPC reply lands on the client's stdin.

8.  The agent reading the response uses `agent_guidance` to compose
    its message to the user. `provenance.citation` carries the
    canonical reference string for any quoting.
```

Resource reads (`resources/read`) take a similar path through
`_handle_resources_read` → `mcp_resources.read_*` → `parse_provenance`
→ `mcp_compose.compose_resource_response`. They never invoke the
cma binary; they read JSONL directly with a tolerant parser.

---

## The three-section payload contract

Every tool response and every resource read returns:

```
{
  "analysis":       <tool-specific data + raw cma_stdout>,
  "agent_guidance": {
      "what_this_tool_does":         "...",
      "what_this_tool_does_not_do":  "...",
      "how_to_cite_faithfully":      "..."
  },
  "provenance":     <server_version, license, cost_usd, citation,
                     deterministic, timestamp, cma_argv, cma_returncode,
                     cma_binary_version, git_sha,
                     [for reads:] data_source>
}
```

**Why three sections, not one.** A plain stdout passthrough lets the
agent paraphrase cma's output as its own observation, stripping the
attribution that makes the loop's evidence worth citing. The
`agent_guidance` section is the structure that carries the citation
discipline forward into whatever the agent shows the user. The
`provenance` section is the structure that lets a downstream auditor
reproduce or verify the call.

Adversarial determinism tests in `tests/test_payload_determinism.py`
pin the shape on every tool and resource. Any change that affects
the payload requires updating those tests.

The convention is inherited from frame-check and applied here
unchanged; the determinism tests pin it commit-by-commit.

---

## Subprocess discipline

Three rules govern every cma invocation. They are enforced
structurally, not by review.

1. **argv-array, never shell=True** (DECISIONS AD-004).
   `subprocess.run([cma_binary, *argv], shell=False)`. Operator-
   supplied strings land in single argv slots. cma's argument
   parser treats them as data; bash does not interpolate them.
   The argv-injection-resistance test in
   `tests/test_subprocess.py` writes a malicious filename
   (`'; rm benign'`) and confirms cma sees it as one argv slot,
   not as a shell command.

2. **5-second timeout on every call** (DECISIONS AD-003).
   `subprocess.run(..., timeout=5)`. On timeout, cma_subprocess
   raises `CmaError(reason="timeout")`. The MCP server stays
   responsive; the caller decides whether to retry. Matches bash
   cma's own failure-isolated `hooks/cma-pre` discipline.

3. **Missing binary surfaces as `isError`, not silent failure**
   (DECISIONS AD-006-style discipline). When `cma` is not on
   `PATH`, the response carries
   `{"isError": true, "reason": "missing_binary",
   "install": "https://github.com/Clarethium/cma#readme"}`.
   No silent skip.

The cma binary path resolution: `shutil.which("cma")`. Operators
who need a non-default path set the `CMA_BINARY` environment
variable and `cma_subprocess.run_cma` uses it. (Tests cover both
paths.)

---

## JSONL read tolerance

`cma_jsonl.py` reads the operator's data directly for the four
read-only resource URIs (`cma://decisions`, `cma://rejections`,
`cma://core`, `cma://stats`). The reader is **tolerant** — DECISIONS
AD-002 — and reports the parse-trust signal in `provenance`:

```
ReadResult(
    records=[<successfully parsed rows>],
    schema_version_native=<count of "schema_version":"1.0" rows>,
    schema_version_legacy=<count of rows missing schema_version>,
    schema_version_unknown=<{seen_value: count, ...}>,
    parse_failures=<count of malformed lines>,
)
```

`mcp_resources.parse_provenance` rolls these counts into the
`provenance.data_source` block on every resource read. A caller who
wants strict reading checks the counts; the wrapper itself does not
reject. This matches bash cma's own tolerant-read discipline.

If a future schema_version is genuinely incompatible, cma-mcp will
add a strict gate at parse time and emit `isError` for that schema
specifically. Until then, permissive read with honest provenance is
the right balance: the parse-trust signal in
`provenance.data_source` lets the caller decide whether to trust
the records.

---

## Install fingerprint

`cma-mcp --version` emits one-line JSON:

```
{"server_name": "cma-mcp",
 "server_version": "0.1.0",
 "protocol_version": "2024-11-05",
 "git_sha": "<runtime probe or build-time bake>",
 "cma_binary_version": "<cma --version output>",
 "python": "3.12.3",
 "script": "/path/to/installed/mcp_server.py"}
```

`git_sha` resolves via two paths:

1. **Runtime probe** (`_git_sha()` in `mcp_server.py`):
   `git rev-parse HEAD` against the script's directory. Works in
   development clones (`pip install -e .`).
2. **Build-time bake** (fallback):
   `from _build_info import BUILD_GIT_SHA`. `setup.py` writes
   `_build_info.py` at sdist/wheel build time, preferring the
   `CMA_MCP_BUILD_SHA` environment variable (CI sets it to
   `$GITHUB_SHA`) over a local `git rev-parse`. Works for installs
   from a wheel where the runtime probe sees no `.git`.

Without the bake, PyPI installs would silently report
`git_sha: null` and the forensic-traceability claim would degrade
on the most common install path.

---

## Module map

| File | Lines | Responsibility |
|---|---:|---|
| `mcp_server.py` | ~550 | CLI entry point; `cli()` argument parser; per-tool/per-method handlers; install fingerprint; `_build_dispatcher()` wiring. |
| `mcp_protocol.py` | ~230 | JSON-RPC 2.0 over stdio: `Request`, `parse_line`, `write_response`, `Dispatcher`, `ProtocolError`, JSON-RPC error codes. |
| `mcp_schema.py` | ~520 | Tool and resource catalogs: descriptions, `inputSchema` JSONSchemas, parameter validation. The agent-facing surface lives here. |
| `mcp_compose.py` | ~340 | Three-section payload composers, per tool + per resource. `configure_provenance()` once at startup; helpers thereafter. |
| `mcp_resources.py` | ~210 | Resource-read business logic: read JSONL, sort newest-first, attach `parse_provenance`, return composed payload. |
| `cma_subprocess.py` | ~245 | The single ingress to bash cma. `run_cma`, `cma_version`, error shapes (`CmaError` with `reason` field). |
| `cma_jsonl.py` | ~165 | Tolerant JSONL reader. Counts schema-version trust signal. No interpretation. |
| `mcp_log.py` | ~70 | Stderr-only structured logging. Stdout reserved for JSON-RPC. |
| `_build_info.py` | 2 | Auto-generated by `setup.py` at build time. `BUILD_GIT_SHA = "..."`. Gitignored. |

Test suite (`tests/`): 48 cases plus the wheel-install smoke step
in CI.

---

## What this design rejects

- **No MCP SDK dependency.** Manual JSON-RPC keeps the runtime
  surface to the Python standard library.
- **No methodology vocabulary bundled.** `--fm` is opaque.
  Operators tag with their methodology's catalog (Lodestone's
  FM-1..10 or otherwise).
- **No transports beyond stdio.** SSE / WebSocket / HTTP are out of
  scope; gateways exist for multi-client deployment. DECISIONS
  AD-005.
- **No reimplementation of cma's primitives.** Every flag is a
  subprocess argv slot.

These rejections are not "we'll get to them later." They are the
shape that keeps cma-mcp thin and drift-resistant.

---

## How to extend safely

A surface change (adding a tool, adding a resource, changing a
schema) touches **four files together**:

1. `mcp_schema.py` — add the entry to `TOOLS` or `RESOURCES`.
2. `mcp_server.py` — add the `_handle_*` dispatcher and wire it.
3. `tests/test_mcp_server.py` — add a conformance test that
   exercises the surface.
4. `docs/MCP_SERVER.md` — document the operator-facing reference.

A PR that moves only one of the four is incomplete. Reviewers will
ask for the others. See [`CONTRIBUTING.md`](../../CONTRIBUTING.md)
for the full PR checklist.

---

*Updated when the architecture changes. Last revision tracks the
build-time SHA bake mechanism and the wire-protocol subprocess test
landing.*
