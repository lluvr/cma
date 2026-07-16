# AGENTS.md

Guidance for AI coding agents (Claude Code, Cursor, Codex, Aider,
etc.) working in this repository.

This file is loaded by most agent runtimes the same way `CLAUDE.md`
or `.cursorrules` is. Read it before making changes.

## What this repo is

`lluvr/cma` is the public canonical repository for **cma**
(executable compound practice loop) plus its MCP wrapper at
`cma-mcp/`. The bash CLI at the repo root is the load-bearing
implementation; the Python MCP wrapper at `cma-mcp/` is a thin
distribution surface. They ship together because every cma flag is a
cma-mcp tool argument and every JSONL field in `surface_events.jsonl`
is a cma-mcp parser concern; same-repo prevents drift structurally.

The decision is codified in `docs/DECISIONS.md` AD-008. If you are
proposing structural changes, read AD-008 first.

## What goes in this repo

This repository ships only what an adopter needs to install, run,
extend, and audit CMA. The scope is fixed:

- The bash CLI and its `scripts/test.sh` suite.
- The `cma-mcp/` Python wrapper, its tests, and the wheel metadata.
- `README.md`, `CONTRIBUTING.md`, `docs/GOVERNANCE.md`, `SECURITY.md`,
  `CHANGELOG.md`, `LICENSE`, `CITATION.cff`, `docs/DECISIONS.md`.
- `AGENTS.md` (this file) at the root.

Anything outside that scope does not enter the repository. The
following content shapes are **never** committed here, regardless of
how relevant they feel to the change in front of you:

- Strategy memos, roadmap drafts, "what we are betting on"
  documents, positioning analyses.
- Audit deliverables: leakage audits, security audits, methodology
  audits, publication-readiness verdicts, gap inventories,
  remediation logs.
- Reviewer outreach lists, recruitment templates, methodology
  paper outlines or candidate-version drafts.
- Anything that names a private workspace, secrets vault, claude
  memory layout, or absolute path into a contributor's home
  directory.

Construction discipline: when public content is needed on a subject
that touches one of those shapes, write the public version from
scratch for the adopter audience. Do not paraphrase from a private
draft. If a paragraph reads naturally only to a reader who already
knows what is private, rewrite or remove it.

## How this is enforced

Three layers, each independent:

1. **`.gitignore`** carries shape-based patterns that match common
   strategic-memo and audit-deliverable filenames so files of those
   shapes do not stage by accident.

2. **`.gitleaks.toml`** carries shape-based rules that refuse
   commits matching contributor-workspace absolute paths and the
   filename shapes in §2 above. Run `gitleaks detect` locally
   before committing if you are unsure.

3. **Branch protection ruleset** on the default branch blocks
   force-push, deletion, and non-linear history. History rewrite
   to clean a leak is a maintainer-led recovery operation, not
   part of normal flow.

## When you find an existing leak

If you discover that the public history contains content that
should not be there:

1. Open an issue describing the location and the rough shape of the
   content. Do not paste the leak itself into the issue.
2. Wait for maintainer acknowledgment before any history rewrite.
   History rewrite invalidates Zenodo DOIs, breaks external
   references, and may require coordinated PyPI yanks.

## Commit-message hygiene

A commit that removes leaked content should not narrate the leak in
its own message. The diff shows what was removed; the message should
not re-narrate it. Subtract over substitute: when removing a
sentence that referenced the leak, delete the sentence and rewrite
the surrounding paragraph to stand on its own. Do not replace it
with a placeholder marker; the marker itself is a leak.

## Engineering norms

- DCO sign-off required (`git commit -s ...`). The `dco-check`
  workflow blocks merges of unsigned commits.
- Bash CLI tests run via `./scripts/test.sh` at the repo root. MCP wrapper
  tests live under `cma-mcp/tests/` and run via
  `pytest cma-mcp/tests/`. Both must pass before merging.
