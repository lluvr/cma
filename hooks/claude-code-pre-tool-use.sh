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
stdin_payload=""
if [[ ! -t 0 ]]; then
    stdin_payload=$(cat)
fi

env_tool_name="${CLAUDE_TOOL_NAME:-}"
env_tool_input="${CLAUDE_TOOL_INPUT:-}"

python3 - "$stdin_payload" "$env_tool_name" "$env_tool_input" <<'PYEOF'
import json, os, sys, subprocess

stdin_json, env_tool_name, env_tool_input = sys.argv[1:]

tool_name = ""
tool_input = {}

# Parse stdin JSON (Claude Code's current hook format)
if stdin_json:
    try:
        data = json.loads(stdin_json)
        tool_name = data.get("tool_name", "") or tool_name
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

# Heuristic surface detection from file path or command
def detect_surface(text):
    t = text.lower()
    if any(k in t for k in ("auth", "login", "session", "jwt", "oauth", "password", "credential")):
        return "auth"
    if any(k in t for k in ("payment", "stripe", "billing", "checkout")):
        return "payments"
    if any(k in t for k in ("schema", "migration", "/model", "database", "db/")):
        return "db"
    if any(k in t for k in ("/test", ".test.", ".spec.", "/__tests__/")):
        return "test"
    if any(k in t for k in ("/api", "route", "endpoint", "controller", "handler")):
        return "api"
    if any(k in t for k in ("/ui", "/component", ".tsx", ".jsx", ".vue")):
        return "ui"
    if any(k in t for k in ("readme", "/docs/", ".md")):
        return "docs"
    return ""

surface = detect_surface(file_path or command)

# Build cma surface query.
# Prefer surface filter when detected (broader: catches captures from any file
# in the same surface). Fall back to file filter when no surface heuristic
# matches. Combining both with AND is too strict in practice.
args = ["cma", "surface", "--limit", "3"]
if surface:
    args.extend(["--surface", surface])
elif file_path:
    args.extend(["--file", os.path.basename(file_path)])
else:
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

# Query without logging first, so a surface event is only recorded when
# this hook actually hands captures to the assistant. A miss-free query
# is not a warning and should not count as one in leak detection.
if not run_surface(args + ["--no-log"]):
    sys.exit(0)
output = run_surface(args)
if not output:
    sys.exit(0)

# Captured text is untrusted: strip ANSI/OSC escapes and control characters
# (keeping newline and tab) before handing it to the assistant.
import re
output = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|[\x00-\x08\x0b-\x1f\x7f-\x9f]", "", output)
context = "Relevant prior captures from cma (action-time injection):\n\n" + output
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": context,
    }
}))
PYEOF
