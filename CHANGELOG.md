# Changelog

All notable changes to cma are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] (1.0.0-dev)

### Added (compound-loop evidence)

- `cma stats --evidence`: composes preventions and leaks into a single loop-closure-rate signal over a trailing window (default 30 days; `--window N` to override). The rate is grounded in surface-event evidence: a prevention counts toward closure only when the miss it links to (via `--miss-id`) was surfaced between its capture and the prevention's capture. Self-attested preventions without that chain are reported separately and do not inflate the rate. Output also shows recurring patterns in the window and the prevention-to-miss linkage rate. The single signal the README's "compound learning is evidence" promise implies, now honestly computable from cma's own data. `--json` emits a structured record (`preventions`, `preventions_linked_to_miss`, `preventions_evidenced`, `leaks`, `loop_closure_rate`, `recurring`) for downstream consumers (dashboards, corpus-stats publishers, other agents).
- Weak-signal soft-match in `cma stats --leaks`. The strong-leak threshold now requires both `surface` and `fm` to be present and equal on miss and prior surface event. When surface matches but `fm` is absent on one side, the result is reported as a weak signal in a separate block, not as a leak. Reduces the silent zero-leak case for operators who capture without `--fm`.
- Preventions composed into `cma stats --recurrence` and `cma stats --leaks`. Each prevention with `miss_id` attributes one catch to the miss's `(surface, fm)` pair. The recurrence view now annotates each recurring pair with `(caught: N, catch-rate: P%)`. The leak view annotates each leak with `Caught on this pair: N`. A pair with high catch-rate alongside recurrence is the loop working most of the time but slipping occasionally, framed correctly instead of "the prevention is not working."

### Added (storage and benchmarks)

- `cma init` warns when `$CMA_DIR` matches a cloud-sync path shape (Dropbox, iCloud Drive, OneDrive, Google Drive, pCloud) or a network filesystem type (NFS, CIFS / SMB, sshfs). Advisory; init still succeeds. DATA.md gains a Storage requirements subsection naming supported / unsupported filesystems.
- DATA.md atomicity paragraph corrected: kernel-level append serialization on Linux and macOS is stronger than the PIPE_BUF floor the prior wording implied. The bash test suite already exercises 200 concurrent processes writing 64 KiB records and verifies all land valid.
- `bench.sh` reports min / p50 / p95 / p99 over `N=100` timed iterations per operation (after 3 warmup runs) instead of single-sample p95. New `--json` flag emits a machine-readable record carrying operation latencies, host kernel/CPU/filesystem fingerprint, and timestamp, suitable for tracking results over time. README Performance section no longer carries a fixed table; describes the methodology and points at `bench.sh --json` for actual numbers.

### Added (toolchain honesty)

- README requirements line declares `python3` 3.10 or newer as a hard runtime dependency. The "no package-manager dependencies" framing was true but understated: cma shells out to python3 for JSON encoding and JSONL queries on every capture and every stats view.
- CI matrix runs `test.sh` against Python 3.10, 3.11, and 3.12 in parallel (`fail-fast: false`).

### Initial 1.0 surface

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
- Shell wrapper (`hooks/cma-pre`) implementing the action-time injection architecture for zsh and bash environments. Native preexec integration (zsh) or via bash-preexec library (bash). Manual invocation supported. `CMA_PRE_TRIGGERS` env var overrides the default trigger command list. Failure-isolated (cma missing or errored does not block the wrapped command), bounded latency (5-second timeout on cma queries), surface detection consistent with the Claude Code hook.
- `cma stats --behavior`: behavior-layer validation view. Reads texture-preserved misses (those captured with `--intended` and `--corrected`), groups by surface/fm, and surfaces representative pivots. Makes the behavior layer of the validation framework (ARCHITECTURE.md Section 5.2) computable from cma's own data without external tooling. Recurring pivots in the same surface/fm pair are evidence that surfaced warnings consistently change operator behavior.
- Performance benchmarks (`bench.sh`) measuring `cma-pre --check`, `cma surface`, and `cma stats` latency against a synthetic 100-capture data set. All operations measured under 50ms at p95, validating the ARCHITECTURE.md Section 6 latency target with concrete numbers rather than aspirational claims. Uses Python `time.perf_counter` for portability and warmup iterations to discount cold-start.
- Decision applies-when matching: `cma surface` now matches decisions by their `applies_when` field against context keywords. A decision with `applies_when="auth db"` surfaces whenever surface or file context contains "auth" or "db", even if the decision's stored surface differs. Closes the decision-surfacing loop: decisions surface at the moment their conditions match (action time), not only at session start or when explicitly queried by stored surface. Matching is decision-specific; misses and other capture types unchanged. Documented in ARCHITECTURE.md Section 2.3.
- Claude Code SessionStart hook (`hooks/claude-code-session-start.sh`): surfaces priming context at the start of each session — recurring failure patterns and active rejections by default, optionally behavior pivots. Configurable via `CMA_SESSION_START_SECTIONS` env var. Together with the PreToolUse hook, covers both ends of the action-time injection theme: session-boundary context and per-action surfacing during work. ARCHITECTURE.md Section 3.1a.

