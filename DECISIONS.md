# Architectural Decisions

This file records architectural decisions for the cma project.
Entries are dated and named, newest-first. Each entry stands on its
own: a decision, its rationale, the trade-off accepted, and whether
the decision is reversible. A PR that contradicts a prior entry
names the contradiction in the PR description.

Entries to date are scoped to the **cma-mcp** component (the
Python MCP wrapper under `cma-mcp/`). Architectural decisions
governing the bash cma reference implementation are documented in
`DESIGN.md`, `ARCHITECTURE.md`, and `DATA.md` at the repository
root.

Newest first.

---

## AD-008: cma-mcp lives inside Clarethium/cma as a subdirectory, not as a separate sibling repository

**Date:** 2026-05-06

**Decision.** cma-mcp ships under `cma-mcp/` in the Clarethium/cma
repository alongside the canonical bash CLI rather than as a
separate `Clarethium/cma-mcp` repository. One repository, one
governance scaffold (root-level `DECISIONS.md`, `GOVERNANCE.md`,
`CONTRIBUTING.md`, `SECURITY.md`, `CITATION.cff`, `NOTICE`), two
release tracks (tags prefixed `cma-1.x` and `cma-mcp-0.x`), two
CHANGELOGs (`CHANGELOG.md` for cma; `cma-mcp/CHANGELOG.md` for
cma-mcp), two CI workflows (`tests.yml` for bash cma;
`tests-mcp.yml` for the Python wrapper, path-filtered to
`cma-mcp/**`).

**Rationale.** cma-mcp is a *wrapper-of* relationship to cma, not a
*uses-as-substrate* relationship: every cma flag is a tool argument,
every JSONL field a parser concern, the cma `surface_events.jsonl`
schema directly load-bearing for cma-mcp's leak-detection coverage.
Wrapper-of relationships couple their subjects tightly enough that
drift is the failure mode. Same-repo prevents drift
structurally: schema changes, new flags, and leak-detection logic
must update wrapper and wrapped together in one PR. Separate repos
would create a coordination tax that the project's compounding
logic actively works against.

**Why frame-check's separate-repo pattern doesn't apply.** That
project *uses* Touchstone as a substrate; Touchstone evolves
independently. cma-mcp wraps cma. An earlier draft treated frame-check's
two-repo shape as a general convention; this entry records the
correction.

**Trade-off accepted.** Repo size grows with both Python and bash
content. Contributor population is slightly more mixed. Independent
release cadence is preserved through tag prefixing and per-component
CHANGELOG files; same-repo does not force same-release.

**Reversibility.** If a future evidence point demands separation,
the `cma-mcp/` directory can be extracted to its own repo via
`git filter-repo`, preserving history. The decision is not
load-bearing on irreversible structure.

---

## AD-007: Tool surface is seven verbs, resource surface is four URIs

**Date:** 2026-05-06

**Decision.** Tool surface mirrors bash cma's seven primitives:
`cma_miss`, `cma_decision`, `cma_reject`, `cma_prevented`,
`cma_distill`, `cma_surface`, `cma_stats`. Resource surface is four
URIs for read-only context: `cma://decisions`, `cma://rejections`,
`cma://core`, `cma://stats`.

**Rationale.** A model that knows bash cma's CLI knows cma-mcp's
tools without retraining. `cma_distill` and `cma_stats` carry
`mode`/`view` arguments rather than splitting into multiple tools to
keep the tool count at the bash cma 1.0 surface (seven). `cma_surface`
remains a tool, not a resource, because it logs `surface_events.jsonl`
as a side effect (load-bearing for `cma stats --leaks`).

Resources are reserved for context the agent reads to orient itself
(decisions, rejections, core learnings, stats summary). Calling
`cma stats` for non-default views (`--leaks`, `--recurrence`,
`--behavior`, `--preventions`, `--rejections`) goes through the
`cma_stats` tool with a `view` arg.

---

## AD-006: cma-mcp does not bundle Lodestone's failure-shape catalog

**Date:** 2026-05-06

**Decision.** No `cma://failure-shapes` resource. Tool descriptions
for `cma_miss` and `cma_prevented` reference Lodestone's FM-1..10 as
an example methodology but do not enumerate it.

**Rationale.** Methodology vocabulary lives in
Lodestone; bundling a frozen copy in cma-mcp couples release cadence
and inverts canon-vs-companion separation. If you want the FM
catalog, read Lodestone directly; if you want autoclassification,
wire `CMA_FM_CLASSIFIER` per cma's plugin convention.

---

## AD-005: Stdio transport only

**Date:** 2026-05-06

**Decision.** cma-mcp ships stdio transport. SSE, WebSocket, and HTTP
transports are explicitly out of scope for v0.1.

**Rationale.** Stdio is the universally supported transport across MCP
clients (Claude Desktop, Cursor, Cline, Continue.dev). If you
need multi-client server-side deployment, you can use one of the
forthcoming MCP gateway projects. Adding transports inside cma-mcp
would expand the surface beyond its distribution-wrapper role.

---

## AD-004: subprocess.run with argv-array, never shell=True

**Date:** 2026-05-06

**Decision.** Every bash cma invocation goes through
`subprocess.run([...], shell=False)` with an argv array. Your
input never gets concatenated into a shell-interpreted string.

**Rationale.** Argument injection is the most likely abuse path for a
local MCP server. The argv-array discipline makes injection
structurally impossible: any string you supply lands in a
single `argv[i]` slot and bash cma's argument parser treats it as
data, not as code.

---

## AD-003: 5-second timeout on every subprocess call

**Date:** 2026-05-06

**Decision.** `subprocess.run` calls all carry `timeout=5`. On
timeout, cma-mcp returns an `isError: true` response naming the
timeout and the partial command. The MCP server stays responsive; the
caller decides whether to retry.

**Rationale.** Matches bash cma's own failure-isolated discipline
(`hooks/cma-pre` 5-second timeout on `cma surface`). A hung cma
process must not hang the MCP server.

---

## AD-002: schema_version pinned to "1.0", any new schema_version
emitted by bash cma surfaces as a parse warning

**Date:** 2026-05-06

**Decision.** cma-mcp's JSONL parser treats records with
`schema_version: "1.0"` as native, records without that field as
legacy (parses leniently), and records with any other
`schema_version` value as a parse warning surfaced in `provenance`.

**Rationale.** Per cma's DATA.md, schema_version is the migration
gate. cma-mcp's wrapper role means it must not silently interpret a
schema it does not recognize; surfacing the unknown schema in
`provenance` lets the caller (model and downstream user) know the
data carries assumptions cma-mcp cannot validate.

---

## AD-001: Manual JSON-RPC, no MCP SDK dependency

**Date:** 2026-05-06

**Decision.** Implement the MCP protocol directly in `mcp_server.py`
using JSON-RPC 2.0 over stdio. No third-party MCP SDK in
`pyproject.toml` dependencies.

**Rationale.** Echoes frame-check's
self-containment convention. The protocol surface used here
(initialize, tools/list, tools/call, resources/list, resources/read,
ping, notifications) fits in a few hundred lines and removes a class
of version-skew failures.

---

*Future architectural decisions append above this line, newest first.*
