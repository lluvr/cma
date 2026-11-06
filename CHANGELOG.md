# Changelog

All notable changes to cma are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Fixed

- The Claude Code `PreToolUse` hook now prints its captures as `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": ...}}`. Claude Code adds plain stdout to the model's context only for events such as `SessionStart` and `UserPromptSubmit`; for `PreToolUse` it went to the debug log, so the per-action captures never reached the assistant. The hook also logs a surface event only when it actually emitted captures.
- `cma stats --rejections` and `--preventions` no longer log surface events. They are read-only views, and the `SessionStart` hook calls `--rejections` every session, which inflated the event log with entries that were never action-time warnings.
- `cma stats --evidence` now uses the same leak rule as `cma stats --leaks`: surface and fm both present and equal. Previously an absent fm on both sides matched (`"" == ""`), so the two views disagreed on the same corpus.
- `cma stats --evidence` prints the counts behind the closure rate and marks it self-attested; `--json` adds `loop_closure_evidenced`, `loop_closure_denominator`, and `loop_closure_basis`.
- The fm classifier, `hooks/cma-pre`, and the `SessionStart` hook no longer require GNU `timeout`. On stock macOS it is absent, so the hooks printed nothing and the classifier never ran. They now fall back to `gtimeout`, then to a python3 time limit that kills the whole process group.
- A flag given without its value (`cma miss "x" --surface`) now exits 1 with "`--surface requires a value`" instead of a bash `unbound variable` error.
- `cma surface --limit` now requires a positive integer. `abc` raised a Python traceback and `-1` silently dropped the oldest result.
- `cma install-hook` shell-quotes the hook paths it writes, so a checkout path containing a space works, and refuses a `settings.json` whose `hooks`, `hooks.SessionStart`, or `hooks.PreToolUse` has the wrong JSON type with a clear message instead of a traceback.
- `cma miss`, `decision`, `reject`, and `prevented` reject an empty description, matching cma-mcp.

### Changed

- Repository home moved to a personal account (`lluvr/cma`). Self-references, badges, and issue/security links updated; author and publisher framing is now personal (organization publisher attribution dropped).
- Zenodo DOI references removed from `CITATION.cff` pending re-issuance under the new account; `SECURITY.md`'s publisher-identity claim softened accordingly.
- Repository layout: the deep-dive docs (`DESIGN`, `ARCHITECTURE`, `DATA`, `DECISIONS`, `GOVERNANCE`) moved under `docs/`, and `test.sh` / `bench.sh` moved under `scripts/`. All internal references updated.

---

## [1.1.0] - 2026-05-25

### Added

- `cma install-hook --claude-code [--scope user|project] [--dry-run]` merges cma's `SessionStart` and `PreToolUse` hook blocks into Claude Code's `settings.json`. Idempotent; preserves any other hooks you have configured; writes a `.bak` of the prior file. `--dry-run` prints the merged JSON to stdout without writing.

---

## [1.0.0] - 2026-05-15

cma 1.0 reference implementation. The surface defined in [DESIGN.md](docs/DESIGN.md) is locked and complete.

### Surface

- Seven primitives: `cma miss`, `cma decision`, `cma reject`, `cma prevented` (captures); `cma surface`, `cma distill`, `cma stats` (operations).
- `cma id <type>` helper prints the id of the most recent capture of a given type, optionally scoped by `--surface`. Composes cleanly into `--miss-id "$(cma id miss)"`.

### Evidence

- `cma stats --evidence`: loop-closure rate over a trailing window (default 30 days; `--window N` to override). The rate is grounded in surface-event evidence: a prevention counts toward closure only when the miss it links to (via `--miss-id`) was surfaced between its capture and the prevention's capture. Self-attested preventions without that chain are reported separately and do not inflate the rate. `--json` emits a structured record (`preventions`, `preventions_linked_to_miss`, `preventions_evidenced`, `leaks`, `loop_closure_rate`, `recurring`) for dashboards, corpus-stats publishers, and other agents.
- `cma stats --recurrence`: pattern detection grouped by `(surface, fm)` with `(caught: N, catch-rate: P%)` annotation derived from prevention linkage. Defaults to all-time; `--window N` scopes to a trailing window.
- `cma stats --leaks`: strong (surface+fm match) and weak (surface match, fm absent on one side) signal classification. Each leak carries `Caught on this pair: N` for context.
- `cma stats --behavior`: behavior pivots from texture-preserved misses, grouped by surface/fm.

