---
name: Bug report
about: Something cma or cma-mcp does that does not match the documented behavior
title: '[bug] '
labels: bug
---

## Component

- [ ] bash cma (the CLI, hooks, shell wrappers)
- [ ] cma-mcp (the MCP server)
- [ ] Both

## Expected behavior

<!-- What you expected to happen, with reference to README, DESIGN.md, ARCHITECTURE.md, cma-mcp/docs/MCP_SERVER.md, or a specific primitive/tool. -->

## Actual behavior

<!-- What happened instead. Quote any error message verbatim. -->

## Reproduction

<!-- Minimum steps to reproduce. For cma-mcp, the specific MCP client and version helps. -->

## bash cma version

```
$ cma --version
<paste output here, or note "cma not installed">
```

## cma-mcp install fingerprint (if cma-mcp is involved)

```
$ cma-mcp --version
<paste JSON output here>
```

## Environment

- OS:
- Python version (if cma-mcp):
- MCP client (Claude Desktop / Cursor / Cline / etc.) and version (if cma-mcp):

## Logs

<!--
cma writes diagnostics to stderr; cma-mcp logs to stderr too. If
your MCP client surfaces server stderr, paste the relevant lines
here. For cma-mcp, you can set `CMA_MCP_LOG_LEVEL=DEBUG` for
verbose logging.
-->
