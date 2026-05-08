"""Build-time hook: bake the repo git SHA into _build_info.py.

The pyproject.toml file is the authoritative metadata source — this
shim runs only during sdist/wheel builds (and editable installs) so
the resulting artifact carries the git SHA it was built from. After
`pip install` from a wheel there is no `.git` directory next to the
installed module, so the runtime probe in `mcp_server._git_sha()`
returns None; the baked SHA fills that gap and preserves the
forensic-traceability claim of the install fingerprint.

Resolution order (first non-empty wins):

1. CMA_MCP_BUILD_SHA environment variable. CI sets this to
   $GITHUB_SHA before `python -m build` so PyPA's PEP 517 build
   isolation (which copies sources into a temp dir without `.git`)
   does not lose the SHA.
2. `git rev-parse HEAD` against this file's directory and its
   parent. Catches the editable-install path (`pip install -e .`)
   where setup.py runs in the live source tree and `git` walks up
   to the worktree root.
3. Empty string. The runtime probe will return `git_sha: null`
   and the install fingerprint reports the missing trace honestly.

The generated file is regenerated on every build and `.gitignore`d
so local development never commits a stale value.
"""

import os
import subprocess
from pathlib import Path

from setuptools import setup


def _probe_git_sha(cwd: Path) -> str:
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).decode("utf-8").strip()
    except Exception:
        return ""
    if not sha:
        return ""
    try:
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=cwd,
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).decode("utf-8").strip()
        if dirty:
            sha = sha + "+dirty"
    except Exception:
        # `git status` failure (no git, timeout, lock contention) leaves SHA un-suffixed; build proceeds.
        pass
    return sha


def _resolve_git_sha() -> str:
    env_sha = os.environ.get("CMA_MCP_BUILD_SHA", "").strip()
    if env_sha:
        return env_sha
    here = Path(__file__).parent.resolve()
    for candidate in (here, here.parent):
        sha = _probe_git_sha(candidate)
        if sha:
            return sha
    return ""


def _write_build_info() -> None:
    sha = _resolve_git_sha()
    target = Path(__file__).parent / "_build_info.py"
    target.write_text(
        '"""Auto-generated at build time. Do not edit. Do not commit."""\n'
        f'BUILD_GIT_SHA = "{sha}"\n',
        encoding="utf-8",
    )


_write_build_info()
setup()