### Action-time injection

- Five-stage architecture (interception, context extraction, query, injection, logging) specified in [ARCHITECTURE.md](docs/ARCHITECTURE.md). Reference implementations:
  - Claude Code: `hooks/claude-code-pre-tool-use.sh` (per-action surfacing) and `hooks/claude-code-session-start.sh` (session priming with recurrence + active rejections, optionally behavior pivots).
  - Shell: `hooks/cma-pre` for zsh (native `preexec`) and bash (via `bash-preexec`), with manual-wrap support.
- Failure-isolated: hook errors never block the wrapped action; 5-second timeout on cma queries.
- Decision `applies_when` matching: a decision with `applies_when="auth"` surfaces whenever the current action's surface or file path contains "auth", even if the decision's stored surface differs.

### Data substrate

- JSONL append-only at `$CMA_DIR/{misses,decisions,rejections,preventions,core,surface_events}.jsonl`. Schema versioned (`"schema_version": "1.0"` on every record).
- Atomic appends. The test suite exercises 200 concurrent processes writing 64 KiB records; all land valid.
- Tolerant reads: corrupted lines are skipped with a per-file stderr warning; queries continue with remaining records.
- Texture preservation on misses: `--excerpt`, `--intended`, `--corrected` for behavior-layer analysis.
- `cma init` warns when `$CMA_DIR` matches a cloud-sync path (Dropbox, iCloud Drive, OneDrive, Google Drive, pCloud) or a network filesystem type (NFS, CIFS/SMB, sshfs). DATA.md documents supported/unsupported filesystems.

### Methodology integration

- `--fm` is an opaque string. cma stores it without interpretation; vocabulary lives in the methodology, not in cma.
- `CMA_FM_CLASSIFIER` env var plugs in an external classifier (any shell command that reads description on stdin and emits an fm tag on stdout). Failure-isolated with a 5-second timeout; classifier errors do not block the capture.

### Operations

- bash test suite (130 cases) covers all functional paths, edge cases (special characters, missing args, unknown flags), JSON validity, hook integration, shell wrapper modes, and the leak/evidence joins.
- `bench.sh`: latency benchmark across `cma surface`, `cma stats`, and `cma-pre --check` against a 100-capture synthetic corpus. Reports min / p50 / p95 / p99 over N=100 timed iterations after 3 warmup runs. `--json` emits a structured record carrying operation latencies, host kernel/CPU/filesystem fingerprint, and timestamp.
- CI: matrix on Python 3.10, 3.11, 3.12; shellcheck lint on `cma`, `test.sh`, `bench.sh`, hooks; canon-audit on every push.
- `cma --version`, `cma --help`, `cma init` for setup and orientation.

### Documentation

- [DESIGN.md](docs/DESIGN.md): seven-primitive surface, argument semantics, output expectations.
- [ARCHITECTURE.md](docs/ARCHITECTURE.md): five-stage action-time injection contract, data shapes, validation framework, quality criteria for integrations.
- [DATA.md](docs/DATA.md): per-record-type schemas with examples, schema versioning policy, atomicity guarantees, tolerant-read behavior, storage requirements, backup recommendations, migration policy.
- [DECISIONS.md](docs/DECISIONS.md): architectural decision records.

### Roadmap

- Counterfactual capture: explicit data structure for studying basin transitions beyond intended/corrected pairs.
- Per-project data scoping: optional separation of captures by project rather than a single global directory.
- Recency-weighted surface ranking.
- Trained classifier on accumulated labeled corpus (long-term; requires data accumulation).
