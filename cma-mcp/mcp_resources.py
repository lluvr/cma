"""
Resource read handlers.

Resources are read-only context surfaces an MCP client can pull at
will. cma-mcp ships four:

    cma://decisions   active decisions in window
    cma://rejections  active rejections in window
    cma://core        active core learnings (retired filtered)
    cma://stats       compound-practice stats summary

Reads bypass the bash cma subprocess and parse JSONL directly via
cma_jsonl. The exception is `cma://stats`, which shells out to
`cma stats` so the summary text matches what an operator would see
in their terminal — drift between the resource and the CLI would
violate STRATEGY DD-1.

cma 1.0 is single-project (per-project scoping is on cma's roadmap
beyond 1.0). cma-mcp follows: no project filtering at v0.1; all
records in the operator's `~/.cma/` surface to the operator's MCP
clients. When cma adds project scoping, cma-mcp will follow.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import cma_jsonl
import mcp_compose
from cma_subprocess import CmaError, run_cma


DECISIONS_LOOKBACK_DAYS = 180
DECISIONS_LIMIT = 30

REJECTIONS_LOOKBACK_DAYS = 30
REJECTIONS_LIMIT = 30

CORE_LIMIT = 30


def _cutoff_iso(days: int) -> str:
    """Return ISO-8601 timestamp `days` ago in UTC."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")


def _filter_within_days(records: list[dict], days: int) -> list[dict]:
    """Filter records to those with timestamp >= now - days."""
    cutoff = _cutoff_iso(days)
    return [
        r for r in records
        if isinstance(r.get("timestamp"), str) and r["timestamp"] >= cutoff
    ]


def _newest_first(records: list[dict]) -> list[dict]:
    """Sort records newest-first by timestamp; missing-last."""
    return sorted(records, key=lambda r: r.get("timestamp", ""), reverse=True)


# ── cma://decisions ────────────────────────────────────────────────


def read_decisions() -> dict:
    """Active decisions in window."""
    result = cma_jsonl.read_decisions()
    in_window = _filter_within_days(
        [r for r in result.records if r.get("type") == "decision"],
        DECISIONS_LOOKBACK_DAYS,
    )
    sorted_records = _newest_first(in_window)[:DECISIONS_LIMIT]

    summary = {
        "lookback_days": DECISIONS_LOOKBACK_DAYS,
        "in_window": len(in_window),
        "shown": len(sorted_records),
        "limit": DECISIONS_LIMIT,
    }

    return mcp_compose.compose_resource_response(
        uri="cma://decisions",
        records=sorted_records,
        data_provenance=cma_jsonl.parse_provenance(result),
        summary=summary,
    )


# ── cma://rejections ───────────────────────────────────────────────


def read_rejections() -> dict:
    """Active rejections in window."""
    result = cma_jsonl.read_rejections()
    in_window = _filter_within_days(
        [r for r in result.records if r.get("type") == "rejection"],
        REJECTIONS_LOOKBACK_DAYS,
    )
    sorted_records = _newest_first(in_window)[:REJECTIONS_LIMIT]

    summary = {
        "lookback_days": REJECTIONS_LOOKBACK_DAYS,
        "in_window": len(in_window),
        "shown": len(sorted_records),
        "limit": REJECTIONS_LIMIT,
    }

    return mcp_compose.compose_resource_response(
        uri="cma://rejections",
        records=sorted_records,
        data_provenance=cma_jsonl.parse_provenance(result),
        summary=summary,
    )


# ── cma://core ─────────────────────────────────────────────────────


def read_core() -> dict:
    """
    Active core learnings.

    cma's core.jsonl mixes two record types: `core` (the learning) and
    `retirement` (a marker that retires a core by id). A core is
    active iff no retirement record references its id.
    """
    result = cma_jsonl.read_core()
    cores = [r for r in result.records if r.get("type") == "core"]
    retired_ids = {
        r.get("retires")
        for r in result.records
        if r.get("type") == "retirement" and isinstance(r.get("retires"), str)
    }
    active = [c for c in cores if c.get("id") not in retired_ids]
    sorted_records = _newest_first(active)[:CORE_LIMIT]

    summary = {
        "active": len(active),
        "retired": len(cores) - len(active),
        "shown": len(sorted_records),
        "limit": CORE_LIMIT,
    }

    return mcp_compose.compose_resource_response(
        uri="cma://core",
        records=sorted_records,
        data_provenance=cma_jsonl.parse_provenance(result),
        summary=summary,
    )


# ── cma://stats ────────────────────────────────────────────────────


def read_stats() -> dict:
    """
    Default stats summary.

    Shells out to `cma stats` so the summary text matches what an
    operator would see in their terminal. Other views (leaks,
    recurrence, behavior, etc.) go through the cma_stats tool with a
    `view` argument.
    """
    try:
        result = run_cma(["stats"])
        return mcp_compose.compose_stats_response(
            view="default",
            cma_stdout=result.stdout,
            cma_stderr=result.stderr,
            extra_provenance={
                "cma_argv": result.argv,
                "cma_returncode": result.returncode,
            },
        )
    except CmaError as exc:
        return mcp_compose.compose_error_response(
            tool_or_uri="cma://stats",
            reason=exc.reason,
            detail=exc.stderr or str(exc),
        )


# ── dispatch ────────────────────────────────────────────────────────


READERS = {
    "cma://decisions": read_decisions,
    "cma://rejections": read_rejections,
    "cma://core": read_core,
    "cma://stats": read_stats,
}


def read(uri: str) -> dict:
    """Dispatch a resource read by URI."""
    reader = READERS.get(uri)
    if reader is None:
        return mcp_compose.compose_error_response(
            tool_or_uri=uri,
            reason="unknown_resource",
            detail=f"no resource reader registered for uri: {uri}",
            is_user_error=True,
        )
    return reader()
