"""
MCP protocol conformance tests.

Pin the surface that clients see: initialize handshake, tools/list,
resources/list, ping, error envelopes for unknown methods and
invalid params. These tests do not exercise bash cma; tool dispatch
that runs the subprocess lives in test_subprocess.py.
"""

from __future__ import annotations

import json

import mcp_protocol
import mcp_server
from conftest import call_handler


def test_initialize_returns_protocol_and_serverinfo(fresh_dispatcher):
    result = call_handler(fresh_dispatcher, "initialize", {"protocolVersion": "2024-11-05"})
    assert result["protocolVersion"] == mcp_server.PROTOCOL_VERSION
    assert result["serverInfo"]["name"] == "cma-mcp"
    assert result["serverInfo"]["version"] == mcp_server.SERVER_VERSION
    assert "capabilities" in result
    assert result["capabilities"]["tools"]["listChanged"] is False
    assert result["capabilities"]["resources"]["listChanged"] is False
    # The instructions field is the cross-tool orientation prose;
    # clients with UI may surface it.
    assert isinstance(result["instructions"], str)
    assert "cma-mcp" in result["instructions"]
    assert "cma_miss" in result["instructions"]


def test_server_version_is_strict_semver():
    """Per CHANGELOG / SERVER_VERSION discipline, version is M.m.p only."""
    parts = mcp_server.SERVER_VERSION.split(".")
    assert len(parts) == 3, f"SERVER_VERSION must be M.m.p; got {mcp_server.SERVER_VERSION}"
    for p in parts:
        assert p.isdigit(), f"SERVER_VERSION component must be digits; got {p}"


def test_tools_list_carries_seven_tools(fresh_dispatcher):
    result = call_handler(fresh_dispatcher, "tools/list")
    names = sorted(t["name"] for t in result["tools"])
    assert names == sorted([
        "cma_miss",
        "cma_decision",
        "cma_reject",
        "cma_prevented",
        "cma_distill",
        "cma_surface",
        "cma_stats",
    ])
    # Every tool carries description + inputSchema fields the MCP spec requires.
    for tool in result["tools"]:
        assert isinstance(tool["description"], str) and len(tool["description"]) > 50
        assert tool["inputSchema"]["type"] == "object"


def test_tool_descriptions_reference_lodestone_for_methodology(fresh_dispatcher):
    """
    Per DECISIONS AD-006: cma-mcp does not bundle Lodestone vocabulary.
    The fm field on cma_miss (and cma_prevented) is where FM tagging
    surfaces; that field's description must reference Lodestone as
    the canonical methodology rather than enumerating the catalog.
    """
    result = call_handler(fresh_dispatcher, "tools/list")
    cma_miss = next(t for t in result["tools"] if t["name"] == "cma_miss")
    fm_field_desc = cma_miss["inputSchema"]["properties"]["fm"]["description"]
    assert "lodestone" in fm_field_desc.lower(), (
        "fm field must point to Lodestone as the canonical methodology"
    )
    # The description must NOT define what each FM means (bundling the
    # catalog inverts canon-vs-companion separation per DECISIONS AD-006).
    # Brief reference to FM-1..10 as an example tag namespace is OK;
    # an enumeration of definitions is not. We probe by checking for
    # the disambiguation prose ("Speed Over Understanding", etc.) that
    # would only appear if the catalog were bundled.
    forbidden_definitions = [
        "Speed Over Understanding",
        "Component Over Journey",
        "Happy Path Only",
        "Assumption Over Verification",
    ]
    for definition in forbidden_definitions:
        assert definition not in fm_field_desc, (
            f"fm description bundles Lodestone vocabulary ({definition!r}); "
            "remove the definition and reference Lodestone instead"
        )


def test_cma_stats_view_enum_includes_evidence(fresh_dispatcher):
    """
    bash cma exposes `cma stats --evidence`; the MCP wrapper must
    pass it through. Without this, the central evidence signal is
    unreachable from any MCP-connected client.
    """
    result = call_handler(fresh_dispatcher, "tools/list")
    cma_stats = next(t for t in result["tools"] if t["name"] == "cma_stats")
    view_enum = cma_stats["inputSchema"]["properties"]["view"]["enum"]
    assert "evidence" in view_enum, (
        f"evidence view missing from cma_stats enum: {view_enum}"
    )


def test_every_string_field_has_max_length(fresh_dispatcher):
    """
    Every string input field must carry maxLength. An MCP client (or
    a misbehaving agent) that sends an unbounded payload would either
    fill the operator's data dir or trip the OS ARG_MAX limit on
    subprocess exec. Bounded fields force a clean schema-level error
    instead.
    """
    result = call_handler(fresh_dispatcher, "tools/list")
    failures = []
    for tool in result["tools"]:
        for prop_name, prop in tool["inputSchema"].get("properties", {}).items():
            if prop.get("type") != "string":
                continue
            # enum is a strictly tighter constraint than maxLength
            # (value must be in a small fixed set); fields bounded by
            # enum do not also need maxLength.
            if "enum" in prop:
                continue
            if "maxLength" not in prop:
                failures.append(f"{tool['name']}.{prop_name} missing maxLength")
            elif not isinstance(prop["maxLength"], int) or prop["maxLength"] <= 0:
                failures.append(
                    f"{tool['name']}.{prop_name} maxLength is not a positive int: "
                    f"{prop['maxLength']!r}"
                )
    assert not failures, "\n".join(failures)


