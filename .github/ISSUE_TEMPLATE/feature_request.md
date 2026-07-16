---
name: Feature request
about: A capability cma or cma-mcp could expose
title: '[feature] '
labels: enhancement
---

## Component

- [ ] bash cma (the CLI, hooks, shell wrappers)
- [ ] cma-mcp (the MCP server)
- [ ] Both

## What you want

<!-- The capability, in terms of what you want to do. -->

## Why it matters

<!-- What does this enable that is not currently possible? Concrete use case helps. -->

## Proposed shape

<!--
For bash cma: command surface (flags, output format, exit codes).
Mirror docs/DESIGN.md conventions (kebab-case flags, JSONL outputs where
appropriate).

For cma-mcp: tool / resource name, parameters, returned payload
shape. Mirror existing cma-mcp patterns (three-section payload,
snake_case fields, optional `surface` label, `maxLength` on every
string field).
-->

## Related-project impact

<!--
Does this require a parallel change in the other component, in
docs/DESIGN.md / docs/ARCHITECTURE.md / docs/DATA.md /
cma-mcp/docs/MCP_SERVER.md, or in any paired methodology? If yes,
name what.
-->
