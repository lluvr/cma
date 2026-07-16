<!--
Thanks for contributing. Read CONTRIBUTING.md and docs/GOVERNANCE.md
before opening a substantial change. Especially:

- Sign every commit with DCO: `git commit -s`
- Run the relevant test suite before pushing:
  - bash cma: `./scripts/test.sh`
  - cma-mcp:  `python3 -m pytest -q` from `cma-mcp/`
- Check whether your change contradicts a prior docs/DECISIONS.md entry;
  if so, the PR description must name the contradiction.
-->

## Summary

<!-- One short paragraph: what changed, why. -->

## Component

- [ ] bash cma (repository root)
- [ ] cma-mcp (Python MCP wrapper)
- [ ] Both
- [ ] Cross-cutting (governance, license, citation, docs)

## Type

- [ ] Bug fix
- [ ] New surface (additive; minor version bump for the touched component)
- [ ] Surface-breaking change (major version bump)
- [ ] Documentation only
- [ ] Test addition / refactor
- [ ] Architectural decision (docs/DECISIONS.md entry added)

## Reviewer checklist

- [ ] DCO sign-off on every commit (`git log` shows `Signed-off-by:` trailer)
- [ ] Relevant test suite passes locally
- [ ] If bash cma surface changed: `cma`, `scripts/test.sh`, `docs/DESIGN.md`, and `docs/ARCHITECTURE.md` (if action-time injection touched) updated together
- [ ] If cma-mcp surface changed: `mcp_schema.py`, `mcp_server.py`, the relevant test, and `cma-mcp/docs/MCP_SERVER.md` updated together
- [ ] If payload shape changed: `cma-mcp/tests/test_payload_determinism.py` updated
- [ ] If runtime behavior changed: the relevant CHANGELOG `[Unreleased]` updated
- [ ] No new runtime dependency added (bash cma: bash + python3 stdlib only; cma-mcp: Python stdlib only)
- [ ] `bash scripts/canon_audit.sh` passes locally

## Related-project impact

<!--
Does this change affect references to Touchstone, frame-check,
Lodestone, or any related project? If yes, name what coordinates with
each. If no, write "none".
-->

## DECISIONS

<!--
If this PR adds a docs/DECISIONS.md entry, paste the AD-NNN block here.
If this PR contradicts a prior docs/DECISIONS.md entry, name the
contradiction and the reason.
-->
