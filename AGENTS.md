# AGENTS.md

Guidance for AI coding agents (Claude Code, Cursor, Codex, Aider,
etc.) working in this repository.

This file is loaded by most agent runtimes the same way `CLAUDE.md`
or `.cursorrules` is. Read it before making changes.

## What this repo is

`Clarethium/cma` is the public canonical repository for the **CMA**
(Compound Memory Architecture) bash CLI plus its MCP wrapper at
`cma-mcp/`. The bash CLI at the repo root is the load-bearing
implementation; the Python MCP wrapper at `cma-mcp/` is a thin
distribution surface. They ship together because every CMA flag is a
CMA-MCP tool argument and every JSONL field in `surface_events.jsonl`
is a CMA-MCP parser concern; same-repo prevents drift structurally.

The decision is codified in `DECISIONS.md` AD-008. If you are
proposing structural changes, read AD-008 first.

## What goes in this repo

This repository ships only what an adopter needs to install, run,
extend, and audit CMA. The scope is fixed:

- The bash CLI and its `test.sh` suite.
- The `cma-mcp/` Python wrapper, its tests, and the wheel metadata.
- `README.md`, `CONTRIBUTING.md`, `GOVERNANCE.md`, `SECURITY.md`,
  `CHANGELOG.md`, `LICENSE`, `CITATION.cff`, `DECISIONS.md`.
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
- Bash CLI tests run via `./test.sh` at the repo root. MCP wrapper
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
- `DECISIONS.md`: durable architectural decisions (AD-001 through
  AD-008).
- `CONTRIBUTING.md`: PR flow, sign-off, style.
- `SECURITY.md`: vulnerability disclosure.
- `cma-mcp/README.md`: MCP wrapper specifics.
