# Contributing

The cma project ships two components in this repository:

- **cma** (bash, repository root) — the canonical compound practice
  loop reference implementation. Contributions touch `cma`, `hooks/`,
  `test.sh`, `bench.sh`, and the design docs (`DESIGN.md`,
  `ARCHITECTURE.md`, `DATA.md`).
- **cma-mcp** (Python, `cma-mcp/` subdirectory) — the Model Context
  Protocol distribution wrapper. Contributions touch the Python
  modules (`mcp_*.py`, `cma_*.py`), `cma-mcp/tests/`, and
  `cma-mcp/docs/`.

This document covers **how** contributions happen mechanically: file
layout, test requirements, PR process, and what a reviewer will
check. For **who** decides and **when** a contribution becomes
canon, see `GOVERNANCE.md`. Architectural decisions and their
rationales are recorded in `DECISIONS.md`.

---

## Repository layout

```
cma/
├── cma                          bash CLI (the seven primitives)
├── hooks/                       Claude Code + shell preexec integrations
├── test.sh, bench.sh            bash test and benchmark harnesses
├── DESIGN.md ARCHITECTURE.md DATA.md   cma's surface, architecture, schema
├── CHANGELOG.md                 cma's release history
├── README.md                    cma overview
├── cma-mcp/                     Python MCP distribution wrapper
│   ├── mcp_server.py mcp_*.py cma_*.py   flat-modules wheel layout
│   ├── tests/                   pytest suite
│   ├── docs/                    MCP_SERVER, ARCHITECTURE, FAQ, TROUBLESHOOTING
│   ├── pyproject.toml           PyPI metadata, build config, py-modules list
│   ├── README.md                cma-mcp quickstart (also rendered on PyPI)
│   └── CHANGELOG.md             cma-mcp's release history (independent of cma)
├── DECISIONS.md GOVERNANCE.md   project-level governance (covers both)
├── CONTRIBUTING.md SECURITY.md CITATION.cff NOTICE LICENSE   cross-cutting
└── .github/
    ├── workflows/test.yml       cma's bash test workflow
    ├── workflows/tests-mcp.yml  cma-mcp's pytest workflow
    ├── workflows/dco-check.yml  Sign-off-by enforcement (entire repo)
    ├── workflows/codeql.yml     CodeQL scan for Python in cma-mcp/
    ├── PULL_REQUEST_TEMPLATE.md
    └── ISSUE_TEMPLATE/
```

The two release tracks are independent. cma's `CHANGELOG.md` at root
tracks the bash CLI's releases (cma 1.0, etc.). `cma-mcp/CHANGELOG.md`
tracks the Python wrapper's releases (cma-mcp 0.1, etc.). Tags are
prefixed accordingly (`cma-1.1`, `cma-mcp-0.2`).

---

## Before you start

1. **Read `DECISIONS.md`.** Architectural changes append a new
   entry; do not silently overturn an existing one. A contribution
   that contradicts a prior decision needs the contradiction named
   in the PR description.
2. **For bash cma contributions:** ensure `bash` and a working
   `python3` are available (cma uses python3 for JSON escape only).
   Run `./test.sh` from the repository root before opening a PR.
3. **For cma-mcp contributions:** confirm bash cma is installed and
   on `PATH` (cma-mcp's tests exercise real subprocess calls).
   ```bash
   cma --help
   ```
   If cma is missing, build it from this repository: `ln -s
   "$(pwd)/cma" ~/.local/bin/cma` (per cma's README quickstart).
4. **Run the full test suite for the component you touched.**
   ```bash
   ./test.sh                   # bash cma tests
   cd cma-mcp && pip install -e .[test] && python3 -m pytest -q
   ```
   The suite for the touched component must stay green.

---

## Contribution types

### Bug fix

Open a PR with the fix and at least one test that fails before the
fix and passes after. Reference the issue number in the PR
description.

### MCP protocol surface change

Tool or resource additions, removals, or schema changes touch four
files together:

1. `mcp_schema.py` (input/output schema)
2. `mcp_server.py` (dispatch)
3. `tests/test_mcp_server.py` (conformance test)
4. `docs/MCP_SERVER.md` (reference)

A PR that moves only one of the four is incomplete. Reviewers will
ask for the others.

Surface changes also bump `SERVER_VERSION` in `mcp_server.py`:

- patch: bug fix, no schema change
- minor: new optional field, new tool/resource
- major: schema-breaking change

### Subprocess wrapper extension

`cma_subprocess.py` wraps bash cma's CLI. New cma flags or behaviors
land here when:

- cma releases a new flag that you want exposed via MCP
- a defensive timeout, retry, or error-shape adjustment is needed

Extensions must respect AD-004 (argv-array, never shell=True) and
AD-003 (5-second timeout).

### Test addition

cma-mcp's adversarial coverage is split across the existing test
files: `cma-mcp/tests/test_mcp_server.py` (protocol-level boundaries:
parse error, invalid JSON-RPC, unknown method, malformed params),
`cma-mcp/tests/test_resources.py` (JSONL corruption recovery,
unknown schema-version surfacing, missing-file graceful return),
and `cma-mcp/tests/test_subprocess.py` (subprocess timeout,
missing-binary path, argv-injection-resistance probe). New
adversarial cases are always welcome; add to whichever file fits
the layer being exercised.

`cma-mcp/tests/test_payload_determinism.py` pins the three-section
payload shape on every tool and resource. Any change that affects
payload shape requires a determinism-test update.

---

## Pull request requirements

1. **Sign off your commits with the Developer Certificate of Origin
   (DCO).** This is enforced by CI. Use `git commit -s` to add
   `Signed-off-by: Your Name <your.email@example.com>` to each
   commit. By signing off, you certify the contribution as your work
   under the rules of [DCO 1.1](https://developercertificate.org/).
2. **Tests pass on Python 3.10, 3.11, 3.12.** CI runs all three.
3. **No new external runtime dependencies** without an architectural
   decision in `DECISIONS.md`. cma-mcp's runtime dependency footprint
   is currently the Python standard library only; adding a
   dependency requires explicit rationale.
4. **Three-section payload discipline preserved.** If the PR changes
   any tool or resource response, every changed surface still
   returns `{analysis, agent_guidance, provenance}`.
5. **No silent behavior change.** If a fix changes observable
   behavior, document the change in `CHANGELOG.md` under
   `[Unreleased]`.

---

## Reviewer checklist

A PR that lands meets all of the following:

- [ ] DCO sign-off present on every commit (CI green)
- [ ] Tests pass on all supported Python versions (CI green)
- [ ] CodeQL scan green (CI)
- [ ] Three-section payload preserved on all changed surfaces
- [ ] Schema, server, test, and docs updated together for surface changes
- [ ] CHANGELOG.md `[Unreleased]` updated
- [ ] No new runtime dependency without architectural decision
- [ ] If contradicting a prior DECISIONS.md entry, the contradiction is named in the PR description

---

## Reporting issues

Bug reports, feature requests, and protocol questions go to
[GitHub Issues](https://github.com/Clarethium/cma/issues). For
issues specific to one component, prefix the title with `[cma]`
or `[cma-mcp]` so triage can disambiguate. Security issues go to
`hello@clarethium.com` per `SECURITY.md`.
