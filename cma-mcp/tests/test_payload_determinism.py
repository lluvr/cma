"""
Three-section payload determinism.

Pin the discipline: every tool response and every resource read
returns `{analysis, agent_guidance, provenance}`. Provenance carries
the canonical fields. Tests here are the load-bearing assertions
that catch any future change which silently breaks the pattern.
"""

from __future__ import annotations

import mcp_compose
import mcp_resources


REQUIRED_TOP_KEYS = {"analysis", "agent_guidance", "provenance"}
REQUIRED_PROVENANCE_KEYS = {
    "server_name",
    "server_version",
    "protocol_version",
    "license",
    "cost_usd",
    "citation",
    "deterministic",
    "timestamp",
}


def _assert_three_section(payload: dict) -> None:
    assert set(payload.keys()) == REQUIRED_TOP_KEYS, (
        f"payload top-level keys must equal {REQUIRED_TOP_KEYS}; got {set(payload.keys())}"
    )
    assert isinstance(payload["analysis"], dict)
    assert isinstance(payload["agent_guidance"], dict)
    assert isinstance(payload["provenance"], dict)


def _assert_provenance_canonical(provenance: dict) -> None:
    missing = REQUIRED_PROVENANCE_KEYS - set(provenance.keys())
    assert not missing, f"provenance missing required keys: {missing}"
    assert provenance["server_name"] == "cma-mcp"
    assert provenance["license"] == "Apache-2.0"
    assert provenance["cost_usd"] == 0.0
    assert provenance["deterministic"] is True
    assert "Clarethium" in provenance["citation"]


def _setup_provenance() -> None:
    mcp_compose.configure_provenance(
        server_name="cma-mcp",
        server_version="0.1.0",
        protocol_version="2024-11-05",
        git_sha="test-sha-abc12345",
    )


def test_capture_response_is_three_section():
    _setup_provenance()
    payload = mcp_compose.compose_capture_response(
        tool_name="cma_miss",
        record=None,
        cma_stdout="recorded miss",
        cma_stderr="",
    )
    _assert_three_section(payload)
    _assert_provenance_canonical(payload["provenance"])
    # Capture-tool guidance must name the cite discipline.
    assert "cite" in payload["agent_guidance"]["how_to_cite_faithfully"].lower()


def test_surface_response_is_three_section():
    _setup_provenance()
    payload = mcp_compose.compose_surface_response(
        matched=[],
        cma_stdout="no matches",
        cma_stderr="",
        filters={"surface": "auth"},
    )
    _assert_three_section(payload)
    _assert_provenance_canonical(payload["provenance"])
    assert payload["analysis"]["filters"]["surface"] == "auth"


def test_stats_response_is_three_section():
    _setup_provenance()
    payload = mcp_compose.compose_stats_response(
        view="default",
        cma_stdout="counts...",
        cma_stderr="",
    )
    _assert_three_section(payload)
    _assert_provenance_canonical(payload["provenance"])


def test_resource_response_is_three_section():
    _setup_provenance()
    payload = mcp_compose.compose_resource_response(
        uri="cma://decisions",
        records=[],
        data_provenance={"file": "/tmp/x", "exists": False, "records_parsed": 0},
    )
    _assert_three_section(payload)
    _assert_provenance_canonical(payload["provenance"])
    assert "data_source" in payload["provenance"]


def test_error_response_is_three_section():
    _setup_provenance()
    payload = mcp_compose.compose_error_response(
        tool_or_uri="cma_miss",
        reason="missing_binary",
        detail="cma not on PATH",
    )
    _assert_three_section(payload)
    _assert_provenance_canonical(payload["provenance"])
    assert payload["analysis"]["error"] is True


def test_provenance_git_sha_included_when_configured():
    _setup_provenance()
    payload = mcp_compose.compose_stats_response(
        view="default",
        cma_stdout="",
        cma_stderr="",
    )
    assert payload["provenance"]["git_sha"] == "test-sha-abc12345"


def test_every_resource_uri_produces_three_section_payload(seeded_cma_dir):
    """
    Each resource (except cma://stats which shells out) goes
    through the read path with a real seeded corpus. All must
    produce a three-section payload.
    """
    _setup_provenance()
    for uri in ["cma://decisions", "cma://rejections", "cma://core"]:
        payload = mcp_resources.read(uri)
        _assert_three_section(payload)
        _assert_provenance_canonical(payload["provenance"])


def test_provenance_timestamp_is_iso8601_zulu():
    _setup_provenance()
    payload = mcp_compose.compose_stats_response(
        view="default",
        cma_stdout="",
        cma_stderr="",
    )
    ts = payload["provenance"]["timestamp"]
    # YYYY-MM-DDTHH:MM:SS.NNNNNNZ (microsecond ISO 8601 UTC)
    assert ts.endswith("Z")
    assert ts[4] == "-" and ts[7] == "-" and ts[10] == "T"
    # Round-trip through datetime to confirm it parses as ISO 8601
    from datetime import datetime
    parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    assert parsed.microsecond is not None
