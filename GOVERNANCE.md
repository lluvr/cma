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

**Curator:** Lovro Lucic (single-curator BDFL model for v0.x).

---

## Purpose

This document names who decides what in the cma project, where
those decisions are recorded, and what is explicitly held for
future specification. It closes the reference to `GOVERNANCE.md`
in `CONTRIBUTING.md` without overcommitting to a formal review
process that has not yet been tested against a real external
reviewer.

Strategy and durable decisions live in `NOTES.md`. Architectural
decisions live in `DECISIONS.md`. This document covers governance
mechanics only: who has authority, over what, by what process, and
what happens when governance itself needs to change.

---

## Current state: single-curator

The cma project is a single-curator project. **Lovro Lucic** is the
curator.
For v0.x of the project, the curator carries benevolent-dictator
authority (BDFL-style) over:

- Which architectural decisions land in `DECISIONS.md`
- Which durable decisions land or are amended in `NOTES.md §6`
- Which tool/resource surface changes ship
- Which pull requests merge (reviewer, per `CONTRIBUTING.md`)
- Release timing and version numbers
- Companion-link maintenance with cma, Lodestone, Touchstone,
  frame-check-mcp

Named authorship is the project's primary credibility asset, in line
with the broader Clarethium discipline (see frame-check-mcp's
`GOVERNANCE.md` for the parallel statement). The curator is the
named author on every published release.

---

## Where decisions already live

A decision is not a decision until it lands in an authoritative
source. The sources below are current:

| Decision type | Authoritative source |
|---|---|
| Strategy and durable product decisions (require overturn proposal) | `NOTES.md` (especially §6) |
| Architectural decisions | `DECISIONS.md` |
| Contribution workflow (PR process, tests, sign-off) | `CONTRIBUTING.md` |
| MCP protocol surface | `docs/MCP_SERVER.md` |
| Release history | `CHANGELOG.md` |
| Security policy and reporting | `SECURITY.md` |
| License | `LICENSE` (Apache-2.0); `NOTICE` (per-component summary) |
| Citable form | `CITATION.cff` |
| Anticipated critiques (construct-honesty) | `docs/ANTICIPATED_CRITIQUES.md` |
| Validation program | `docs/VALIDATION_PROGRAM.md` |

---

## How a change becomes canon

For any of the following, open a pull request against `main` with a
description that names the affected source(s) above:

1. **Bug fix or test addition.** Reviewer approves; merge.
2. **New architectural decision.** PR adds an entry to `DECISIONS.md`
   (newest-first append). Reviewer approves; merge.
3. **Durable decision change** (anything in `NOTES.md §6`). PR
   includes both the strategy change and an explicit overturn
   rationale. Curator review required. Default disposition is
   conservative: durable decisions stay durable absent material new
   evidence.
4. **Tool or resource surface change.** PR updates the schema in
   `mcp_schema.py`, the dispatch in `mcp_server.py`, the tests in
   `tests/test_mcp_server.py`, and the docs in `docs/MCP_SERVER.md`.
   All four must move together.
5. **Companion-link change** (text in `NOTES.md §3` or `README.md`
   that references Lodestone, Touchstone, cma, frame-check-mcp).
   Coordinate with the affected companion repo's curator before
   merge. Currently the curator is the same person; that simplifies
   coordination but does not exempt it.

---

## Explicitly deferred

The following are deferred until evidence or external engagement
forces a position:

- **Multi-contributor governance.** Formal review process with
  named reviewers, dissent procedure, and conflict resolution.
  Deferred until a sustained external contributor exists.
- **Suggestion/RFC process** modeled on Touchstone's
  `SUGGESTIONS/PROCESS.md`. cma-mcp is small enough that PR review
  is sufficient for v0.x; an RFC layer may add unwanted weight.
- **Trademark and brand policy.** cma-mcp is published under
  Clarethium; brand decisions defer to the Clarethium-level
  curator.

---

## When governance itself needs to change

Curator amends this document via PR. New external contributors
sustained over 90 days warrant moving from BDFL to a named-reviewer
model; the move itself is recorded as a `NOTES.md` durable
decision.
