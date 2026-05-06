"""
Resource read tests.

Exercise the JSONL parser and resource composers without invoking the
bash cma subprocess. cma://stats is the exception (it shells out);
its tests live in test_subprocess.py.
"""

from __future__ import annotations

import json

import cma_jsonl
import mcp_resources


def test_decisions_resource_returns_three_section_payload(seeded_cma_dir):
    payload = mcp_resources.read("cma://decisions")
    assert set(payload.keys()) == {"analysis", "agent_guidance", "provenance"}
    assert payload["analysis"]["uri"] == "cma://decisions"
    assert payload["analysis"]["record_count"] == 1
    assert payload["analysis"]["records"][0]["id"] == "20260502-110000-bbbb2222"


def test_rejections_resource_returns_three_section_payload(seeded_cma_dir):
    payload = mcp_resources.read("cma://rejections")
    assert payload["analysis"]["record_count"] == 1
    assert payload["analysis"]["records"][0]["id"] == "20260503-120000-cccc3333"


def test_core_resource_filters_retired_via_retirement_records(seeded_cma_dir):
    payload = mcp_resources.read("cma://core")
    # The seed has 2 cores + 1 retirement targeting the second core.
    # Active core surfaces; retired core does not.
    summary = payload["analysis"]["summary"]
    assert summary["active"] == 1
    assert summary["retired"] == 1
    ids = [r["id"] for r in payload["analysis"]["records"]]
    assert "20260301-090000-eeee5555" in ids
    assert "20260302-090000-ffff6666" not in ids


def test_resource_handles_missing_file_gracefully(isolated_cma_dir):
    """An empty CMA_DIR returns empty record_count, not an error."""
    payload = mcp_resources.read("cma://decisions")
    assert payload["analysis"]["record_count"] == 0
    assert payload["provenance"]["data_source"]["exists"] is False


def test_corrupt_lines_are_skipped_and_counted(isolated_cma_dir):
    """A corrupt line is counted in provenance, not raised."""
    decisions_path = isolated_cma_dir / "decisions.jsonl"
    valid = {
        "schema_version": "1.0",
        "type": "decision",
        "id": "20260601-080000-corrup99",
        "timestamp": "2026-06-01T08:00:00Z",
        "description": "VALID: a real decision body that satisfies validation",
    }
    with open(decisions_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(valid) + "\n")
        fh.write("this line is not valid json\n")
        fh.write(json.dumps(valid) + "\n")  # second valid record

    payload = mcp_resources.read("cma://decisions")
    assert payload["analysis"]["record_count"] == 2
    assert payload["provenance"]["data_source"]["corrupt_lines_skipped"] == 1


def test_unknown_schema_version_surfaces_in_provenance(isolated_cma_dir):
    decisions_path = isolated_cma_dir / "decisions.jsonl"
    record = {
        "schema_version": "9.9",
        "type": "decision",
        "id": "20260601-080000-future99",
        "timestamp": "2026-06-01T08:00:00Z",
        "description": "FROM_FUTURE: a record the parser does not know",
    }
    with open(decisions_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")

    payload = mcp_resources.read("cma://decisions")
    assert "9.9" in payload["provenance"]["data_source"]["unknown_schema_versions"]


def test_legacy_record_no_schema_version_parses_leniently(isolated_cma_dir):
    decisions_path = isolated_cma_dir / "decisions.jsonl"
    legacy = {
        "type": "decision",
        "id": "20251201-080000-legacy00",
        "timestamp": "2025-12-01T08:00:00Z",
        "description": "LEGACY: a record from before schema_version was introduced",
    }
    with open(decisions_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(legacy) + "\n")

    payload = mcp_resources.read("cma://decisions")
    assert payload["analysis"]["record_count"] == 1
    assert payload["provenance"]["data_source"]["legacy_records_no_schema_version"] == 1


def test_unknown_resource_uri_returns_error_payload(isolated_cma_dir):
    payload = mcp_resources.read("cma://does-not-exist")
    assert payload["analysis"]["error"] is True
    assert payload["analysis"]["reason"] == "unknown_resource"


def test_jsonl_reader_returns_empty_on_missing_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("CMA_DIR", str(tmp_path / "does-not-exist"))
    result = cma_jsonl.read_decisions()
    assert result.records == []
    assert result.file_existed is False
