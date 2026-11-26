#!/usr/bin/env bash
# cma PreToolUse hook for Claude Code.
#
# Surfaces relevant prior captures (misses, decisions, rejections, preventions)
# at the moment Claude is about to use a tool that touches a file or runs a
# command. Output goes to stdout as a JSON object carrying
# hookSpecificOutput.additionalContext, which is the form Claude Code adds to
# the assistant's context for PreToolUse hooks (plain stdout from a PreToolUse
# hook only reaches the debug log).
#
# Install: copy or symlink to a location, then add to ~/.claude/settings.json:
#
#   "hooks": {
#     "PreToolUse": [
#       {
#         "hooks": [
#           {
#             "type": "command",
#             "command": "bash /path/to/cma/hooks/claude-code-pre-tool-use.sh"
#           }
#         ]
#       }
#     ]
#   }
#
# Requires `cma` on PATH (see cma's quick-start).

set -uo pipefail

# Read hook payload: prefer stdin JSON (current Claude Code format),
# fall back to env vars (older convention used by some hooks).
#
# The payload stays on stdin. A Write carries the whole file body, and
# passing that as an argument fails past the kernel's 128 KiB limit per
# argument, so the script goes in -c and Python reads stdin itself.
read -r -d '' HOOK_PY <<'PYEOF'
import json, os, re, sys, subprocess

stdin_json = "" if sys.stdin.isatty() else sys.stdin.read()
env_tool_name = os.environ.get("CLAUDE_TOOL_NAME", "")
env_tool_input = os.environ.get("CLAUDE_TOOL_INPUT", "")

tool_name = ""
tool_input = {}
session_id = ""

# Parse stdin JSON (Claude Code's current hook format)
if stdin_json:
    try:
        data = json.loads(stdin_json)
        tool_name = data.get("tool_name", "") or tool_name
        session_id = data.get("session_id") or ""
        ti = data.get("tool_input", {})
        if isinstance(ti, dict):
            tool_input = ti
        elif isinstance(ti, str):
            try:
                tool_input = json.loads(ti)
            except json.JSONDecodeError:
                pass
    except json.JSONDecodeError:
        pass

# Fall back to env vars
if not tool_name:
    tool_name = env_tool_name
if not tool_input and env_tool_input:
    try:
        tool_input = json.loads(env_tool_input)
    except json.JSONDecodeError:
        pass

# CMA_EVAL=1 records an arm for this session before any surfacing.
# The off arm still computes the match, writes a shadow, and shows nothing.
# Missing session id keeps today's behavior: show the warning.
arm = ""
if os.environ.get("CMA_EVAL") == "1" and session_id:
    def _cma_line(argv):
        try:
            result = subprocess.run(argv, capture_output=True, text=True, timeout=5)
        except Exception:
            return ""
        if result.returncode != 0:
            return ""
        return result.stdout.strip()
    arm = _cma_line(["cma", "eval", "arm", "--session", session_id])
    _cma_line(["cma", "eval", "touch", "--session", session_id])

# Only surface for tools that touch files or run commands
relevant_tools = {"Edit", "Write", "MultiEdit", "NotebookEdit", "Bash"}
if tool_name not in relevant_tools:
    sys.exit(0)

# Extract a file path or command for context
file_path = ""
command = ""
if tool_name in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
elif tool_name == "Bash":
    command = tool_input.get("command", "")

# Whole tokens only. "auth" inside "author", and "session" inside a
# filename, are not auth. A short keyword as a substring labels the
# wrong file and then hides that file's own miss.
NARROW_TOKENS = {
    "auth": {
        "auth", "auths", "authentication", "authenticate", "authenticated",
        "authorization", "authorize", "authorized", "unauthorized",
        "login", "jwt", "oauth", "oauth2", "password", "passwords",
        "credential", "credentials",
    },
    "payments": {"payment", "payments", "stripe", "billing", "checkout"},
    "db": {
        "schema", "schemas", "migration", "migrations",
        "database", "databases",
    },
}

def detect_narrow(text):
    t = text.lower()
    tokens = set(re.findall(r"[a-z0-9]+", t))
    for surface in ("auth", "payments", "db"):
        if tokens & NARROW_TOKENS[surface]:
            return surface
    # "model" and "db" alone match too many paths. The slash is the signal.
    if "/model" in t or "/db/" in t:
        return "db"
    return ""

# The file's own captures come first. ui, docs, api, and test are not
# inferred from an extension or a path word: that shows one bucket's
# latest misses on unrelated files, and the assistant learns to skip
# the hook. Auth, payments, and db are the fallback, and only when
# this file has no capture. A bash command has no file, so it gets
# the narrow surface or nothing.
narrow = detect_narrow(file_path or command)
base_name = os.path.basename(file_path) if file_path else ""
base = ["cma", "surface", "--limit", "3"]
queries = []
if base_name:
    queries.append(base + ["--file", base_name])
if narrow:
    queries.append(base + ["--surface", narrow])
if not queries:
    sys.exit(0)

def run_surface(argv):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=5)
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    out = result.stdout.strip()
    if out == "No captures match.":
        return ""
    return out

def first_query():
    for query in queries:
        if run_surface(query + ["--no-log"]):
            return query
    return None

# Log only the query that actually matched, so a miss-free probe is not
# a warning. The off arm writes a shadow instead and prints nothing.
matched = first_query()
if matched is None:
    sys.exit(0)
if arm == "off":
    run_surface(matched + ["--shadow", "--session", session_id])
    sys.exit(0)
log_args = list(matched)
if arm == "on" and session_id:
    log_args.extend(["--session", session_id])
output = run_surface(log_args)
if not output:
    sys.exit(0)

# Captured text is untrusted: strip ANSI/OSC escapes and control characters
# (keeping newline and tab) before handing it to the assistant.
output = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|[\x00-\x08\x0b-\x1f\x7f-\x9f]", "", output)
context = (
    "Previous failures that matched this edit. "
    "When an Instead line is present, do that. "
    "The line above it is the failure it replaced.\n\n" + output
)
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": context,
    }
}))
PYEOF

python3 -c "$HOOK_PY"
