"""
Wire-protocol subprocess tests.

The other test files dispatch in-process — they exercise handler
logic but never push bytes through real stdin/stdout pipes. This
file closes the gap documented in `docs/ANTICIPATED_CRITIQUES.md`
C-8: spawn cma-mcp as a real subprocess, exchange JSON-RPC over
the standard MCP transport, and pin the framing-level invariants
that an in-process dispatcher cannot see.

Mirrors frame-check-mcp's `test_mcp_adversarial.py` pattern:
construct a real client→server→client roundtrip, fire malformed
and rapid-fire inputs at it, and confirm the server stays
responsive with well-formed JSON-RPC error envelopes throughout.

Tests skip when the bash cma binary is not on PATH because tools/call
exercises the subprocess wrapper end-to-end. ping/initialize/list
methods do not need the binary.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import pytest


HERE = Path(__file__).resolve().parent.parent
SERVER_PATH = HERE / "mcp_server.py"
DEFAULT_TIMEOUT_S = 5.0


class WireServer:
    """A real cma-mcp subprocess driven over stdin/stdout pipes.

    Reads one JSON-RPC line per response. Notifications produce no
    response. The class deliberately stays minimal — it is the
    test's leverage point, not a general-purpose MCP client.
    """

    def __init__(self, cma_dir: Path):
        env = os.environ.copy()
        env["CMA_DIR"] = str(cma_dir)
        self.proc = subprocess.Popen(
            [sys.executable, str(SERVER_PATH)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            bufsize=0,
        )
        self._next_id = 1

    def send_line(self, line: str) -> None:
        """Write an arbitrary line to the server's stdin (no framing)."""
        self.proc.stdin.write((line + "\n").encode("utf-8"))
        self.proc.stdin.flush()

    def send_request(self, method: str, params: dict | None = None) -> int:
        """Send a JSON-RPC request, return its id."""
        req_id = self._next_id
        self._next_id += 1
        line = json.dumps(
            {"jsonrpc": "2.0", "id": req_id, "method": method,
             "params": params or {}}
        )
        self.send_line(line)
        return req_id

    def send_notification(self, method: str, params: dict | None = None) -> None:
        line = json.dumps({"jsonrpc": "2.0", "method": method,
                           "params": params or {}})
        self.send_line(line)

    def read_reply(self, timeout_s: float = DEFAULT_TIMEOUT_S) -> dict:
        """Read one JSON-RPC line. Raises if the server closes the pipe."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            line = self.proc.stdout.readline()
            if line:
                return json.loads(line)
            if self.proc.poll() is not None:
                stderr = self.proc.stderr.read().decode("utf-8", errors="replace")
                raise AssertionError(
                    f"server exited with code {self.proc.returncode}; "
                    f"stderr=\n{stderr}"
                )
        raise AssertionError(f"no reply within {timeout_s}s")

    def call(self, method: str, params: dict | None = None) -> dict:
        """Send a request and read its reply. Convenience for the common case."""
        req_id = self.send_request(method, params)
        reply = self.read_reply()
        assert reply.get("id") == req_id, (
            f"id mismatch: sent {req_id}, got {reply.get('id')}"
        )
        return reply

    def close(self) -> None:
        try:
            if self.proc.stdin and not self.proc.stdin.closed:
                self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=2)


@contextmanager
def wire_server(cma_dir: Path) -> Iterator[WireServer]:
    server = WireServer(cma_dir)
    try:
        yield server
    finally:
        server.close()


# ── handshake & negotiation ────────────────────────────────────────


def test_initialize_handshake_over_real_stdio(tmp_path):
    with wire_server(tmp_path) as server:
        reply = server.call("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "wire-test", "version": "0"},
        })
        assert reply["jsonrpc"] == "2.0"
        result = reply["result"]
        assert result["protocolVersion"] == "2024-11-05"
        assert result["serverInfo"]["name"] == "cma-mcp"
        assert "capabilities" in result
        # Instructions field surfaces cross-tool orientation prose.
        assert "cma-mcp" in result["instructions"]


def test_initialized_notification_does_not_emit_a_response(tmp_path):
    """Notifications are one-way per JSON-RPC 2.0; no reply must
    appear on stdout, even if the server logs them on stderr."""
    with wire_server(tmp_path) as server:
        server.call("initialize", {"protocolVersion": "2024-11-05"})
        server.send_notification("notifications/initialized", {})
        # If the server incorrectly emitted a response, the next
        # request's reply would have a stale id. Send a real ping
        # and confirm we get exactly the matching id back.
        ping_reply = server.call("ping")
        assert "result" in ping_reply
        assert ping_reply["result"] == {}


# ── catalog discovery ────────────────────────────────────────────


def test_tools_list_returns_seven_tools_over_wire(tmp_path):
    with wire_server(tmp_path) as server:
        server.call("initialize", {"protocolVersion": "2024-11-05"})
        reply = server.call("tools/list")
        names = sorted(t["name"] for t in reply["result"]["tools"])
        assert names == sorted([
            "cma_miss", "cma_decision", "cma_reject", "cma_prevented",
            "cma_distill", "cma_surface", "cma_stats",
        ])


def test_resources_list_returns_four_resources_over_wire(tmp_path):
    with wire_server(tmp_path) as server:
        server.call("initialize", {"protocolVersion": "2024-11-05"})
        reply = server.call("resources/list")
        uris = sorted(r["uri"] for r in reply["result"]["resources"])
        assert uris == sorted([
            "cma://core", "cma://decisions",
            "cma://rejections", "cma://stats",
        ])


# ── error envelope discipline ────────────────────────────────────


def test_unknown_method_emits_method_not_found_envelope(tmp_path):
    with wire_server(tmp_path) as server:
        reply = server.call("does/not/exist")
        assert "error" in reply
        # JSON-RPC 2.0 method-not-found is -32601.
        assert reply["error"]["code"] == -32601
        assert "result" not in reply


def test_malformed_json_line_emits_parse_error_and_server_stays_alive(tmp_path):
    """A garbage line must produce a parse-error envelope (id null
    per JSON-RPC 2.0), and the server must remain responsive to
    subsequent valid requests."""
    with wire_server(tmp_path) as server:
        server.send_line("this is not json {")
        reply = server.read_reply()
        assert reply["id"] is None
        assert reply["error"]["code"] == -32700  # PARSE_ERROR
        # Server must still answer a clean request afterwards.
        ping = server.call("ping")
        assert "result" in ping


def test_tools_call_unknown_tool_emits_invalid_params(tmp_path):
    with wire_server(tmp_path) as server:
        server.call("initialize", {"protocolVersion": "2024-11-05"})
        reply = server.call("tools/call", {
            "name": "cma_does_not_exist",
            "arguments": {},
        })
        assert "error" in reply
        # MCP servers map "unknown tool name" to JSON-RPC invalid-params
        # (-32602) per MCP convention.
        assert reply["error"]["code"] == -32602


def test_resources_read_unknown_uri_emits_resource_not_found(tmp_path):
    with wire_server(tmp_path) as server:
        server.call("initialize", {"protocolVersion": "2024-11-05"})
        reply = server.call("resources/read", {"uri": "cma://nope"})
        assert "error" in reply
        # MCP-specific code for resource-not-found.
        assert reply["error"]["code"] == -32002


# ── framing robustness ────────────────────────────────────────────


def test_rapid_fire_sequential_requests_keep_correct_id_pairing(tmp_path):
    """Send 10 requests back-to-back without waiting between sends.
    The server must read them in order and reply in order. Pinning
    this catches framing-level bugs (e.g., a buffered reader that
    swallows or merges lines)."""
    with wire_server(tmp_path) as server:
        server.call("initialize", {"protocolVersion": "2024-11-05"})
        sent_ids = [server.send_request("ping") for _ in range(10)]
        replies = [server.read_reply() for _ in sent_ids]
        for sent, reply in zip(sent_ids, replies):
            assert reply["id"] == sent, (
                f"out-of-order reply: expected id {sent}, got {reply}"
            )
            assert "result" in reply


def test_oversized_request_does_not_crash_the_server(tmp_path):
    """A 64 KiB description on cma_miss must either round-trip or
    error cleanly via JSON-RPC; the server must not exit, hang, or
    emit malformed output."""
    big = "x" * (64 * 1024)
    with wire_server(tmp_path) as server:
        server.call("initialize", {"protocolVersion": "2024-11-05"})
        reply = server.call("tools/call", {
            "name": "cma_miss",
            "arguments": {"description": big, "surface": "general"},
        }, )
        # We tolerate either path: a clean isError payload (cma
        # rejected the input) or a successful capture. Not allowed:
        # absent reply, mangled JSON, server crash.
        assert "result" in reply or "error" in reply
        # Server must remain responsive.
        ping = server.call("ping")
        assert "result" in ping


def test_server_continues_after_a_burst_of_malformed_lines(tmp_path):
    """Three malformed lines in a row, then a valid request. The
    server must answer all three with parse-error envelopes (id
    null) and then return a normal result for the valid request."""
    with wire_server(tmp_path) as server:
        for _ in range(3):
            server.send_line("garbage }{")
            reply = server.read_reply()
            assert reply["id"] is None
            assert reply["error"]["code"] == -32700
        ping = server.call("ping")
        assert "result" in ping


# ── tool dispatch end-to-end (requires bash cma) ───────────────────


@pytest.mark.subprocess
def test_tools_call_cma_stats_round_trips_three_section_payload(
    tmp_path, cma_binary_available,
):
    """Full-stack invocation: client → cma-mcp dispatch → bash cma
    subprocess → mcp_compose → JSON-RPC reply. Pins the empty-corpus
    case (no captures yet) so the test does not depend on the
    operator's data."""
    if not cma_binary_available:
        pytest.skip("cma binary not on PATH")
    with wire_server(tmp_path) as server:
        server.call("initialize", {"protocolVersion": "2024-11-05"})
        reply = server.call("tools/call", {
            "name": "cma_stats",
            "arguments": {"view": "default"},
        })
        result = reply["result"]
        # MCP tools/call returns content[] with type="text" carrying
        # the JSON-stringified payload.
        assert "content" in result
        text = result["content"][0]["text"]
        payload = json.loads(text)
        assert set(payload.keys()) >= {"analysis", "agent_guidance",
                                        "provenance"}
        assert payload["provenance"]["server_name"] == "cma-mcp"
        assert payload["provenance"]["cost_usd"] == 0.0
        assert payload["provenance"]["deterministic"] is True
        # cma_argv is the audit trail: the exact argv the wrapper
        # passed to cma. On an empty corpus the call still succeeds.
        assert payload["provenance"]["cma_returncode"] == 0
        assert payload["provenance"]["cma_argv"][-1] == "stats"
