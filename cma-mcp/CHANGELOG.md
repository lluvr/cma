# Changelog (cma-mcp)

All notable changes to **cma-mcp** are documented in this file.

cma-mcp ships in this repository alongside the canonical bash cma
reference implementation. The two components release independently:

- bash cma's release history is in the repository's
  [CHANGELOG.md](../CHANGELOG.md) at root.
- This file tracks cma-mcp's release history.

Version tags carry the component prefix (`cma-mcp-0.1.1` for this
component, `cma-1.0.0` for bash cma).

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

(no entries yet)

---

## [0.1.1] - 2026-05-15

First public release.

### Added

- Python ≥3.10 MCP server speaking JSON-RPC over stdio. No SDK dependency; protocol implemented directly (AD-001).
- Seven tools mirroring bash cma's primitives: `cma_miss`, `cma_decision`, `cma_reject`, `cma_prevented`, `cma_distill` (modes: `default` / `retire` / `review`), `cma_surface` (instrumented; logs `surface_events.jsonl` for leak detection), `cma_stats` (views: `default` / `evidence` / `leaks` / `recurrence` / `preventions` / `rejections` / `behavior`; integer `window` parameter scopes the evidence view).
- Four read-only resources for context inheritance: `cma://decisions`, `cma://rejections`, `cma://core`, `cma://stats`.
- Three-section payload (`analysis` + `agent_guidance` + `provenance`) on every tool response and resource read. Tests pin the structure.
- Methodology-agnostic substrate (AD-006): `fm` is an opaque string. cma-mcp bundles no methodology vocabulary; operators pass their methodology's tag through.
- Schema-version handling (AD-002): records with `schema_version: "1.0"` are native; legacy records parse leniently; unknown versions surface in `provenance`.
- Subprocess wrapper around the canonical bash cma binary (AD-004): argv-array (no shell interpolation), 5-second per-call timeout (AD-003), and a 512 KiB argv byte-budget pre-flight guard that surfaces `input_too_large` cleanly before exec.
- Schema-level input bounds on every string field: `MAX_DESCRIPTION` 4 KiB, `MAX_TEXTURE` 64 KiB, `MAX_SHORT_FIELD` 2 KiB. Enum-constrained fields are exempt (the enum is tighter). A schema-invariant test asserts the property; future tool additions cannot regress the bound silently.
- `cma-mcp --version` emits an install fingerprint: `server_version`, `protocol_version`, `git_sha` (runtime probe with build-time bake fallback), `cma_binary_version`, Python version, script path. CI sets `CMA_MCP_BUILD_SHA` so PEP 517 build isolation does not drop the SHA.
- `cma-mcp --test` prints the three-section payload for a canned tool call without an MCP handshake (offline sanity check).
- Initialize handshake carries the standard MCP fields plus a top-level `instructions` block with cross-tool orientation prose.
- pytest suite (54 cases) covers protocol conformance, subprocess wrapping, JSONL parsing, three-section payload determinism, install-fingerprint resolution, adversarial inputs (boundary, malformed, argv-injection probe), and wire-protocol subprocess roundtrips over real stdin/stdout pipes.
- Documentation: `docs/ARCHITECTURE.md` (module map, data flow, contracts), `docs/FAQ.md` and `docs/TROUBLESHOOTING.md` (gotchas, MCP-client configuration across Claude Desktop / Cursor / Cline / Continue.dev, diagnostic loop, bug-report template).
- `bench.py`: wire-level latency benchmark across all tools and resources against a 100-capture synthetic corpus. Shows the wrapper adds essentially zero overhead; subprocess-bound calls inherit bash cma's latency.
- Publish workflow `.github/workflows/publish-mcp.yml`: tag-triggered build of wheel + sdist, twine validation, wheel-content inspection, smoke install, then PyPI upload via OIDC Trusted Publishing. Gated by a required-reviewer protection rule on the `pypi` GitHub Environment.
- CI: `tests-mcp.yml` runs pytest plus a wheel-install smoke check in a clean virtualenv on every push, catching packaging regressions the editable-install path cannot see.

### Notes

- Version alignment is enforced at tag-push time: `pyproject.toml`, `mcp_server.SERVER_VERSION`, and `cma-mcp/CITATION.cff` must match the tag's `cma-mcp-X.Y.Z` literal. The `verify-tag` step in `publish-mcp.yml` hard-fails on drift.