def test_resources_list_carries_four_resources(fresh_dispatcher):
    result = call_handler(fresh_dispatcher, "resources/list")
    uris = sorted(r["uri"] for r in result["resources"])
    assert uris == sorted([
        "cma://decisions",
        "cma://rejections",
        "cma://core",
        "cma://stats",
    ])


def test_ping_returns_empty(fresh_dispatcher):
    assert call_handler(fresh_dispatcher, "ping") == {}


def test_unknown_method_emits_method_not_found_via_dispatch_one(
    fresh_dispatcher, capsys
):
    line = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "does/not/exist"})
    fresh_dispatcher._dispatch_one(line)
    out = capsys.readouterr().out.strip()
    assert out, "dispatcher must emit a response on stdout"
    payload = json.loads(out)
    assert payload["id"] == 1
    assert payload["error"]["code"] == mcp_protocol.METHOD_NOT_FOUND


def test_invalid_jsonrpc_line_emits_parse_error(fresh_dispatcher, capsys):
    fresh_dispatcher._dispatch_one("this is not json")
    out = capsys.readouterr().out.strip()
    payload = json.loads(out)
    assert payload["id"] is None
    assert payload["error"]["code"] == mcp_protocol.PARSE_ERROR


def test_resources_read_unknown_uri_emits_resource_not_found(fresh_dispatcher):
    import pytest

    with pytest.raises(mcp_protocol.ProtocolError) as excinfo:
        call_handler(fresh_dispatcher, "resources/read", {"uri": "cma://nope"})
    assert excinfo.value.code == mcp_protocol.RESOURCE_NOT_FOUND


def test_tools_call_unknown_tool_is_invalid_params(fresh_dispatcher):
    import pytest

    with pytest.raises(mcp_protocol.ProtocolError) as excinfo:
        call_handler(
            fresh_dispatcher,
            "tools/call",
            {"name": "cma_does_not_exist", "arguments": {}},
        )
    assert excinfo.value.code == mcp_protocol.INVALID_PARAMS


def test_tools_call_missing_name_is_invalid_params(fresh_dispatcher):
    import pytest

    with pytest.raises(mcp_protocol.ProtocolError) as excinfo:
        call_handler(fresh_dispatcher, "tools/call", {"arguments": {}})
    assert excinfo.value.code == mcp_protocol.INVALID_PARAMS


def test_initialize_notification_does_not_crash(fresh_dispatcher):
    handler = fresh_dispatcher._notification_handlers.get("notifications/initialized")
    assert handler is not None
    # Notifications return None and must not raise.
    assert handler({}) is None


def test_git_sha_falls_back_to_baked_build_info(monkeypatch, tmp_path):
    """When the runtime git probe fails (PyPI install layout — no `.git`
    next to the script), `_git_sha()` must fall back to the build-time
    value baked into `_build_info.BUILD_GIT_SHA` by `setup.py`.

    Without this fallback, the install fingerprint silently degrades
    to `git_sha: null` on the most common install path, weakening the
    forensic-traceability claim documented in cma-mcp/README.md.
    """
    import subprocess as _subprocess
    import sys

    def _always_fail(*args, **kwargs):
        raise FileNotFoundError("git probe disabled for this test")

    monkeypatch.setattr(_subprocess, "check_output", _always_fail)

    fake_module = type(sys)("_build_info")
    fake_module.BUILD_GIT_SHA = "deadbeefcafefade1234567890abcdef00000000"
    monkeypatch.setitem(sys.modules, "_build_info", fake_module)

    assert mcp_server._git_sha() == "deadbeefcafefade1234567890abcdef00000000"


def test_git_sha_returns_none_when_no_runtime_and_no_baked(monkeypatch):
    """If the runtime probe fails AND no `_build_info` is importable
    (or its baked SHA is empty), `_git_sha()` must return None so the
    fingerprint surfaces the missing trace as `git_sha: null` honestly.
    """
    import subprocess as _subprocess
    import sys

    def _always_fail(*args, **kwargs):
        raise FileNotFoundError("git probe disabled for this test")

    monkeypatch.setattr(_subprocess, "check_output", _always_fail)

    empty_module = type(sys)("_build_info")
    empty_module.BUILD_GIT_SHA = ""
    monkeypatch.setitem(sys.modules, "_build_info", empty_module)

    assert mcp_server._git_sha() is None
