"""
cma-mcp: Model Context Protocol server for the cma compound practice loop.

This file is the entry point. It wires together:

- The JSON-RPC over stdio loop (mcp_protocol)
- The tool surface and input schemas (mcp_schema)
- The bash cma subprocess wrapper (cma_subprocess)
- The resource read handlers (mcp_resources)
- The three-section payload composer (mcp_compose)
- Stderr logging (mcp_log)

What makes this MCP server different from a plain tool wrapper
---------------------------------------------------------------
Most MCP tools return raw data. cma-mcp returns a structured
epistemic payload with three sections:

  1. analysis        the data (record captured, query results, etc.)
  2. agent_guidance  what this tool can and cannot tell the agent,
                     and how to cite the output faithfully without
                     paraphrasing it as the agent's own observation
  3. provenance      cma-mcp version, wrapped cma binary version,
                     license, cost (always 0 USD; deterministic),
                     citation string

The agent_guidance and provenance blocks exist because an agent
passing cma-mcp output to a user without attribution would strip
the reproducibility that makes the compound-practice evidence
worth citing.

Protocol
--------
Implements the Model Context Protocol over stdio using JSON-RPC 2.0
line-delimited. No external dependency on an MCP SDK (DECISIONS
AD-001). The protocol surface used here (initialize, tools/list,
tools/call, resources/list, resources/read, ping, notifications) is
small enough that implementing it in-repo keeps cma-mcp
self-contained: no extra install step, no SDK version drift.

License: Apache-2.0. See LICENSE at repo root.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys

import mcp_compose
import mcp_log
import mcp_protocol
import mcp_resources
import mcp_schema
from cma_subprocess import CmaError, cma_version, run_cma


# ── version constants ──────────────────────────────────────────────

# SERVER_VERSION is exposed via the MCP initialize handshake; clients
# see it on connect. Bump on every user-visible capability change.
# Strict M.m.p form (no suffixes here) is enforced by
# tests/test_mcp_server.py::test_server_version_is_strict_semver.
# pyproject.toml carries the PEP 440 .dev0 marker during the dev
# window; at lift the suffix drops and the strings align.
SERVER_NAME = "cma-mcp"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2024-11-05"

# Cross-tool orientation prose for MCP clients whose UI surfaces the
# initialize response's `instructions` field (e.g., Claude Desktop).
# Names the use case, the default invocation shape, and the tool /
# resource set so an agent reading this gets orientation that the
# per-tool descriptions cannot carry.
SERVER_INSTRUCTIONS = (
    "cma-mcp distributes the cma compound practice loop to "
    "MCP-compatible clients. Use cma_miss to record a failure worth "
    "surfacing later, cma_decision for an architectural choice, "
    "cma_reject for an option ruled out, and cma_prevented for a "
    "moment where a surfaced warning changed behavior. Use "
    "cma_surface before substantive work to inherit relevant prior "
    "context (this also logs a surface event used by leak detection). "
    "Use cma_stats and the cma:// resources to inspect the corpus. "
    "cma-mcp is methodology-agnostic: vocabulary lives in Lodestone "
    "(https://github.com/Clarethium/lodestone). Three-section payload "
    "(analysis + agent_guidance + provenance) on every response; "
    "preserve attribution when relaying tool output to the operator."
)


# ── tool dispatch ──────────────────────────────────────────────────


def _to_cma_flag(field_name: str) -> str:
    """Convert a snake_case schema field name to a `--kebab-case` flag."""
    return "--" + field_name.replace("_", "-")


def _build_capture_argv(verb: str, params: dict, optional_fields: list[str]) -> list[str]:
    """
    Build argv for a cma capture verb (miss, decision, reject,
    prevented). The first positional arg is `description`; named
    flags follow.
    """
    description = params.get("description", "")
    if not isinstance(description, str) or len(description) < 1:
        raise mcp_protocol.ProtocolError(
            mcp_protocol.INVALID_PARAMS,
            f"{verb}: description is required and must be a non-empty string",
        )
    argv = [verb, description]
    for field in optional_fields:
        value = params.get(field)
        if value is None:
            continue
        if not isinstance(value, str):
            raise mcp_protocol.ProtocolError(
                mcp_protocol.INVALID_PARAMS,
                f"{verb}: optional field '{field}' must be a string",
            )
        argv.extend([_to_cma_flag(field), value])
    return argv


def _wrap_cma_call(tool_name: str, argv: list[str]) -> dict:
    """Run cma <argv>, compose a three-section response."""
    try:
        result = run_cma(argv)
    except CmaError as exc:
        return mcp_compose.compose_error_response(
            tool_or_uri=tool_name,
            reason=exc.reason,
            detail=exc.stderr or str(exc),
        )
    return mcp_compose.compose_capture_response(
        tool_name=tool_name,
        record=None,
        cma_stdout=result.stdout,
        cma_stderr=result.stderr,
        extra_provenance={
            "cma_argv": result.argv,
            "cma_returncode": result.returncode,
        },
    )


def _handle_cma_miss(params: dict) -> dict:
    argv = _build_capture_argv(
        "miss",
        params,
        optional_fields=["surface", "fm", "files", "intended", "corrected", "excerpt"],
    )
    return _wrap_cma_call("cma_miss", argv)


def _handle_cma_decision(params: dict) -> dict:
    argv = _build_capture_argv(
        "decision",
        params,
        optional_fields=["surface", "applies_when"],
    )
    return _wrap_cma_call("cma_decision", argv)


def _handle_cma_reject(params: dict) -> dict:
    argv = _build_capture_argv(
        "reject",
        params,
        optional_fields=["surface", "revisit_when"],
    )
    return _wrap_cma_call("cma_reject", argv)


def _handle_cma_prevented(params: dict) -> dict:
    argv = _build_capture_argv(
        "prevented",
        params,
        optional_fields=["miss_id", "warning_id"],
    )
    return _wrap_cma_call("cma_prevented", argv)


def _handle_cma_distill(params: dict) -> dict:
    mode = params.get("mode", "default")
    if mode == "review":
        argv = ["distill", "--review"]
    elif mode == "retire":
        pattern = params.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            raise mcp_protocol.ProtocolError(
                mcp_protocol.INVALID_PARAMS,
                "cma_distill mode=retire: 'pattern' is required",
            )
        argv = ["distill", "--retire", pattern]
    elif mode == "default":
        description = params.get("description")
        if not isinstance(description, str) or len(description) < 8:
            raise mcp_protocol.ProtocolError(
                mcp_protocol.INVALID_PARAMS,
                "cma_distill mode=default: 'description' is required (min 8 chars)",
            )
        argv = ["distill", description]
        scope = params.get("scope")
        if scope:
            argv.extend(["--scope", scope])
        surface = params.get("surface")
        if surface:
            argv.extend(["--surface", surface])
    else:
        raise mcp_protocol.ProtocolError(
            mcp_protocol.INVALID_PARAMS,
            f"cma_distill: unknown mode '{mode}'",
        )
    return _wrap_cma_call("cma_distill", argv)


def _handle_cma_surface(params: dict) -> dict:
    argv = ["surface"]
    surface = params.get("surface")
    if surface:
        argv.extend(["--surface", surface])
    file_arg = params.get("file")
    if file_arg:
        argv.extend(["--file", file_arg])
    type_arg = params.get("type")
    if type_arg:
        argv.extend(["--type", type_arg])
    limit = params.get("limit")
    if limit is not None:
        if not isinstance(limit, int) or limit < 1 or limit > 50:
            raise mcp_protocol.ProtocolError(
                mcp_protocol.INVALID_PARAMS,
                "cma_surface: 'limit' must be an integer between 1 and 50",
            )
        argv.extend(["--limit", str(limit)])

    try:
        result = run_cma(argv)
    except CmaError as exc:
        return mcp_compose.compose_error_response(
            tool_or_uri="cma_surface",
            reason=exc.reason,
            detail=exc.stderr or str(exc),
        )
    return mcp_compose.compose_surface_response(
        matched=[],  # cma's stdout carries the rendering; structured matched-list reserved for v0.2
        cma_stdout=result.stdout,
        cma_stderr=result.stderr,
        filters={k: v for k, v in params.items() if v is not None},
        extra_provenance={
            "cma_argv": result.argv,
            "cma_returncode": result.returncode,
        },
    )


def _handle_cma_stats(params: dict) -> dict:
    view = params.get("view", "default")
    valid_views = {"default", "leaks", "recurrence", "preventions", "rejections", "behavior"}
    if view not in valid_views:
        raise mcp_protocol.ProtocolError(
            mcp_protocol.INVALID_PARAMS,
            f"cma_stats: unknown view '{view}' (valid: {sorted(valid_views)})",
        )
    argv = ["stats"]
    if view != "default":
        argv.append(f"--{view}")
    try:
        result = run_cma(argv)
    except CmaError as exc:
        return mcp_compose.compose_error_response(
            tool_or_uri="cma_stats",
            reason=exc.reason,
            detail=exc.stderr or str(exc),
        )
    return mcp_compose.compose_stats_response(
        view=view,
        cma_stdout=result.stdout,
        cma_stderr=result.stderr,
        extra_provenance={
            "cma_argv": result.argv,
            "cma_returncode": result.returncode,
        },
    )


_TOOL_HANDLERS = {
    "cma_miss": _handle_cma_miss,
    "cma_decision": _handle_cma_decision,
    "cma_reject": _handle_cma_reject,
    "cma_prevented": _handle_cma_prevented,
    "cma_distill": _handle_cma_distill,
    "cma_surface": _handle_cma_surface,
    "cma_stats": _handle_cma_stats,
}


# ── MCP method handlers ─────────────────────────────────────────────


def _handle_initialize(params: dict) -> dict:
    """Initialize handshake: return server identity and capabilities."""
    mcp_log.info(
        "initialize",
        client_protocol=params.get("protocolVersion"),
        client_name=(params.get("clientInfo") or {}).get("name"),
    )
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {
            "tools": {"listChanged": False},
            "resources": {"listChanged": False, "subscribe": False},
        },
        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        "instructions": SERVER_INSTRUCTIONS,
    }


def _handle_tools_list(_: dict) -> dict:
    """Return the registered tool list."""
    return {
        "tools": [
            {
                "name": t["name"],
                "title": t.get("title", t["name"]),
                "description": t["description"],
                "inputSchema": t["inputSchema"],
            }
            for t in mcp_schema.TOOLS
        ]
    }


def _handle_tools_call(params: dict) -> dict:
    """Dispatch a tool call by name, return MCP `content`-shaped result."""
    name = params.get("name")
    if not isinstance(name, str):
        raise mcp_protocol.ProtocolError(
            mcp_protocol.INVALID_PARAMS,
            "tools/call: 'name' is required",
        )
    args = params.get("arguments") or {}
    if not isinstance(args, dict):
        raise mcp_protocol.ProtocolError(
            mcp_protocol.INVALID_PARAMS,
            "tools/call: 'arguments' must be an object",
        )

    handler = _TOOL_HANDLERS.get(name)
    if handler is None:
        raise mcp_protocol.ProtocolError(
            mcp_protocol.INVALID_PARAMS,
            f"tools/call: unknown tool '{name}'",
        )

    mcp_log.info("tool_call", tool=name)
    payload = handler(args)
    is_error = bool(payload.get("analysis", {}).get("error"))
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, ensure_ascii=False, indent=2),
            }
        ],
        "isError": is_error,
    }


def _handle_resources_list(_: dict) -> dict:
    """Return the registered resource list."""
    return {
        "resources": [
            {
                "uri": r["uri"],
                "name": r["name"],
                "title": r.get("title", r["name"]),
                "description": r["description"],
                "mimeType": r["mimeType"],
            }
            for r in mcp_schema.RESOURCES
        ]
    }


def _handle_resources_read(params: dict) -> dict:
    """Dispatch a resource read by URI."""
    uri = params.get("uri")
    if not isinstance(uri, str):
        raise mcp_protocol.ProtocolError(
            mcp_protocol.INVALID_PARAMS,
            "resources/read: 'uri' is required",
        )
    if mcp_schema.get_resource(uri) is None:
        raise mcp_protocol.ProtocolError(
            mcp_protocol.RESOURCE_NOT_FOUND,
            f"resources/read: unknown resource uri '{uri}'",
        )
    mcp_log.info("resource_read", uri=uri)
    payload = mcp_resources.read(uri)
    return {
        "contents": [
            {
                "uri": uri,
                "mimeType": "application/json",
                "text": json.dumps(payload, ensure_ascii=False, indent=2),
            }
        ]
    }


def _handle_ping(_: dict) -> dict:
    return {}


def _handle_notification_initialized(_: dict) -> None:
    mcp_log.info("client_initialized")


# ── server bootstrap ────────────────────────────────────────────────


def _git_sha() -> str | None:
    """Resolve the repo's git SHA + dirty flag, or None if unavailable.

    Two paths: the runtime probe (works in a development clone) and a
    build-time-baked fallback (works for installs from a wheel where
    `.git` no longer sits next to the script). The fallback ships in
    `_build_info.py`, generated by `setup.py` at sdist/wheel build time.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=script_dir,
            stderr=subprocess.DEVNULL,
            timeout=2,
        ).decode("utf-8").strip()
        try:
            dirty = subprocess.check_output(
                ["git", "status", "--porcelain"],
                cwd=script_dir,
                stderr=subprocess.DEVNULL,
                timeout=2,
            ).decode("utf-8").strip()
            if dirty:
                sha = sha + "+dirty"
        except Exception:
            # `git status` failure leaves SHA un-suffixed; clean SHA still serves the install fingerprint.
            pass
        return sha
    except Exception:
        pass
    try:
        from _build_info import BUILD_GIT_SHA  # type: ignore[import-not-found]
    except ImportError:
        return None
    sha = (BUILD_GIT_SHA or "").strip()
    return sha or None


