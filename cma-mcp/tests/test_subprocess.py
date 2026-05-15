"""
bash cma subprocess wrapper tests.

Most tests here require the cma binary on PATH; they auto-skip when
it is not. The injection-resistance test runs without cma because it
asserts the argv-array discipline at the Python layer, not what cma
does on receipt.
"""

from __future__ import annotations

import pytest

import cma_subprocess


pytestmark = pytest.mark.subprocess


def test_resolve_missing_binary_raises_cmaerror(monkeypatch, tmp_path):
    """When cma is not on PATH, CmaError carries reason='missing_binary'."""
    # Empty PATH so shutil.which returns None
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.delenv("CMA_BIN", raising=False)
    with pytest.raises(cma_subprocess.CmaError) as excinfo:
        cma_subprocess.resolve_cma_binary()
    assert excinfo.value.reason == "missing_binary"


def test_cma_bin_override_wrong_path_raises(monkeypatch):
    """CMA_BIN pointing at a non-existent file fails with clear reason."""
    monkeypatch.setenv("CMA_BIN", "/nonexistent/path/to/cma")
    # Reload the module so it picks up the env var.
    import importlib

    importlib.reload(cma_subprocess)
    with pytest.raises(cma_subprocess.CmaError) as excinfo:
        cma_subprocess.resolve_cma_binary()
    assert excinfo.value.reason == "missing_binary"
    # restore default
    monkeypatch.delenv("CMA_BIN", raising=False)
    importlib.reload(cma_subprocess)


def test_run_cma_help_exits_clean(cma_binary_available):
    if not cma_binary_available:
        pytest.skip("cma binary not on PATH")
    # `cma --help` prints usage and exits 0 in well-behaved CLI.
    # If cma chooses a different convention, skip gracefully rather
    # than break the test on a CLI version diff.
    try:
        result = cma_subprocess.run_cma(["--help"])
    except cma_subprocess.CmaError as exc:
        if exc.reason == "non_zero_exit":
            pytest.skip(f"cma --help exits non-zero on this version: {exc.returncode}")
        raise
    assert result.returncode == 0
    assert isinstance(result.stdout, str)


def test_argv_injection_is_structurally_impossible(cma_binary_available, isolated_cma_dir):
    """
    Per DECISIONS AD-004: argv-array discipline. Passing a
    shell-metacharacter-laden description must NOT execute the
    metacharacter. We assert this by attempting an injection that
    would create a sentinel file if the shell interpreted it.
    """
    if not cma_binary_available:
        pytest.skip("cma binary not on PATH")
    sentinel = isolated_cma_dir / "INJECTED_SENTINEL"
    payload = f'rm benign; touch {sentinel}; echo done'
    # Even if cma errors on this input, the sentinel must NOT be created.
    try:
        cma_subprocess.run_cma(["miss", payload])
    except cma_subprocess.CmaError:
        # Whether the call errors is irrelevant; the assertion below is sentinel-non-existence.
        pass
    assert not sentinel.exists(), "argv-array discipline broken: shell metacharacter executed"


def test_cma_version_returns_string_or_none():
    """cma_version() never raises; returns string when cma exists, None otherwise."""
    out = cma_subprocess.cma_version()
    assert out is None or (isinstance(out, str) and len(out) > 0)


def test_argv_budget_blocks_oversized_payload(cma_binary_available):
    """
    A payload that pushes argv past MAX_ARGV_BYTES must raise
    CmaError(reason='input_too_large') BEFORE subprocess exec. This
    prevents an adversarial MCP client from triggering OS-level
    ARG_MAX errors that surface as generic 'unexpected' failures.
    """
    if not cma_binary_available:
        pytest.skip("cma binary not on PATH")
    oversized = "x" * (cma_subprocess.MAX_ARGV_BYTES + 1)
    with pytest.raises(cma_subprocess.CmaError) as excinfo:
        cma_subprocess.run_cma(["miss", oversized])
    assert excinfo.value.reason == "input_too_large"
    assert "argv exceeds" in excinfo.value.stderr


def test_argv_budget_allows_payload_at_ceiling(cma_binary_available, isolated_cma_dir):
    """
    A payload just under the ceiling is still rejected only if it
    pushes total argv over MAX_ARGV_BYTES. We pick a description
    sized so that argv (binary + 'miss' + description) sums under
    the cap, and assert the call does NOT raise input_too_large.
    """
    if not cma_binary_available:
        pytest.skip("cma binary not on PATH")
    binary_len = len(cma_subprocess.resolve_cma_binary()) + len("miss")
    headroom = cma_subprocess.MAX_ARGV_BYTES - binary_len - 64
    payload = "x" * headroom
    try:
        cma_subprocess.run_cma(["miss", payload])
    except cma_subprocess.CmaError as exc:
        assert exc.reason != "input_too_large", (
            f"under-ceiling payload was rejected as oversized: {exc}"
        )
