# cma Data Directory

This document specifies the layout and schema of cma's data directory, the durable artifact of compound practice. The data is the asset; the tool is the interface. This document is the contract for what's in `~/.cma/`.

The default data directory is `~/.cma/`, overridable with the `CMA_DIR` environment variable. cma creates the directory on first capture; running `cma init` creates it explicitly with a README placed inside.

## 1. Layout

```
$CMA_DIR/
├── misses.jsonl              Captures of failures (cma miss)
├── decisions.jsonl           Captures of architectural choices (cma decision)
├── rejections.jsonl          Captures of eliminated options (cma reject)
├── preventions.jsonl         Captures of caught warnings (cma prevented)
├── core.jsonl                Distilled learnings + retirements (cma distill)
└── surface_events.jsonl      Surface query events (logged by cma surface)
```

All files are JSON Lines (JSONL): one JSON object per line, append-only, never edited in place. The format is durable, recoverable line by line, and parseable by any JSON-aware tool.

## 2. Schema

Every record begins with `schema_version`, `type`, `id`, and `timestamp`. Type-specific fields follow.

### 2.1 Common fields

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | string | Schema version. Currently `"1.0"`. Future schema changes gate migrations against this. |
| `type` | string | Record type: `miss`, `decision`, `rejection`, `prevention`, `core`, `retirement`, `surface_event`. |
| `id` | string | Unique record ID, format `YYYYMMDD-HHMMSS-<8-hex>`. UTC timestamp + random suffix. |
| `timestamp` | string | ISO 8601 UTC, format `YYYY-MM-DDTHH:MM:SSZ`. |
| `description` | string | One-line statement of what the record captures. Required on captures; not present on retirement and surface_event records. |

### 2.2 Miss

Captures a failure. Written by `cma miss`.

```json
{
  "schema_version": "1.0",
  "type": "miss",
  "id": "20260505-...",
  "timestamp": "2026-05-05T...",
  "description": "...",
  "surface": "auth",
  "fm": "assumption-over-verification",
  "files": "src/auth/jwt.ts",
  "intended": "patch only the failing test",
  "corrected": "trace upstream defect, fix at root",
  "excerpt": "operator: ...\nassistant: ..."
}
```

Optional fields: `surface`, `fm`, `files`, `intended`, `corrected`, `excerpt`. Texture fields (`intended`, `corrected`, `excerpt`) preserve the conditions of failure and enable behavior-layer validation analysis (`cma stats --behavior`).

### 2.3 Decision

Captures an architectural or strategic choice. Written by `cma decision`.

```json
{
  "schema_version": "1.0",
  "type": "decision",
  "id": "20260505-...",
  "timestamp": "2026-05-05T...",
  "description": "TOPIC: choice (rationale)",
  "surface": "infra",
  "applies_when": "auth db migration"
}
```

Optional fields: `surface`, `applies_when`. The `applies_when` predicate is matched against context keywords at action time so the decision surfaces when its conditions are met (see ARCHITECTURE.md Section 2.3).

### 2.4 Rejection

Captures an eliminated option. Written by `cma reject`.

```json
{
  "schema_version": "1.0",
  "type": "rejection",
  "id": "20260505-...",
  "timestamp": "2026-05-05T...",
  "description": "OPTION: reason for elimination",
  "surface": "infra",
  "revisit_when": "if performance becomes critical"
}
```

Optional fields: `surface`, `revisit_when`.

### 2.5 Prevention

Captures a moment where a surfaced warning prevented a recurrence. Written by `cma prevented`.

```json
{
  "schema_version": "1.0",
  "type": "prevention",
  "id": "20260505-...",
  "timestamp": "2026-05-05T...",
  "description": "almost X, did Y instead",
  "miss_id": "20260504-...",
  "warning_id": "20260504-..."
}
```

Optional fields: `miss_id`, `warning_id`. Linking a prevention to its original miss enables the miss's prevention rate to be computed (process-layer validation).

### 2.6 Core learning

A promoted learning that surfaces permanently. Written by `cma distill <learning>`.

