#!/usr/bin/env bash
# bench.sh - Performance benchmarks for cma's action-time injection layer.
#
# ARCHITECTURE.md Section 6 specifies <50ms typical end-to-end overhead for
# integration calls. This script measures `cma-pre --check` (the hook path)
# and `cma surface` (the underlying query) so the claim is verifiable rather
# than aspirational.
#
# Usage:
#   ./bench.sh           Run and print a human-readable table.
#   ./bench.sh --json    Emit machine-readable JSON to stdout (one object).
#
# Methodology: each operation is timed N=100 times after 3 warmup iterations.
# Reports min, median (p50), p95, p99. Numbers vary across machines, kernels,
# and runs; do not pin to a single sample. Re-run on the target host before
# citing.

set -uo pipefail

CMA="$(cd "$(dirname "$0")" && pwd)/cma"
PRE="$(cd "$(dirname "$0")" && pwd)/hooks/cma-pre"

N=${BENCH_N:-100}
EMIT_JSON=false
[[ "${1:-}" == "--json" ]] && EMIT_JSON=true

# Set up a clean data directory and populate it with realistic data
CMA_DIR=$(mktemp -d)
export CMA_DIR

# Make cma command findable by cma-pre (which calls it via PATH)
PATH_BIN=$(mktemp -d)
ln -sf "$CMA" "$PATH_BIN/cma"
export PATH="$PATH_BIN:$PATH"
trap 'rm -rf "$CMA_DIR" "$PATH_BIN"' EXIT

# Populate with 100 realistic captures across multiple surfaces
$EMIT_JSON || echo "Populating $CMA_DIR with 100 captures..."
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

# Run a benchmark with warmup, then N timed iterations. Emits a results line
# to RESULTS_TMP for later aggregation.
bench() {
    local name="$1"
    shift
    for i in 1 2 3; do
        time_ms "$@" >/dev/null
    done
    local samples=()
    for i in $(seq 1 "$N"); do
        samples+=( "$(time_ms "$@")" )
    done
    local sorted=()
    mapfile -t sorted < <(printf '%s\n' "${samples[@]}" | sort -n)
    local min="${sorted[0]}"
    local p50="${sorted[$((N / 2))]}"
    local p95_idx=$(( (N * 95) / 100 ))
    [[ "$p95_idx" -ge "$N" ]] && p95_idx=$((N - 1))
    local p95="${sorted[$p95_idx]}"
    local p99_idx=$(( (N * 99) / 100 ))
    [[ "$p99_idx" -ge "$N" ]] && p99_idx=$((N - 1))
    local p99="${sorted[$p99_idx]}"
    printf '%s\t%s\t%s\t%s\t%s\n' "$name" "$min" "$p50" "$p95" "$p99" >> "$RESULTS_TMP"
}

RESULTS_TMP=$(mktemp)
trap 'rm -rf "$CMA_DIR" "$PATH_BIN" "$RESULTS_TMP"' EXIT

bench "cma surface --surface auth"        "$CMA" surface --surface auth
bench "cma surface --type miss"           "$CMA" surface --type miss --limit 5
bench "cma stats (default summary)"       "$CMA" stats
bench "cma stats --recurrence"            "$CMA" stats --recurrence
bench "cma stats --evidence"              "$CMA" stats --evidence
bench "cma-pre --check (matched surface)" bash "$PRE" --check "git commit -m fix-auth"
bench "cma-pre --check (no match)"        bash "$PRE" --check "ls /tmp"
bench "cma-pre --check (non-trigger)"     bash "$PRE" --check "echo hello"

# Host fingerprint so adopters can compare results across machines.
HOST_KERNEL=$(uname -srm 2>/dev/null || echo unknown)
HOST_CPU=$(python3 -c 'import platform; print(platform.processor() or platform.machine())' 2>/dev/null || echo unknown)
HOST_FS=$(df -T "$CMA_DIR" 2>/dev/null | awk 'NR==2 {print $2}' || df "$CMA_DIR" 2>/dev/null | awk 'NR==2 {print $1}' || echo unknown)

if $EMIT_JSON; then
    python3 - "$RESULTS_TMP" "$N" "$HOST_KERNEL" "$HOST_CPU" "$HOST_FS" <<'PYEOF'
import json, sys
from datetime import datetime, timezone

results_path, n, kernel, cpu, fs = sys.argv[1:]
ops = []
with open(results_path) as f:
    for line in f:
        line = line.rstrip("\n")
        if not line:
            continue
        name, mn, p50, p95, p99 = line.split("\t")
        ops.append({
            "name": name,
            "min_ms": int(mn),
            "p50_ms": int(p50),
            "p95_ms": int(p95),
            "p99_ms": int(p99),
        })

print(json.dumps({
    "schema_version": "1.0",
    "n_per_op": int(n),
    "warmup_iterations": 3,
    "host": {
        "kernel": kernel,
        "cpu": cpu,
        "filesystem": fs,
    },
    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "target_p95_ms": 50,
    "operations": ops,
}, indent=2))
PYEOF
else
    echo ""
    echo "Latency benchmarks (N=$N per operation; ARCHITECTURE.md target: <50ms typical)"
    echo "Host: $HOST_KERNEL ($HOST_CPU, fs=$HOST_FS)"
    echo ""
    while IFS=$'\t' read -r name mn p50 p95 p99; do
        printf "  %-42s  min=%4sms  p50=%4sms  p95=%4sms  p99=%4sms\n" "$name" "$mn" "$p50" "$p95" "$p99"
    done < "$RESULTS_TMP"
    echo ""
    echo "Captures: 100 misses across 7 surfaces, 5 failure shapes."
    echo "Methodology: $N timed iterations after 3 warmup runs per op."
    echo "Re-run on the target host before citing numbers; sub-50ms work is noisy."
fi
