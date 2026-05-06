"""
bash cma subprocess wrapper.

Every write through cma-mcp ultimately runs the canonical `cma` bash
binary as a subprocess. Reads (resource fetches) bypass this module
and parse JSONL files directly via cma_jsonl, but reads that have
side effects (notably `cma_surface`, which writes
surface_events.jsonl for `cma stats --leaks` validation) go through
here too.

Discipline (DECISIONS AD-003, AD-004):

- Every call uses subprocess.run with shell=False and an argv array.
  Operator input never gets concatenated into a shell-interpreted
  string, so argument injection is structurally impossible.
- Every call carries a 5-second timeout. A hung cma process must not
  hang the MCP server.
- Errors from cma (non-zero exit, timeout, missing binary) become
  CmaError exceptions carrying the partial command and stderr.
  Callers translate them into MCP isError responses.

The wrapper intentionally does not parse cma's stdout. Stdout shape
varies between cma verbs (`cma miss` returns a confirmation;
`cma stats --leaks` returns a table). The dispatch in mcp_server.py
includes the raw stdout in the response payload's `analysis` block
so callers can read what cma reported. For structured reads, the
caller follows up with a JSONL fetch via cma_jsonl.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass


# Per DECISIONS AD-003: every cma call carries this timeout.
DEFAULT_TIMEOUT_SECONDS = 5

# The bash cma binary is resolved from PATH by default. Operators
# can override with CMA_BIN to point at a specific cma checkout.
_CMA_BIN_OVERRIDE = os.environ.get("CMA_BIN")


class CmaError(Exception):
    """
    Raised when a cma subprocess invocation fails.

    Attributes
    ----------
    argv : list of str
        The full argv that was attempted. Always starts with the
        resolved cma binary path. Useful for debugging in operator
        logs.
    returncode : int or None
        The cma process exit status. None if the process did not
        return (timeout, missing binary, etc.).
    stdout : str
        Captured stdout up to the failure point. May be empty.
    stderr : str
        Captured stderr up to the failure point. cma writes
        operator-facing diagnostics here.
    reason : str
        One of: "missing_binary", "timeout", "non_zero_exit",
        "unexpected".
    """

    def __init__(
        self,
        argv: list[str],
        returncode: int | None,
        stdout: str,
        stderr: str,
        reason: str,
    ):
        self.argv = argv
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.reason = reason
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        cmd = " ".join(self.argv)
        return f"cma subprocess failed ({self.reason}): {cmd}"


@dataclass
class CmaResult:
    """Successful cma invocation result."""

    argv: list[str]
    returncode: int
    stdout: str
    stderr: str


def resolve_cma_binary() -> str:
    """Resolve the bash cma binary path. Raises CmaError if missing."""
    if _CMA_BIN_OVERRIDE:
        if not os.path.isfile(_CMA_BIN_OVERRIDE):
            raise CmaError(
                argv=[_CMA_BIN_OVERRIDE],
                returncode=None,
                stdout="",
                stderr=f"CMA_BIN override points to a path that is not a file: {_CMA_BIN_OVERRIDE}",
                reason="missing_binary",
            )
        return _CMA_BIN_OVERRIDE

    found = shutil.which("cma")
    if not found:
        raise CmaError(
            argv=["cma"],
            returncode=None,
            stdout="",
            stderr="cma binary not found on PATH; install from https://github.com/Clarethium/cma",
            reason="missing_binary",
        )
    return found


def run_cma(args: list[str], timeout: int | None = None) -> CmaResult:
    """
    Invoke `cma <args...>` as a subprocess.

    Parameters
    ----------
    args : list of str
        Arguments passed to cma. Do not include the binary itself;
        this function resolves it.
    timeout : int, optional
        Override the default 5-second timeout. None uses
        DEFAULT_TIMEOUT_SECONDS.

    Returns
    -------
    CmaResult
        On success (returncode == 0).

    Raises
    ------
    CmaError
        On any failure (missing binary, timeout, non-zero exit).
    """
    binary = resolve_cma_binary()
    argv = [binary] + list(args)
    t = timeout if timeout is not None else DEFAULT_TIMEOUT_SECONDS

    try:
        proc = subprocess.run(
            argv,
            shell=False,
            capture_output=True,
            text=True,
            timeout=t,
        )
    except subprocess.TimeoutExpired as exc:
        raise CmaError(
            argv=argv,
            returncode=None,
            stdout=exc.stdout or "",
            stderr=exc.stderr or "",
            reason="timeout",
        ) from exc
    except OSError as exc:
        raise CmaError(
            argv=argv,
            returncode=None,
            stdout="",
            stderr=str(exc),
            reason="unexpected",
        ) from exc

    if proc.returncode != 0:
        raise CmaError(
            argv=argv,
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            reason="non_zero_exit",
        )

    return CmaResult(
        argv=argv,
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def cma_version() -> str | None:
    """
    Probe `cma --version` for the install fingerprint. Returns the
    raw stdout (single line) on success, None if cma is unavailable.

    Used by `cma-mcp --version` to show operators which cma binary
    their MCP server is wrapping.
    """
    try:
        result = run_cma(["--version"])
    except CmaError:
        return None
    return result.stdout.strip() or None