- Style: no em-dashes, en-dashes, smart quotes, or curly apostrophes
  anywhere in committed content (prose, code, commit messages). Use
  straight quotes and rewrite sentences rather than reaching for an
  em-dash. Enforcement is per-developer convention; no automated
  check ships in this repository.
- No AI attribution in commit messages. No "Generated with Claude
  Code" footer. No `Co-Authored-By: Claude`. The work belongs to the
  human committer regardless of which tool produced the diff.

## Pointers for further reading

- `README.md`: what CMA is and how to use it.
- `docs/DECISIONS.md`: durable architectural decisions (AD-001 through
  AD-008).
- `CONTRIBUTING.md`: PR flow, sign-off, style.
- `SECURITY.md`: vulnerability disclosure.
- `cma-mcp/README.md`: MCP wrapper specifics.

## Forbidden vocabulary

Beyond the file shapes above, certain phrasings always leak. These never appear in committed content (with the exception of this AGENTS.md, the canon audit script `scripts/canon_audit.sh`, and its two self-test fixtures `scripts/canon_audit_known_leaks.txt` and `scripts/canon_audit_pystring_concat_known_leaks.py`, which are allowed to name the patterns in order to forbid or self-verify them):

- `maintainer-side`, `maintainer-internal` (any compound).
- `the operator's [strategy|methodology|notes|vault|workspace|tree|dev tree|bet|stake|positioning]`, also when an adjective intervenes (`the operator's research vault`).
- Bare `operator [paper|study|playbook|doctrine|memo|brief]`: these artifact-shape words name a written artifact authored by "the operator" and are unambiguously leak-shaped.
- Practitioner-sense `operator` compounds: `operator [methodology|framework|practice|discipline|skill|stance]`, `multi-operator`, `operator-AI`, and `the operator's [loop|stance|skill|judgment|contribution|disposition|perspective|choice|workflow|discipline]`. "operator" was retired from public content in favor of "builder" (the person), second person for direct address, or dropped where it read as filler; these compounds are leaks. Bare `operator` in unrelated literal senses (cloud operators, the Python `operator` module, mathematical operators) is fine. The fresh-reader test catches any practitioner-sense recurrence the patterns miss.
- Any definite reference to `vault` as a body of operator material: `the vault`, `in the vault`, `from the vault`. Also forbidden as terms of art: `vault-faithful`, `vault-validated`, `vault behaviour`, `vault precision threshold`, `vault notes`. Allowed only in domain compounds where `vault` is unrelated (`password vault`, `secrets vault`, `hashicorp vault`, `key vault`).
- Sanitization-shape parentheticals: `(see private)`, `(internal reference)`, `(maintainer-side reference)`, `(see maintainer-side ...)`.
- Strategic-positioning vocabulary: `trust|data|authorship|named-authorship|compounding|methodology moat`, `Clarethium-empire`, `empire-grade`, `the project's empire`, `core claim`, `evidence discipline`.
- Operator hostname / username: `Powerhouse.localdomain`, `llucic@`.

Subtract over substitute: when removing one of these, delete the sentence and rewrite the surrounding paragraph. Do not replace it with a placeholder marker; the marker itself is a leak.

## Verification before commit

Run the canon audit:

```bash
bash scripts/canon_audit.sh --self-test   # verify the audit catches every forbidden shape
bash scripts/canon_audit.sh               # check the working tree
```

Both must exit 0. The self-test runs the audit against `scripts/canon_audit_known_leaks.txt` (the fixture lists every shape forbidden above) and confirms the pattern set still catches all of them. The working-tree check verifies your changes don't introduce new violations.

False positives can be tagged with an inline comment: `# canon-exempt: <reason>`. The reason is mandatory; bare `# canon-exempt:` without a reason is rejected.

## Build artifacts

`build/`, `dist/`, `*.egg-info/`, `__pycache__/`, `.pytest_cache/`, `.venv/`, `venv/`, `.tox/`, `.coverage`, `htmlcov/` MUST NOT be committed. They re-import previously-sanitized text from prior pipeline runs and have leaked maintainer-side content in past releases. The repository `.gitignore` covers these patterns; do not bypass.
