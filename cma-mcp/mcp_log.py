"""
Stderr logging helper.

cma-mcp logs to stderr because stdio is reserved for the MCP protocol
itself. MCP clients capture stderr separately; operators inspecting
the logs use their client's MCP-server logs view.

Format: ISO-8601 UTC timestamp + level + key=value pairs. Single
line per event. Timestamps are normalized to second resolution to
keep determinism tests stable across machines.

The module-level logger instance is shared across all callers; this
matches the singleton stderr stream and avoids duplicate handler
attachment.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any


_LEVEL = os.environ.get("CMA_MCP_LOG_LEVEL", "INFO").upper()
_LEVELS = {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40, "OFF": 100}
_LEVEL_NUM = _LEVELS.get(_LEVEL, 20)


def _now_iso() -> str:
    """Return UTC ISO-8601 timestamp at microsecond resolution."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _emit(level: str, event: str, fields: dict[str, Any]) -> None:
    """Write a single log line to stderr."""
    parts = [f"{k}={_format_value(v)}" for k, v in fields.items() if v is not None]
    line = f"[{_now_iso()}] {level} event={event}"
    if parts:
        line += " " + " ".join(parts)
    print(line, file=sys.stderr, flush=True)


def _format_value(v: Any) -> str:
    """Render a log value: quote strings with whitespace, otherwise raw."""
    s = str(v)
    if " " in s or "=" in s or "\t" in s:
        # Replace newlines so multi-line values stay on one log line.
        s = s.replace("\n", "\\n").replace("\r", "")
        return f'"{s}"'
    return s


def info(event: str, **fields: Any) -> None:
    if _LEVEL_NUM <= 20:
        _emit("INFO", event, fields)


def warn(event: str, **fields: Any) -> None:
    if _LEVEL_NUM <= 30:
        _emit("WARN", event, fields)


def error(event: str, **fields: Any) -> None:
    if _LEVEL_NUM <= 40:
        _emit("ERROR", event, fields)


def debug(event: str, **fields: Any) -> None:
    if _LEVEL_NUM <= 10:
        _emit("DEBUG", event, fields)
