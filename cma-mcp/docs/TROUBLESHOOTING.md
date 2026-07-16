# cma-mcp Troubleshooting

Symptoms, diagnostics, fixes. Read top-down: the diagnostic loop
at the start gives the right answer for ~80% of issues.

For "why" questions and conceptual orientation, see
[`FAQ.md`](FAQ.md).

---

## The diagnostic loop

When something is wrong, run these four commands in order. Each
one rules out a specific class of problem; the first failure
identifies the layer to fix.

```
1.  cma --version           # is bash cma installed and runnable?
2.  cma stats               # does bash cma read your corpus?
3.  cma-mcp --version       # is cma-mcp installed and importable?
4.  cma-mcp --test          # does the wrapper round-trip a real call?
```

If `1` fails: install bash cma per the
[parent README](https://github.com/lluvr/cma#readme).

If `2` fails (binary works but corpus errors): run `cma init` to
materialize `~/.cma/`, or check that `CMA_DIR` is not pointing
somewhere unexpected.

If `3` fails: re-run `pip install cma-mcp` (or `pipx install
cma-mcp`). If the script is missing on PATH, the install location
is not on `PATH`.

If `4` fails: the bug is in the wrapper layer or its connection to
cma. The error output names the layer (subprocess timeout,
parse failure, schema mismatch).

---

## The MCP client cannot see cma-mcp

**Symptom.** Claude Desktop / Cursor / Cline show no cma tools in
the tool list.

**Cause hierarchy** (likely-first):

1. **Config file path is wrong for the platform.**
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows (Claude Desktop): `%APPDATA%\Claude\claude_desktop_config.json`
   - Cursor: `~/.cursor/mcp.json` (or settings UI)

2. **JSON syntax error in the config.** Validate with
   `python3 -m json.tool < <config_file>`. A trailing comma after
   the last entry is the most common cause.

3. **The client was not restarted after the config change.** MCP
   servers are loaded at client start; a config change is invisible
   until the next launch.

4. **The `cma-mcp` command is not on the PATH the client sees.**
   GUI applications do not always inherit shell PATH (Claude
   Desktop on macOS is the canonical example). Use the absolute
   path:

   ```json
   {
     "mcpServers": {
       "cma": {
         "command": "/Users/yourname/.local/bin/cma-mcp"
       }
     }
   }
   ```

   Find the absolute path with `which cma-mcp`.

5. **cma-mcp itself is failing on startup.** Run `cma-mcp --version`
   directly. If it errors, that error is what the client sees.

**Diagnostic.** Most clients log MCP server startup. For Claude
Desktop on macOS, the log is at
`~/Library/Logs/Claude/mcp-server-cma.log`. The first line of that
log tells you what failed.

---

## Tool calls return "isError: true" with "missing_binary"

**Symptom.** Every tool call returns:
```
{"isError": true, "reason": "missing_binary",
 "install": "https://github.com/lluvr/cma#readme"}
```

**Cause.** The cma binary is not on the PATH that cma-mcp sees.

**Fix.**

```bash
which cma                                # confirm the binary is on YOUR PATH
echo "$PATH"                              # confirm what your PATH is
cma-mcp --version | python3 -m json.tool  # check what cma-mcp sees
```

If `which cma` returns a path but `cma-mcp --version` reports
`cma_binary_version: null`, the MCP client is launching cma-mcp
without your shell PATH. Set the binary path explicitly via the
`CMA_BINARY` environment variable in the MCP client config:

```json
{
  "mcpServers": {
    "cma": {
      "command": "cma-mcp",
      "env": {
        "CMA_BINARY": "/usr/local/bin/cma"
      }
    }
  }
}
```

---

## Tool calls hang, then return "isError: true" with "timeout"

**Symptom.** Calls that previously completed in milliseconds now
hang for 5 seconds and return:
```
{"isError": true, "reason": "timeout"}
```

**Cause.** bash cma is taking longer than 5 seconds. This is a
hard ceiling enforced by cma-mcp (DECISIONS AD-003) so a hung cma
process does not hang the MCP server.

**Diagnose.**

```bash
time cma stats           # baseline: should be sub-second
ls -la ~/.cma/           # check corpus size
wc -l ~/.cma/*.jsonl     # individual file sizes
```

The most common causes:

1. A JSONL file has grown into the millions of records. Aggregation
   stats (`cma stats --leaks`, `--recurrence`) become O(N²) past
   some threshold. Mitigate via `cma distill --retire <pattern>`
   to graduate frequent recurrences into core learnings, or split
   the corpus per project via `CMA_DIR`.
2. The file is on a slow / network filesystem. Move the corpus to a
   local SSD path via `CMA_DIR`.
3. A corrupted record is causing cma's parser to thrash. Run
   `cma stats` and look for `cma: skipped N corrupted line(s)`
   warnings.

---

## "Unknown schema_version" warnings on every read

**Symptom.** Resource reads (`cma://decisions`, `cma://core`, etc.)
include `provenance.data_source.schema_version_unknown` with non-
zero counts.

**Cause.** Records in your corpus carry a `schema_version` other
than `"1.0"`. cma-mcp parses them tolerantly (DECISIONS AD-002) so
the read still succeeds, but the trust signal flags the
unrecognized schema.

**Fix.** Two paths.

1. If the records came from a different cma fork (a different
   `schema_version` value), confirm the schema is read-compatible
   with cma 1.0. Most additive changes are; check the fork's
   schema docs.
2. If the records carry a future cma schema, upgrade to a cma
   version that recognizes it. Until then, the `provenance.data_
   source.schema_version_unknown` count is the honest read signal.

---

## `cma-mcp --version` reports `git_sha: null`

**Symptom.**

```json
{"server_name": "cma-mcp", ..., "git_sha": null, ...}
```

**Causes**, depending on install path.

1. **From a wheel where `_build_info.py` was not bundled.** Should
   not happen post 0.1.0 because `pyproject.toml` lists
   `_build_info` in `py-modules` and `setup.py` writes the file.
   If you are running an early-cut wheel, rebuild from source.
2. **Build-time SHA was unavailable.** `setup.py` writes empty
   when `CMA_MCP_BUILD_SHA` is not set and there is no `.git`
   directory accessible (e.g., a ZIP source download). Rebuild
   inside a real clone.
3. **A development clone, not a wheel install, but the `git`
   binary is missing or unreadable.** Install git and confirm
   `git rev-parse HEAD` works from the cma-mcp directory.

`git_sha: null` is honest and not a fatal error; the install
fingerprint surfaces the gap rather than hiding it.

---

## Coverage report shows a sudden drop after a refactor

Coverage scopes the eight runtime modules per `pyproject.toml
[tool.coverage.run]`. The wire-protocol tests
(`tests/test_mcp_wire.py`) spawn cma-mcp as a real subprocess and
do not increment coverage counters because pytest-cov does not
follow subprocess code paths without a `sitecustomize` hook.

If you renamed a module or moved code into a function only
exercised through wire tests, coverage will appear to drop even
though end-to-end behavior is unchanged. Confirm by running:

```bash
python3 -m pytest tests/test_mcp_wire.py -v
```

If those pass, the behavior is intact; the coverage number is a
floor, not a ceiling.

---

## Where to file a bug

Reproducible bugs go to
[github.com/lluvr/cma/issues](https://github.com/lluvr/cma/issues)
with the `cma-mcp` label or `[cma-mcp]` in the title to
disambiguate from bash cma issues.

A useful bug report includes:

```
## What I expected
<one sentence>

## What I observed
<the error or unexpected output, copied verbatim>

## Reproduction
<minimal MCP client + cma-mcp interaction>

## Environment
$ cma-mcp --version
{...paste the install fingerprint...}

$ cma --version
<paste>

OS: <Linux/macOS/Windows-WSL distribution + version>
MCP client: <Claude Desktop X.Y.Z / Cursor / Cline / etc.>
```

Security issues use GitHub's private vulnerability reporting; see
[SECURITY.md](https://github.com/lluvr/cma/blob/main/SECURITY.md),
not the public issue tracker.
