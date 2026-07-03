"""
Shared pytest fixtures.

The flat-modules layout (per pyproject.toml [tool.setuptools]
py-modules) means cma-mcp's source files live at the repo root, not
under a package directory. Tests sit in tests/ and reach the modules
via sys.path injection here.
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ── env isolation ─────────────────────────────────────────────────


@pytest.fixture
def isolated_cma_dir(tmp_path, monkeypatch):
    """
    Point CMA_DIR at a temp directory so JSONL reads run against a
    known-empty corpus. Does not invoke the bash cma binary; tests
    that need the binary use the `cma_binary_available` fixture.
    """
    monkeypatch.setenv("CMA_DIR", str(tmp_path))
    yield tmp_path


def days_ago(n: int) -> str:
    """ISO-8601 UTC timestamp n days in the past.

    Fixture seeds use relative timestamps so records never age out of
    the resources' lookback windows. The previous fixed seeds rotted:
    the 2026-05-03 rejection aged past REJECTIONS_LOOKBACK_DAYS (30)
    in June 2026 and silently broke the suite.
    """
    stamp = datetime.now(timezone.utc) - timedelta(days=n)
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def seeded_cma_dir(isolated_cma_dir):
    """
    Returns a temp CMA_DIR pre-seeded with a small, schema-1.0 corpus
    covering each record type. Tests build assertions against this
    fixed seed.
    """
    seeds = {
        "misses.jsonl": [
            {
                "schema_version": "1.0",
                "type": "miss",
                "id": "20260501-100000-aaaa1111",
                "timestamp": days_ago(6),
                "description": "claimed verified without testing the cross-tenant write path",
                "surface": "auth",
                "fm": "FM-3",
            },
        ],
        "decisions.jsonl": [
            {
                "schema_version": "1.0",
                "type": "decision",
                "id": "20260502-110000-bbbb2222",
                "timestamp": days_ago(5),
                "description": "AUTH: JWT over sessions because stateless scales horizontally",
                "surface": "auth",
                "applies_when": "auth jwt",
            },
        ],
        "rejections.jsonl": [
            {
                "schema_version": "1.0",
                "type": "rejection",
                "id": "20260503-120000-cccc3333",
                "timestamp": days_ago(4),
                "description": "GraphQL: overhead for this project",
                "surface": "api",
                "revisit_when": "if mobile clients are added",
            },
        ],
        "preventions.jsonl": [
            {
                "schema_version": "1.0",
                "type": "prevention",
                "id": "20260504-130000-dddd4444",
                "timestamp": days_ago(3),
                "description": "almost claimed verified, ran the cross-tenant test instead",
                "miss_id": "20260501-100000-aaaa1111",
            },
        ],
        "core.jsonl": [
            {
                "schema_version": "1.0",
                "type": "core",
                "id": "20260301-090000-eeee5555",
                "timestamp": days_ago(20),
                "description": "Always check JWT expiration in auth middleware",
                "scope": "general",
                "surface": "auth",
            },
            {
                "schema_version": "1.0",
                "type": "core",
                "id": "20260302-090000-ffff6666",
                "timestamp": days_ago(19),
                "description": "Centralize model identifiers to config; never hardcode",
                "scope": "general",
                "surface": "general",
            },
            {
                "schema_version": "1.0",
                "type": "retirement",
                "id": "20260401-100000-9999aaaa",
                "timestamp": days_ago(10),
                "retires": "20260302-090000-ffff6666",
                "pattern": "model identifiers",
            },
        ],
    }
    for filename, records in seeds.items():
        path = isolated_cma_dir / filename
        with open(path, "w", encoding="utf-8") as fh:
            for r in records:
                fh.write(json.dumps(r) + "\n")
    yield isolated_cma_dir


# ── subprocess availability ──────────────────────────────────────


@pytest.fixture(scope="session")
def cma_binary_available() -> bool:
    """True iff the canonical cma binary is on PATH."""
    return shutil.which("cma") is not None


# ── helpers ─────────────────────────────────────────────────────────


@pytest.fixture
def fresh_dispatcher(monkeypatch):
    """
    Build a Dispatcher with the server's handlers wired, with
    provenance configured. Tests can call dispatcher._dispatch_one
    or build a JSON-RPC line and feed it via the same path.
    """
    # Re-import so any module-level state is fresh.
    import importlib

    import mcp_compose
    import mcp_server

    importlib.reload(mcp_compose)
    importlib.reload(mcp_server)

    mcp_compose.configure_provenance(
        server_name=mcp_server.SERVER_NAME,
        server_version=mcp_server.SERVER_VERSION,
        protocol_version=mcp_server.PROTOCOL_VERSION,
        git_sha=None,
    )
    return mcp_server._build_dispatcher()


def call_handler(dispatcher, method: str, params: dict | None = None) -> dict:
    """
    Invoke a request handler and return its result body.
    Bypasses the JSON-RPC envelope serializer for direct assertions.
    """
    handler = dispatcher._request_handlers.get(method)
    assert handler is not None, f"no handler registered for {method}"
    return handler(params or {})
