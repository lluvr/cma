# Governance

**Scope:** Covers the cma project as a whole. The project ships as
a single repository ([Clarethium/cma](https://github.com/Clarethium/cma))
with two components: the bash cma reference implementation
(repository root) and the cma-mcp Python distribution wrapper
(`cma-mcp/` subdirectory). One curator, one governance model, one
issue tracker.

**Status:** Minimal v0. Documents the current de-facto governance
model. Formal review process and dissent handling are deferred until
a real external contributor or reviewer engages.

**Date:** 2026-05-06

**Curator:** Lovro Lucic (single-curator BDFL model).

---

## Purpose

This document names who decides what in the cma project, where
those decisions are recorded, and what is explicitly held for
future specification. It closes the reference to `GOVERNANCE.md`
in `CONTRIBUTING.md` without overcommitting to a formal review
process that has not yet been tested against a real external
reviewer.

Architectural decisions live in `DECISIONS.md`. This document
covers governance mechanics only: who has authority, over what, by
what process, and what happens when governance itself needs to
change.

---

## Current state: single-curator

The cma project is a single-curator project. **Lovro Lucic** is the
curator.
In the single-curator phase, the curator carries benevolent-dictator
authority (BDFL-style) over:

- Which architectural decisions land in `DECISIONS.md`
- Which tool/resource surface changes ship
- Which pull requests merge (reviewer, per `CONTRIBUTING.md`)
- Release timing and version numbers
- Companion-link maintenance with cma, Lodestone, Touchstone,
  frame-check

The curator is the named author on every published release.

---

## Where decisions already live

A decision is not a decision until it lands in an authoritative
source. The sources below are current:

| Decision type | Authoritative source |
|---|---|
| Architectural decisions | `DECISIONS.md` |
| Contribution workflow (PR process, tests, sign-off) | `CONTRIBUTING.md` |
| MCP protocol surface | `cma-mcp/docs/MCP_SERVER.md` |
| Release history | `CHANGELOG.md` (bash cma); `cma-mcp/CHANGELOG.md` (cma-mcp) |
| Security policy and reporting | `SECURITY.md` |
| License | `LICENSE` (Apache-2.0); `NOTICE` (per-component summary) |
| Citable form | `CITATION.cff` |

---

## How a change becomes canon

For any of the following, open a pull request against `main` with a
description that names the affected source(s) above:

1. **Bug fix or test addition.** Reviewer approves; merge.
2. **New architectural decision.** PR adds an entry to `DECISIONS.md`
   (newest-first append). A PR that contradicts a prior entry
   names the contradiction in the PR description. Curator review
   required. Default disposition is conservative: prior decisions
   stay in place absent material new evidence.
3. **Tool or resource surface change.** PR updates the schema in
   `cma-mcp/mcp_schema.py`, the dispatch in `cma-mcp/mcp_server.py`,
   the tests in `cma-mcp/tests/test_mcp_server.py`, and the docs in
   `cma-mcp/docs/MCP_SERVER.md`. All four must move together.
4. **Companion-link change** (text in `README.md` that references
   Lodestone, Touchstone, cma, frame-check). Coordinate with the
   affected companion repo's curator before merge. Currently the
   curator is the same person; that simplifies coordination but
   does not exempt it.

---

## Explicitly deferred

The following are deferred until evidence or external engagement
forces a position:

- **Multi-contributor governance.** Formal review process with
  named reviewers, dissent procedure, and conflict resolution.
  Deferred until a sustained external contributor exists.
- **Suggestion/RFC process** modeled on Touchstone's
  `SUGGESTIONS/PROCESS.md`. cma-mcp is small enough that PR review
  is sufficient at the current scale; an RFC layer may add unwanted weight.
- **Trademark and brand policy.** cma-mcp is published under
  Clarethium; brand decisions defer to the Clarethium-level
  curator.

---

## When governance itself needs to change

Curator amends this document via PR. New external contributors
sustained over 90 days warrant moving from BDFL to a named-reviewer
model; the move itself is recorded as a new entry in
`DECISIONS.md`.
