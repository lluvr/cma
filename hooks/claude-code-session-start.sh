#!/usr/bin/env bash
# cma SessionStart hook for Claude Code.
#
# Surfaces priming context at the start of each Claude Code session: recent
# recurring failure patterns and active rejections, so the assistant has
# orientation before the first tool call. Per-action surfacing (the
# PreToolUse hook in claude-code-pre-tool-use.sh) handles relevance during
# work; this hook handles context at session boundary.
#
# Install: add to ~/.claude/settings.json:
#
#   "hooks": {
#     "SessionStart": [
#       {
#         "hooks": [
#           {
#             "type": "command",
#             "command": "bash /path/to/cma/hooks/claude-code-session-start.sh"
#           }
#         ]
#       }
#     ]
#   }
#
# Configuration: CMA_SESSION_START_SECTIONS (comma-separated, default
# "recurrence,rejections"). Available sections: recurrence, rejections,
# behavior. Set to "all" to include every available section.
#
# See docs/ARCHITECTURE.md Section 2.1 (Interception) for the design context.

set -uo pipefail

# Drain stdin (Claude Code may pass JSON; we do not need to parse it for
# this hook since the work is pulling priming context, not responding to
# tool input).
if [[ ! -t 0 ]]; then
    cat > /dev/null
fi

# Stage 3: query, failure-isolated. If cma missing, silent exit.
if ! command -v cma >/dev/null 2>&1; then
    exit 0
fi

sections="${CMA_SESSION_START_SECTIONS:-recurrence,rejections}"
if [[ "$sections" == "all" ]]; then
    sections="recurrence,rejections,behavior"
fi

# Run a command under a time limit. GNU `timeout` is missing on stock
# macOS, so fall back to Homebrew's `gtimeout`, then to python3 (already
# a hard dependency). Exit status 124 on expiry, matching `timeout`.
with_timeout() {
    local secs="$1"; shift
    if command -v timeout >/dev/null 2>&1; then
        timeout "$secs" "$@"
    elif command -v gtimeout >/dev/null 2>&1; then
        gtimeout "$secs" "$@"
    else
        # Like GNU timeout, signal the whole process group on expiry so a
        # grandchild holding the output pipe cannot outlive the limit.
        python3 -c '
import os, signal, subprocess, sys
try:
    p = subprocess.Popen(sys.argv[2:], start_new_session=True)
except OSError:
    sys.exit(127)
try:
    sys.exit(p.wait(timeout=float(sys.argv[1])))
except subprocess.TimeoutExpired:
    os.killpg(p.pid, signal.SIGKILL)
    p.wait()
    sys.exit(124)
' "$secs" "$@"
    fi
}

# Collect outputs from selected sections.
# Each subsection's full output is preserved (header + data + footer)
# because the framing text helps the assistant interpret the data.
get_section() {
    local name="$1"
    local out=""
    case "$name" in
        recurrence)
            out=$(with_timeout 5 cma stats --recurrence 2>/dev/null || true)
            # Suppress empty/no-data outputs: only return content if we
            # actually have recurring patterns.
            if [[ "$out" == *"no patterns are recurring"* ]] || [[ "$out" == *"No misses recorded"* ]] || [[ -z "$out" ]]; then
                out=""
            fi
            ;;
        rejections)
            out=$(with_timeout 5 cma stats --rejections 2>/dev/null || true)
            # Suppress when there are no active rejections
            if [[ "$out" == *"No captures match"* ]] || [[ -z "$out" ]]; then
                out=""
            fi
            ;;
        behavior)
            out=$(with_timeout 5 cma stats --behavior 2>/dev/null || true)
            if [[ "$out" == *"No misses recorded"* ]] || [[ "$out" == *"none have intended/corrected"* ]] || [[ -z "$out" ]]; then
                out=""
            fi
            ;;
    esac
    echo "$out"
}

# Stage 4: injection. Assemble output, write to stdout for Claude Code
# to inject as session context. Silent when nothing to show.

declare -a parts=()
IFS=',' read -ra requested <<< "$sections"
for s in "${requested[@]}"; do
    s=$(echo "$s" | tr -d '[:space:]')
    [[ -z "$s" ]] && continue
    content=$(get_section "$s")
    if [[ -n "$content" ]]; then
        parts+=( "## $s" "$content" "" )
    fi
done

if [[ ${#parts[@]} -eq 0 ]]; then
    exit 0
fi

echo "# cma session-start context"
echo ""
for p in "${parts[@]}"; do
    echo "$p"
done

# Stage 5: logging, handled by cma stats invocations themselves where
# applicable (stats commands are aggregate views that do not log surface
# events; this is intentional, since session-start priming is broad rather
# than action-specific).
