"""
JSON-RPC 2.0 over stdio for the Model Context Protocol.

Per DECISIONS AD-001: cma-mcp implements MCP directly without a
third-party SDK. The protocol surface used here is small enough
(initialize, tools/list, tools/call, resources/list, resources/read,
ping, notifications) that an in-repo implementation removes a class
of version-skew failures and keeps cma-mcp's runtime dependency
footprint at zero.

This module owns the I/O loop and the envelope discipline. It does
not know about cma-specific tools or resources; mcp_server registers
handlers and this module dispatches.

Transport contract:

- Each line on stdin is exactly one JSON-RPC request or notification.
- Each response is exactly one line on stdout, JSON-encoded, no
  embedded newlines (json.dumps default).
- Notifications (no `id` field) receive no response.
- stderr is for logging only; protocol traffic never touches it.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any, Callable

import mcp_log


# JSON-RPC 2.0 standard error codes.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# MCP-specific
RESOURCE_NOT_FOUND = -32002


@dataclass
class Request:
    """A parsed JSON-RPC request or notification."""

    method: str
    params: dict
    id: Any = None  # missing for notifications

    @property
    def is_notification(self) -> bool:
        return self.id is None


class ProtocolError(Exception):
    """Raised when a request cannot be processed; carries JSON-RPC code."""

    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)


def parse_line(line: str) -> Request:
    """
    Parse a single JSON-RPC line into a Request.

    Raises ProtocolError on parse or shape errors. Returned id is
    None for notifications, otherwise carries the request id (string,
    integer, or null per JSON-RPC 2.0).
    """
    try:
        msg = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ProtocolError(PARSE_ERROR, f"parse error: {exc}", None)

    if not isinstance(msg, dict):
        raise ProtocolError(INVALID_REQUEST, "request must be an object")
    if msg.get("jsonrpc") != "2.0":
        raise ProtocolError(INVALID_REQUEST, "jsonrpc must be '2.0'")
    method = msg.get("method")
    if not isinstance(method, str) or not method:
        raise ProtocolError(INVALID_REQUEST, "method must be a non-empty string")
    params = msg.get("params") or {}
    if not isinstance(params, dict):
        raise ProtocolError(INVALID_PARAMS, "params must be an object")
    return Request(method=method, params=params, id=msg.get("id"))


def write_response(req_id: Any, result: dict) -> None:
    """Write a JSON-RPC success response to stdout."""
    payload = {"jsonrpc": "2.0", "id": req_id, "result": result}
    _write(payload)


def write_error(req_id: Any, code: int, message: str, data: Any = None) -> None:
    """Write a JSON-RPC error response to stdout."""
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    payload = {"jsonrpc": "2.0", "id": req_id, "error": err}
    _write(payload)


def _write(payload: dict) -> None:
    """Serialize and write a single JSON-RPC envelope on one line."""
    # ensure_ascii=False so unicode passes through; default behavior
    # of json.dumps already produces no embedded newlines.
    line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    print(line, file=sys.stdout, flush=True)


# ── server loop ────────────────────────────────────────────────────


# Handler signature: (params: dict) -> dict (the result body).
# Notification handlers take params and return None.
Handler = Callable[[dict], dict]
NotificationHandler = Callable[[dict], None]


class Dispatcher:
    """Method registry plus stdio loop."""

    def __init__(self) -> None:
        self._request_handlers: dict[str, Handler] = {}
        self._notification_handlers: dict[str, NotificationHandler] = {}

    def on_request(self, method: str, handler: Handler) -> None:
        """Register a handler for a request method."""
        self._request_handlers[method] = handler

    def on_notification(self, method: str, handler: NotificationHandler) -> None:
        """Register a handler for a notification method."""
        self._notification_handlers[method] = handler

    def serve_forever(self) -> int:
        """
        Read lines from stdin and dispatch until EOF or an
        unrecoverable error.

        Returns
        -------
        int
            Exit code: 0 on clean EOF, non-zero if the loop terminates
            from an unhandled error.
        """
        mcp_log.info("loop_start")
        for raw_line in sys.stdin:
            line = raw_line.strip()
            if not line:
                continue
            self._dispatch_one(line)
        mcp_log.info("loop_eof")
        return 0

    def _dispatch_one(self, line: str) -> None:
        """Parse, route, and respond to a single JSON-RPC line."""
        try:
            req = parse_line(line)
        except ProtocolError as exc:
            # Parse errors carry no id (we never read one); per
            # JSON-RPC the response id is null.
            write_error(None, exc.code, exc.message, exc.data)
            mcp_log.warn("parse_error", code=exc.code, message=exc.message)
            return

        if req.is_notification:
            handler = self._notification_handlers.get(req.method)
            if handler is None:
                # Notifications without handlers are silently ignored
                # per JSON-RPC 2.0; log so operators can debug.
                mcp_log.debug("notification_ignored", method=req.method)
                return
            try:
                handler(req.params)
            except Exception as exc:
                # Notifications cannot return errors; log and move on.
                mcp_log.error(
                    "notification_handler_failed",
                    method=req.method,
                    error=str(exc),
                )
            return

        # Request: must produce a response.
        handler = self._request_handlers.get(req.method)
        if handler is None:
            write_error(
                req.id,
                METHOD_NOT_FOUND,
                f"method not found: {req.method}",
            )
            mcp_log.warn("method_not_found", method=req.method)
            return

        try:
            result = handler(req.params)
        except ProtocolError as exc:
            write_error(req.id, exc.code, exc.message, exc.data)
            mcp_log.warn(
                "request_protocol_error",
                method=req.method,
                code=exc.code,
                message=exc.message,
            )
            return
        except Exception as exc:
            # Unexpected handler crash. Surface as INTERNAL_ERROR
            # without leaking the traceback to clients (which would
            # be a debug-info disclosure on remote-MCP setups).
            mcp_log.error(
                "request_handler_failed",
                method=req.method,
                error=str(exc),
            )
            write_error(
                req.id,
                INTERNAL_ERROR,
                "internal server error",
                {"hint": "check cma-mcp stderr logs"},
            )
            return

        write_response(req.id, result)
