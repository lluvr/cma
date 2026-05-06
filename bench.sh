#!/usr/bin/env bash
# bench.sh - Performance benchmarks for cma's action-time injection layer.
#
# ARCHITECTURE.md Section 6 specifies <50ms typical end-to-end overhead for
# integration calls. This script measures `cma-pre --check` (the hook path)
# and `cma surface` (the underlying query) so the claim is verifiable rather
# than aspirational.
#
# Run from repository root: ./bench.sh

set -uo pipefail

CMA="$(cd "$(dirname "$0")" && pwd)/cma"
PRE="$(cd "$(dirname "$0")" && pwd)/hooks/cma-pre"

# Set up a clean data directory and populate it with realistic data
CMA_DIR=$(mktemp -d)
export CMA_DIR
trap 'rm -rf "$CMA_DIR"' EXIT

# Make cma command findable by cma-pre (which calls it via PATH)
PATH_BIN=$(mktemp -d)
ln -sf "$CMA" "$PATH_BIN/cma"
export PATH="$PATH_BIN:$PATH"
trap 'rm -rf "$CMA_DIR" "$PATH_BIN"' EXIT

# Populate with 100 realistic captures across multiple surfaces
echo "Populating $CMA_DIR with 100 captures..."
surfaces=(auth payments db api ui docs test)
fms=(fm-1 fm-2 fm-3 fm-4 fm-5)
for i in $(seq 1 100); do
    surface=${surfaces[$((RANDOM % ${#surfaces[@]}))]}
    fm=${fms[$((RANDOM % ${#fms[@]}))]}
    cma miss "synthetic miss $i for benchmark" --surface "$surface" --fm "$fm" >/dev/null
done

# Time a single invocation in milliseconds. Uses python3's perf_counter for
# portability (Linux %N differs from macOS BSD date, NTP corrections can
# cause negative deltas with naive arithmetic).
time_ms() {
    python3 -c '
import subprocess, sys, time
cmd = sys.argv[1:]
t0 = time.perf_counter()
subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print(int((time.perf_counter() - t0) * 1000))
' "$@"
}

# Run a benchmark with warmup, then N timed iterations. Report min/median/p95.
bench() {
    local name="$1"
    local n="$2"
    shift 2
    # Warmup: 3 throwaway iterations so cold-start does not skew first sample
    for i in 1 2 3; do
        time_ms "$@" >/dev/null
    done
    local samples=()
    for i in $(seq 1 "$n"); do
        samples+=( "$(time_ms "$@")" )
    done
    local sorted=()
    mapfile -t sorted < <(printf '%s\n' "${samples[@]}" | sort -n)
    local min="${sorted[0]}"
    local median="${sorted[$((n / 2))]}"
    local p95_idx=$(( (n * 95) / 100 ))
    [[ "$p95_idx" -ge "$n" ]] && p95_idx=$((n - 1))
    local p95="${sorted[$p95_idx]}"
    printf "  %-40s  min=%4sms  median=%4sms  p95=%4sms\n" "$name" "$min" "$median" "$p95"
}

echo ""
echo "Latency benchmarks (lower is better; ARCHITECTURE.md target: <50ms typical)"
echo ""

bench "cma surface --surface auth"        20 "$CMA" surface --surface auth
bench "cma surface --type miss"           20 "$CMA" surface --type miss --limit 5
bench "cma stats (default summary)"       20 "$CMA" stats
bench "cma stats --recurrence"            20 "$CMA" stats --recurrence
bench "cma-pre --check (matched surface)" 20 bash "$PRE" --check "git commit -m fix-auth"
bench "cma-pre --check (no match)"        20 bash "$PRE" --check "ls /tmp"
bench "cma-pre --check (non-trigger)"     20 bash "$PRE" --check "echo hello"

echo ""
echo "Captures: 100 misses across 7 surfaces, 5 failure shapes."
echo "Data directory: $CMA_DIR"
