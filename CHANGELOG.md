# Changelog

All notable changes to cma are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] (1.0.0-dev)

### Added

- Initial cma 1.0 reference implementation (bash, no external dependencies; python3 used for JSON escape).
- Capture verbs fully functional: `cma miss`, `cma decision`, `cma reject`, `cma prevented`.
- `cma surface` with `--surface`, `--file`, `--type`, `--limit` filters and recency-ordered output.
- `cma distill` fully functional: default mode promotes a learning to permanent surfacing; `--review` shows recurring miss patterns as distillation candidates; `--retire <pattern>` marks matching core learnings as retired (preserved as retirement records).
- `cma stats` fully functional: default summary plus `--rejections`, `--preventions`, `--recurrence`, and `--leaks` views.
- `cma surface` logs surface events to `surface_events.jsonl` (suppressible with `--no-log`) so `--leaks` can join misses against prior surfaced warnings.
- All seven 1.0 primitives functional. v1.0.0 surface complete.
- Action-time injection: PreToolUse hook for Claude Code (`hooks/claude-code-pre-tool-use.sh`) surfaces relevant prior captures automatically when Claude is about to edit a file or run a command. Heuristic surface detection from file path or command. Closes the compound loop without requiring manual `cma surface` calls.
- Hook test coverage: silent for non-relevant tools, silent when no captures match, surfaces matched captures via stdin JSON, env var fallback for legacy hook protocol.
- Texture preservation on misses: `--excerpt <text>` or `--excerpt-from <file>` (multi-line, preserves newlines and quotes through JSON encoding), `--intended <text>` (counterfactual: what was about to happen), `--corrected <text>` (what happened instead after correction). Texture fields preserve the conditions of failure so future surfacing can match by situation, not just keywords.
- ARCHITECTURE.md specifying the five-stage action-time injection pattern (interception, context extraction, query, injection, logging), reference implementation status, data contracts (surface event, miss with texture, prevention), the three-layer validation framework (process, behavior, outcome), quality criteria for integrations, failure modes to avoid, and versioning policy. The contract integrations conform to.
- Test suite (`test.sh`) with 42 cases covering all functional paths, edge cases (special characters, missing args, unknown flags), and JSON validity.
- CI workflow (GitHub Actions) running the test suite on every push and pull request.
- DESIGN.md specifying the seven-primitive surface and the migration from the working version.
- README with quick-start, status, and license information.

### Pending for 1.0.0

(none — all seven primitives functional in this dev branch)

### Future (post-1.0)

- Generic CLI wrapper for action-time injection in environments other than Claude Code (terminal-based tools, other AI clients).
- Counterfactual capture: explicit "what was about to happen versus what happened" data structure for studying basin transitions.
- Per-project data scoping: optional separation of captures by project rather than a single global directory.
- Trained classifier on accumulated labeled corpus (long-term, requires data accumulation).