def _build_dispatcher() -> mcp_protocol.Dispatcher:
    d = mcp_protocol.Dispatcher()
    d.on_request("initialize", _handle_initialize)
    d.on_request("tools/list", _handle_tools_list)
    d.on_request("tools/call", _handle_tools_call)
    d.on_request("resources/list", _handle_resources_list)
    d.on_request("resources/read", _handle_resources_read)
    d.on_request("ping", _handle_ping)
    d.on_notification("notifications/initialized", _handle_notification_initialized)
    return d


def _emit_version_fingerprint() -> None:
    """
    Print a single-line install fingerprint covering server_version,
    protocol, git_sha (with +dirty flag), cma_binary_version, python,
    and script path. Lets an operator confirm the cma-mcp install
    configured in their MCP client is the expected one.
    """
    fingerprint = {
        "server_name": SERVER_NAME,
        "server_version": SERVER_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "git_sha": _git_sha(),
        "cma_binary_version": cma_version(),
        "python": platform.python_version(),
        "script": os.path.abspath(__file__),
    }
    print(json.dumps(fingerprint, ensure_ascii=False))


def _emit_test_payload() -> None:
    """
    Offline sanity check: print the three-section payload for a
    canned cma_stats default-view call. Useful to verify pipeline
    wiring without an MCP client. Skips gracefully if cma is missing.
    """
    mcp_compose.configure_provenance(
        server_name=SERVER_NAME,
        server_version=SERVER_VERSION,
        protocol_version=PROTOCOL_VERSION,
        git_sha=_git_sha(),
    )
    payload = _handle_cma_stats({"view": "default"})
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def cli() -> int:
    """
    Console entry point. Without flags: speaks MCP over stdio.
    With --version or --test: prints the requested artifact and exits.
    """
    parser = argparse.ArgumentParser(prog="cma-mcp", add_help=True)
    parser.add_argument(
        "--version",
        action="store_true",
        help="emit a single-line install fingerprint and exit",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="emit a canned three-section payload and exit (no MCP client required)",
    )
    args = parser.parse_args()

    if args.version:
        _emit_version_fingerprint()
        return 0
    if args.test:
        _emit_test_payload()
        return 0

    mcp_compose.configure_provenance(
        server_name=SERVER_NAME,
        server_version=SERVER_VERSION,
        protocol_version=PROTOCOL_VERSION,
        git_sha=_git_sha(),
    )
    mcp_log.info("server_start", version=SERVER_VERSION)
    return _build_dispatcher().serve_forever()


if __name__ == "__main__":
    sys.exit(cli())
