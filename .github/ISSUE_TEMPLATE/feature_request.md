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

<!-- The capability, named in operator-facing terms. -->

## Why it matters

<!-- What does this enable that is not currently possible? Concrete use case helps. -->

## Proposed shape

<!--
For bash cma: command surface (flags, output format, exit codes).
Mirror DESIGN.md conventions (kebab-case flags, JSONL outputs where
appropriate).

For cma-mcp: tool / resource name, parameters, returned payload
shape. Mirror existing cma-mcp patterns (three-section payload,
snake_case fields, optional `surface` label, `maxLength` on every
string field).
-->

## Companion impact

<!--
Does this require a parallel change in the other component, in
DESIGN.md / ARCHITECTURE.md / DATA.md / docs/MCP_SERVER.md, or in
any companion repo (Lodestone, Touchstone)? If yes, name what.
-->
