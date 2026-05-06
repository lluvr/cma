"""
JSONL reader for cma's data directory.

cma writes append-only JSON Lines files to `$CMA_DIR/` (default
`~/.cma/`):

    misses.jsonl
    decisions.jsonl
    rejections.jsonl
    preventions.jsonl
    core.jsonl
    surface_events.jsonl

Schema is documented in cma's DATA.md. This module reads those files
without writing — cma-mcp's tools always shell out to bash cma for
writes; reads happen here directly because they are simpler and
faster than spawning a subprocess for every resource fetch.

Tolerance discipline matches bash cma's own (CHANGELOG, "Tolerant
read"): corrupt lines are skipped with a counter the caller can
surface, never raised as an exception. The whole corpus stays usable
even when individual records are damaged.

Schema-version handling follows DECISIONS AD-002: records with
`schema_version: "1.0"` are native; legacy records with no
schema_version field parse leniently; records with any other
schema_version surface the unknown version to the caller for
inclusion in `provenance`.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Iterator


# The set of schema_versions cma-mcp parses natively. Records with a
# schema_version not in this set are still parsed (best-effort) but
# the unknown version is reported up to the caller so it lands in
# `provenance` for the read.
NATIVE_SCHEMA_VERSIONS: frozenset[str] = frozenset({"1.0"})


def cma_dir() -> str:
    """Return the resolved cma data directory."""
    explicit = os.environ.get("CMA_DIR")
    if explicit:
        return os.path.expanduser(explicit)
    return os.path.expanduser("~/.cma")


@dataclass
class ReadResult:
    """Result of reading a JSONL file: records plus parse provenance."""

    records: list[dict] = field(default_factory=list)
    corrupt_lines: int = 0
    legacy_records: int = 0
    unknown_schema_versions: set[str] = field(default_factory=set)
    file_existed: bool = False
    file_path: str = ""

    def merge_into(self, other: "ReadResult") -> None:
        """Accumulate counts from another read into this one."""
        self.records.extend(other.records)
        self.corrupt_lines += other.corrupt_lines
        self.legacy_records += other.legacy_records
        self.unknown_schema_versions |= other.unknown_schema_versions


def read_jsonl(filename: str) -> ReadResult:
    """
    Read a single JSONL file from cma's data directory.

    Returns a ReadResult with the parsed records and a provenance
    summary. Missing files return an empty result with `file_existed
    = False` rather than raising. Corrupt lines (invalid JSON) are
    skipped and counted.
    """
    path = os.path.join(cma_dir(), filename)
    result = ReadResult(file_path=path)

    if not os.path.exists(path):
        return result

    result.file_existed = True

    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                result.corrupt_lines += 1
                continue

            if not isinstance(record, dict):
                # NDJSON files always carry objects, never bare values
                result.corrupt_lines += 1
                continue

            sv = record.get("schema_version")
            if sv is None:
                result.legacy_records += 1
            elif sv not in NATIVE_SCHEMA_VERSIONS:
                result.unknown_schema_versions.add(str(sv))

            result.records.append(record)

    return result


def read_misses() -> ReadResult:
    return read_jsonl("misses.jsonl")


def read_decisions() -> ReadResult:
    return read_jsonl("decisions.jsonl")


def read_rejections() -> ReadResult:
    return read_jsonl("rejections.jsonl")


def read_preventions() -> ReadResult:
    return read_jsonl("preventions.jsonl")


def read_core() -> ReadResult:
    return read_jsonl("core.jsonl")


def read_surface_events() -> ReadResult:
    return read_jsonl("surface_events.jsonl")


def parse_provenance(result: ReadResult) -> dict:
    """
    Render a ReadResult as a provenance dict suitable for inclusion
    in a three-section payload's `provenance.data_source` field.
    """
    prov: dict = {
        "file": result.file_path,
        "exists": result.file_existed,
        "records_parsed": len(result.records),
    }
    if result.corrupt_lines > 0:
        prov["corrupt_lines_skipped"] = result.corrupt_lines
    if result.legacy_records > 0:
        prov["legacy_records_no_schema_version"] = result.legacy_records
    if result.unknown_schema_versions:
        prov["unknown_schema_versions"] = sorted(result.unknown_schema_versions)
    return prov


def iter_records_sorted_by_timestamp_desc(records: list[dict]) -> Iterator[dict]:
    """Yield records newest first by timestamp field, missing-last."""
    keyed = [(r.get("timestamp", ""), r) for r in records]
    keyed.sort(key=lambda kv: kv[0], reverse=True)
    for _, r in keyed:
        yield r
