# Changelog (cma-mcp)

All notable changes to **cma-mcp** are documented in this file.

cma-mcp ships in this repository alongside the canonical bash cma
reference implementation. The two components release independently:

- bash cma's release history is in the repository's
  [CHANGELOG.md](../CHANGELOG.md) at root.
- This file tracks cma-mcp's release history.

Version tags carry the component prefix (`cma-mcp-0.1.0` for this
component, `cma-1.0.0` for bash cma).

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

New entries since the most recent published release accumulate
here. At lift time they either fold into the pending `[0.1.0]`
block below (if 0.1.0 has not yet shipped) or open a new
`[0.1.1]` / `[0.2.0]` block above it (if 0.1.0 has shipped). The
section is intentionally not empty at any time: contributors add
their CHANGELOG entry here as part of the same PR that makes the
change.

(no entries yet)

---

## [0.1.0] - pending publication

First public release. Version content is frozen; PyPI upload is
gated on the lift checklist in the Notes section below. The date
in this header updates to the actual publication date at lift
time.

### Added

- Initial cma-mcp 0.1.0 reference implementation. Python ≥3.10,
  MCP protocol manual JSON-RPC over stdio (no SDK dependency, per
  [DECISIONS AD-001](../DECISIONS.md)).
- Subprocess wrapper around the canonical bash cma binary
  (DECISIONS AD-004): argv-array, no shell interpolation,
  5-second timeout per call (AD-003).
- Seven tools mirroring bash cma's seven primitives: `cma_miss`,
  `cma_decision`, `cma_reject`, `cma_prevented`, `cma_distill`
  (modes: default / retire / review), `cma_surface` (instrumented
  query; logs `surface_events.jsonl` for `cma stats --leaks`
  validation), `cma_stats` (views: default / leaks / recurrence /
  preventions / rejections / behavior).
- Four resources for read-only context: `cma://decisions`,
  `cma://rejections`, `cma://core`, `cma://stats`.
- Three-section payload (`analysis` + `agent_guidance` +
  `provenance`) on every tool response and resource read.
  Adversarial tests pin the structure.
- Methodology-agnostic substrate (DECISIONS AD-006): `--fm` is
  opaque. No Lodestone vocabulary bundled.
- Schema-version handling (DECISIONS AD-002): records with
  `schema_version: "1.0"` are native; legacy records (no
  schema_version field) parse leniently; unknown schema_version
  surfaces in `provenance`.
- `--version` install fingerprint emitting server_version,
  protocol version, git_sha (with `+dirty` flag if working tree
  dirty), cma_binary_version (from `cma --version`), python
  version, absolute script path. The git_sha resolves via two
  paths: a runtime probe of the script's directory (works in
  development clones) and a build-time bake into `_build_info.py`
  via `setup.py` (works for PyPI installs where the runtime probe
  has no `.git` to read). CI sets the `CMA_MCP_BUILD_SHA` env var
  before `python -m build` so PEP 517 build isolation does not
  drop the SHA.
- `--test` offline sanity check: prints the full three-section
  payload for a canned tool call without requiring an MCP client
  handshake.
- Initialize handshake carrying the standard MCP fields plus a
  top-level `instructions` field with cross-tool orientation prose
  (matches frame-check's pattern).
- pytest suite (48 cases) covering protocol conformance,
  subprocess wrapping, JSONL parsing, three-section payload
  determinism, install-fingerprint git_sha fallback, adversarial
  inputs (boundary, malformed, argv-injection-resistance probe),
  and wire-protocol subprocess roundtrips
  (`tests/test_mcp_wire.py`). Coverage in CI scopes the
  eight runtime modules; reported number is a floor (subprocess
  paths in wire tests are not counted by pytest-cov without a
  sitecustomize hook).
- `docs/ARCHITECTURE.md`: module map, data flow for tool calls
  and resource reads, three-section payload contract, subprocess
  discipline, JSONL read tolerance, install fingerprint two-path
  resolution. Reading map for new contributors.
- `docs/FAQ.md` and `docs/TROUBLESHOOTING.md`: conceptual and
  installation gotchas, MCP-client config patterns across Claude
  Desktop / Cursor / Cline / Continue.dev, the four-command
  diagnostic loop, and reproducible bug-report template.
- `bench.py`: latency benchmark mirroring bash cma's `bench.sh`
  shape — measures wire-level round-trip latency for each tool
  and resource through real stdin/stdout pipes against a
  100-capture synthetic corpus. Reveals the wrapper itself adds
  essentially zero overhead; subprocess-bound calls inherit
  cma's latency.
- Publish workflow (`.github/workflows/publish-mcp.yml`) builds
  the wheel + sdist on `cma-mcp-X.Y.Z` tag pushes, validates with
  twine, smoke-tests the installed wheel against the baked SHA,
  and stages the artifacts. PyPI / TestPyPI upload steps are
  intentionally commented out pending the lift checklist
  documented in the workflow header.
- CI wheel-install smoke step in `tests-mcp.yml` builds and
  installs the wheel into a clean virtualenv on every push,
  catching packaging regressions (missing modules, broken entry
  points, dropped license-files, dropped `_build_info.py`) that
  the editable-install pytest path cannot see.
- Input bounds on every string field across the seven tool
  schemas (`MAX_DESCRIPTION=4 KiB`, `MAX_TEXTURE=64 KiB`,
  `MAX_SHORT_FIELD=2 KiB`). Fields constrained by enum are
  exempt; the enum is the tighter constraint. A schema-invariant
  test asserts the property; future tool additions cannot regress
  the bound silently.
- `MAX_ARGV_BYTES=512 KiB` pre-flight guard in
  `cma_subprocess.run_cma`. An over-budget payload raises
  `CmaError(reason='input_too_large')` before exec, replacing the
  generic OS `ARG_MAX` 'unexpected' failure with a clear,
  actionable error to the MCP caller.
- `cma_stats` view enum carries `evidence`, exposing bash cma's
  new `cma stats --evidence` view through MCP. The single signal
  that says whether the loop is closing is reachable from any
  MCP-connected client.
- `cma_stats` input schema carries an integer `window` parameter
  (1..3650, defaults to 30); the dispatcher forwards `--window N`
  to the bash cma subprocess when `view='evidence'`. Operators
  tune the trailing window from MCP without recompiling.
- End-to-end wire test exercising `cma_stats(view='evidence',
  window=7)` over real stdio. The test pins `CMA_BIN` to the
  canonical bash cma in this repo so the assertion does not
  depend on which cma is earliest on the operator's PATH.

### Notes

- 0.1.0 is the first release. PyPI publication is gated on the DOI
  allocation from Zenodo and a final pre-flight conformance pass
  against the installed wheel. Until publication, install from
  source: `pip install -e .` from this directory.
- Versioning convention: PEP 440 pre-release markers (`.dev0`)
  decorate the underlying semver M.m.p during the dev-build
  window. At lift, the suffix drops and `pyproject.toml` aligns
  character-for-character with `SERVER_VERSION` in
  `mcp_server.py`.

---

*cma-mcp internal prototype work prior to 0.1.0 is not documented
here.*