### Reliability and forward-compatibility (Phase 1 polish)

- Schema versioning on all captures: every record (miss, decision, rejection, prevention, core learning, surface event) now includes `"schema_version":"1.0"` as the first field. Future schema changes can gate migrations against this field. Forward-looking polish for 3-year corpus stability.
- Atomic write semantics: capture writes use a single python3 `f.write` syscall on the fully-composed JSON record. Atomic for records under PIPE_BUF (typically 4096 bytes); best-effort atomic for longer texture-bearing records. Replaces the prior bash `>>` append, which could interleave on long writes from concurrent cma processes.
- Tolerant read: corrupted JSONL lines are skipped with a per-file stderr warning of the form `cma: skipped N corrupted line(s) in <file>`, instead of breaking the entire query. The corpus stays usable even when individual records are damaged. Implemented in `cma surface` and `cma stats --leaks`; remaining query paths (recurrence, behavior, distill --review, distill --retire) silently skip with corruption counters that will surface in Phase 2 polish.

### Methodology integration (loose-coupling polish)

- Documentation sanitization: removed Lodestone-coined failure-shape names from cma's docs and code examples (replaced with `<failure-shape>` placeholders or `fm-1` generic tags). Documentation now explicitly states cma is methodology-agnostic and references Lodestone as the canonical methodology when present. Protects the methodology asset by keeping the catalog where it belongs (in Lodestone), not replicated in cma's docs.
- `CMA_FM_CLASSIFIER` plugin hook: when set and `--fm` is not provided, `cma miss` invokes the configured shell command with description on stdin and uses its first line of stdout as the failure-mode tag. Failure-isolated (5-second timeout, classifier errors do not block the capture). External wiring; cma ships no classifier. Documented in ARCHITECTURE.md Section 9. Enables operators to wire methodology-aware classification (Lodestone-aware or otherwise) without coupling cma to any specific methodology.

### Operator confidence (Phase 2 polish)

- DATA.md: complete schema documentation for the data directory. Layout, per-record-type schemas with examples, schema versioning policy, atomicity guarantees, tolerant-read behavior, backup recommendations, and migration policy for future schema versions. The contract for the durable corpus.
- `cma init` command: explicitly creates `~/.cma/` with an inline README pointing to DATA.md. Idempotent. Operators can run `cma init` immediately after install instead of waiting for first capture to materialize the directory.
- Test suite (`test.sh`) with 42 cases covering all functional paths, edge cases (special characters, missing args, unknown flags), and JSON validity.
- CI workflow (GitHub Actions) running the test suite on every push and pull request.
- DESIGN.md specifying the seven-primitive surface and the migration from the working version.
- README with quick-start, status, and license information.

### Pending for 1.0.0 (lift checklist)

The seven-primitive surface is functional and frozen in this dev
branch; the `1.0.0-dev` suffix on `VERSION` reflects the items below
that gate the lift, not unfinished feature work.

- Zenodo DOI allocation (one-time GitHub-Zenodo integration in repo
  settings; first DOI fires on the next published release tag).
- `cma 1.0.0` release tag (`cma-1.0.0`) cut and a corresponding
  CHANGELOG.md `[1.0.0]` entry replacing this `[Unreleased]` block.
- Cross-component release notes covering the cma-mcp 0.1 lift if
  the two ship in the same window (see `cma-mcp/CHANGELOG.md`).

### Future (post-1.0)
- Counterfactual capture: explicit "what was about to happen versus what happened" data structure for studying basin transitions.
- Per-project data scoping: optional separation of captures by project rather than a single global directory.
- Trained classifier on accumulated labeled corpus (long-term, requires data accumulation).
