<!--
Thanks for contributing to cma-mcp. Read CONTRIBUTING.md and
GOVERNANCE.md before opening a substantial change. Especially:

- Sign every commit with DCO: `git commit -s`
- Run pytest before pushing: `python3 -m pytest -q`
- Check whether your change contradicts a prior DECISIONS.md entry;
  if so, the PR description must name the contradiction.
-->

## Summary

<!-- One short paragraph: what changed, why. -->

## Type

<!-- Check one. -->

- [ ] Bug fix (no schema change)
- [ ] New tool, resource, or schema field (additive; minor SERVER_VERSION bump)
- [ ] Schema-breaking change (major SERVER_VERSION bump)
- [ ] Documentation only
- [ ] Test addition / refactor
- [ ] Architectural decision (DECISIONS.md entry added)

## Reviewer checklist

- [ ] DCO sign-off on every commit (`git log` shows `Signed-off-by:` trailer)
- [ ] `python3 -m pytest -q` passes locally
- [ ] If surface changed: `mcp_schema.py`, `mcp_server.py`, the relevant test, and `docs/MCP_SERVER.md` all updated together
- [ ] If payload shape changed: `tests/test_payload_determinism.py` updated
- [ ] If runtime behavior changed: `CHANGELOG.md` `[Unreleased]` updated
- [ ] No new runtime dependency added (cma-mcp's runtime stays stdlib-only by default)

## Companion-link impact

<!--
Does this change affect references to cma, Lodestone, Touchstone,
or frame-check? If yes, name what coordinates with each
companion repo. If no, write "none".
-->

## DECISIONS

<!--
If this PR adds a DECISIONS.md entry, paste the AD-NNN block here.
If this PR contradicts a prior DECISIONS.md entry, name the
contradiction and the reason.
-->
