# AGENTS.md

Guidance for AI coding agents (Claude Code, Cursor, Codex, Aider,
etc.) working in this repository.

This file is loaded by most agent runtimes the same way `CLAUDE.md`
or `.cursorrules` is. Agents should read it before making changes.

## What this repo is

`Clarethium/cma` is the public canonical repo for the **CMA**
(Compound Memory Architecture) bash CLI plus its MCP wrapper at
`cma-mcp/`. The bash CLI at the repo root is the load-bearing
implementation; the Python MCP wrapper at `cma-mcp/` is a thin
distribution surface. They ship together because every CMA flag is
a CMA-MCP tool argument and every JSONL field in `surface_events.jsonl`
is a CMA-MCP parser concern; same-repo prevents drift structurally.

The decision is codified in `DECISIONS.md` AD-008. If you are
proposing structural changes, read AD-008 first.

## Public-canon discipline

This repo is one of several public Clarethium artifacts. The
operator maintains a separate, private working set of strategic
memos, audit deliverables, methodology drafts, outreach lists,
and similar artifacts. Those **never** enter this repo, regardless
of how relevant they feel to the change in front of you.

If you are tempted to commit a file with any of these shapes:

- A document analyzing why some architectural choice was made
  (rationale memos, decision drafts, "repo shape" discussions).
- An audit of leakage, security, methodology gaps, or publication
  readiness.
- An outreach plan, reviewer list, or methodology paper outline.
- Anything mentioning the operator's secrets vault, claude memory
  layout, or absolute paths into the operator's home directory
  (`/home/<operator>/...`).

Stop. That belongs in the operator's private workspace, not here.
Either drop the change, or write a generalized public-canon version
that documents the *outcome* (what was decided, what shipped) without
the maintainer-internal *reasoning* (why specifically, who else is
involved, what is queued).

## How this is enforced

Three layers of enforcement, each independent of the others:

1. **`.gitignore`** at repo root carries patterns for the
   internal-doc artifact families (`*_INVENTORY_v*.md`,
   `*_AUDIT_v*.md`, `*_VERDICT_v*.md`, `*_REMEDIATION_LOG_v*.md`,
   `*_OUTREACH_v*.md`, `EXTRACT_POLICY.md`, etc.). New artifacts
   matching these shapes will not be staged.

2. **`.gitleaks.toml`** at repo root carries rules that refuse
   commits matching the maintainer-internal artifact patterns or
   absolute operator-workspace paths. Run `gitleaks detect`
   locally before committing if you are unsure about a change.

3. **Branch protection ruleset** on the default branch blocks
   force-push, deletion, and non-linear history. History rewrite
   to clean up a leak is an maintainer-side recovery operation,
   not part of normal flow.

## When you find an existing leak

If you discover that the public history contains maintainer-internal
content (rare, but happens), do not silently delete it in a
forward-only commit. Instead:

1. Open an issue describing what you found, where, and the rough
   shape of the content (do not paste the leak itself into the
   issue).
2. Wait for maintainer-side acknowledgment before any history
   rewrite. History rewrite invalidates Zenodo DOIs, breaks
   external references, and may require coordinated PyPI yanks.

## Commit-message hygiene

A commit that removes leaked content should not narrate the leak
in its own message. The diff shows what was removed; the message
should not re-narrate it. If you must reference what was removed,
use a generic descriptor like "an maintainer-internal artifact"
rather than the document name or content category.

## Engineering norms

- DCO sign-off is required (`git commit -s ...`). The
  `dco-check` workflow blocks merges of unsigned commits.
- Bash CLI tests run via `./test.sh` at the repo root. MCP
  wrapper tests live at `cma-mcp/tests/` and run via
  `pytest cma-mcp/tests/`. Both must pass before merging.
- Style: no em-dashes, en-dashes, smart quotes, or curly
  apostrophes anywhere in committed content (prose, code,
  commit messages). Use straight quotes and rewrite sentences
  rather than reaching for an em-dash. Enforcement is per-
  developer convention; no automated check ships in this repo.
- No AI attribution in commit messages. No "Generated with
  Claude Code" footer. No `Co-Authored-By: Claude`. The work is
  the operator's regardless of which tool produced the diff.

## Pointers for further reading

- `README.md`: what CMA is and how to use it.
- `DECISIONS.md`: durable architectural decisions (AD-001 through
  AD-008).
- `CONTRIBUTING.md`: PR flow, sign-off, style.
- `SECURITY.md`: vulnerability disclosure.
- `cma-mcp/README.md`: MCP wrapper specifics.