```json
{
  "schema_version": "1.0",
  "type": "core",
  "id": "20260505-...",
  "timestamp": "2026-05-05T...",
  "description": "the distilled rule",
  "scope": "project",
  "surface": "general"
}
```

Optional fields: `scope`, `surface`.

### 2.7 Retirement

Marks a core learning as retired. Written by `cma distill --retire <pattern>`. Retirements live in `core.jsonl` alongside core learnings; `cma surface` filters them out automatically.

```json
{
  "schema_version": "1.0",
  "type": "retirement",
  "id": "20260505-...",
  "timestamp": "2026-05-05T...",
  "retires": "20260504-...",
  "pattern": "auth"
}
```

Required fields: `retires` (the ID of the core learning being retired), `pattern` (the substring that matched). No `description` field.

### 2.8 Surface event

Records a `cma surface` invocation and what it matched. Written automatically by `cma surface` (suppressible with `--no-log`). Used by `cma stats --leaks` to detect failures despite surfaced warnings.

```json
{
  "schema_version": "1.0",
  "type": "surface_event",
  "id": "20260505-...",
  "timestamp": "2026-05-05T...",
  "filter_surface": "auth",
  "filter_file": "",
  "filter_type": "",
  "filter_limit": 3,
  "matched": [
    {"id": "...", "type": "miss", "surface": "auth", "fm": "..."}
  ]
}
```

`matched` may be empty (the surface query found no records). Empty events are still recorded as evidence that surfacing was attempted.

## 3. Schema versioning policy

The schema follows semantic versioning.

- **Patch versions** (1.0.x): clarifications to documentation, no record changes.
- **Minor versions** (1.x.0): backward-compatible additions. Old records remain valid; readers ignore unknown fields. Examples: adding optional fields to existing record types, adding new record types.
- **Major versions** (x.0.0): breaking changes. Old records may require migration. cma will provide migration tooling at the major version boundary.

Readers MUST gracefully ignore unknown fields. A reader written against schema 1.0 should still parse schema 1.1 records, treating new fields as opaque metadata.

The current schema version is `1.0`. There are currently no announced schema changes.

## 4. Atomicity and durability

cma writes records via a single `write()` syscall on the encoded record bytes. POSIX guarantees atomicity for `write()` calls up to `PIPE_BUF` (typically 4096 bytes on Linux). Records exceeding `PIPE_BUF` (rare; possible with long `excerpt` fields) may interleave under concurrent writes from multiple cma processes.

For single-operator usage with manual or hook-driven captures, concurrent-write risk is negligible. Future versions may add `fcntl.flock`-based locking for multi-process scenarios.

## 5. Tolerant reads

Queries (`cma surface`, `cma stats`, `cma distill --review`, etc.) tolerate corrupted lines: a JSON parse failure on a single line is reported via stderr (`cma: skipped N corrupted line(s) in <file>`) and the query continues with the remaining records. The corpus stays usable even when individual records are damaged.

Empty lines are silently ignored, not counted as corruption.

## 6. Backup recommendations

The data directory is purely append-only JSONL. Backup is straightforward:

- **Snapshot**: copy the entire `~/.cma/` directory.
- **Incremental**: git-track the directory and commit periodically. The append-only structure makes diffs informative.
- **Synced**: store on a synced filesystem (Dropbox, iCloud, etc.). Concurrent writes across machines may interleave; prefer one machine writing at a time.

The data is plain text JSONL; any tooling that handles JSONL handles cma data.

## 7. Migration to future versions

When cma 2.0 ships, migration tooling will:

1. Read records of any prior schema version.
2. Apply any field renames, type conversions, or structural changes.
3. Write a new file alongside the original (e.g., `misses.jsonl.v2`) without modifying the original.
4. Atomically swap the new file into place after operator confirmation.

Operators choosing to stay on schema 1.0 can do so indefinitely; cma 2.0 readers will continue to parse 1.0 records.

## 8. References

- [DESIGN.md](DESIGN.md): the seven cma 1.0 primitives that produce these records.
- [ARCHITECTURE.md](ARCHITECTURE.md): the action-time injection layer and three-layer validation framework that uses this data.
- [CHANGELOG.md](CHANGELOG.md): record of schema and feature changes over time.
