#!/usr/bin/env python3
"""bench.py - Latency benchmarks for cma-mcp's MCP wrapper layer.

bash cma's `bench.sh` measures the cma binary's own latency
(`cma surface`, `cma stats`, `cma-pre --check`) against a synthetic
100-capture data set. cma-mcp adds two layers of overhead on top of
that: `subprocess.run` to spawn the cma binary per call, and
JSON-RPC framing over stdio between the MCP client and cma-mcp.

This benchmark measures cma-mcp's actual wire-level round-trip
latency: the MCP client writes one JSON-RPC line on cma-mcp's stdin
and reads one JSON-RPC line back from cma-mcp's stdout. The result
is the operator's actual cost: "how much does an MCP call cost
compared to running cma directly".

Run from cma-mcp/:
    python3 bench.py

Requires the cma binary on PATH (the wrapper spawns it). Uses a
disposable CMA_DIR populated with 100 synthetic captures so results
do not depend on the operator's corpus.

The benchmark spawns one cma-mcp subprocess for the whole run (the
expected MCP-client lifecycle) and reuses it across all measured
calls. Each tool call goes through:

    client → JSON-RPC over stdin → cma-mcp dispatch
        → subprocess.run([cma, *argv]) → cma binary I/O
        → three-section payload composition
        → JSON-RPC over stdout → client

so the reported latency captures the full operator-experienced cost.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from statistics import median


HERE = Path(__file__).parent.resolve()
WARMUP_ITERATIONS = 3
MEASURED_ITERATIONS = 20
P95_INDEX = int(MEASURED_ITERATIONS * 0.95)
SURFACES = ("auth", "payments", "db", "api", "ui", "docs", "test", "general")
FMS = ("fm-1", "fm-2", "fm-3", "fm-4", "fm-5")


def populate_corpus(cma_binary: str, cma_dir: str, n: int = 100) -> None:
    """Populate a fresh CMA_DIR with synthetic captures."""
    env = os.environ.copy()
    env["CMA_DIR"] = cma_dir
    for i in range(n):
        surface = SURFACES[i % len(SURFACES)]
        fm = FMS[i % len(FMS)]
        subprocess.run(
            [cma_binary, "miss",
             f"synthetic bench miss {i} for cma-mcp wire-latency probe",
             "--surface", surface, "--fm", fm],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=5,
        )


class WireClient:
    """Drive cma-mcp over real stdin/stdout pipes."""

    def __init__(self, cma_dir: str):
        env = os.environ.copy()
        env["CMA_DIR"] = cma_dir
        self.proc = subprocess.Popen(
            [sys.executable, str(HERE / "mcp_server.py")],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            bufsize=0,
        )
        self._next_id = 1
        self._initialize()

    def _initialize(self) -> None:
        self.call("initialize", {"protocolVersion": "2024-11-05",
                                 "capabilities": {},
                                 "clientInfo": {"name": "bench.py", "version": "0"}})
        self.notify("notifications/initialized", {})

    def call(self, method: str, params: dict | None = None) -> dict:
        req_id = self._next_id
        self._next_id += 1
        line = json.dumps({"jsonrpc": "2.0", "id": req_id, "method": method,
                           "params": params or {}})
        self.proc.stdin.write((line + "\n").encode())
        self.proc.stdin.flush()
        reply_line = self.proc.stdout.readline()
        if not reply_line:
            stderr = self.proc.stderr.read().decode(errors="replace")
            raise RuntimeError(f"cma-mcp closed pipe; stderr=\n{stderr}")
        reply = json.loads(reply_line)
        if reply.get("id") != req_id:
            raise RuntimeError(f"id mismatch: sent {req_id}, got {reply.get('id')}")
        if "error" in reply:
            raise RuntimeError(f"server error: {reply['error']}")
        return reply["result"]

    def notify(self, method: str, params: dict | None = None) -> None:
        line = json.dumps({"jsonrpc": "2.0", "method": method,
                           "params": params or {}})
        self.proc.stdin.write((line + "\n").encode())
        self.proc.stdin.flush()

    def close(self) -> None:
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def time_ms(fn) -> int:
    t0 = time.perf_counter()
    fn()
    return int((time.perf_counter() - t0) * 1000)


def bench(client: WireClient, label: str, fn) -> tuple[int, int, int]:
    for _ in range(WARMUP_ITERATIONS):
        fn(client)
    samples = sorted(time_ms(lambda: fn(client)) for _ in range(MEASURED_ITERATIONS))
    return samples[0], samples[len(samples) // 2], samples[min(P95_INDEX, MEASURED_ITERATIONS - 1)]


def report(label: str, mn: int, md: int, p95: int) -> None:
    print(f"  {label:<46}  min={mn:>4}ms  median={md:>4}ms  p95={p95:>4}ms")


def main() -> int:
    cma_binary = shutil.which("cma")
    if cma_binary is None:
        print("ERROR: cma binary not on PATH. Install bash cma first "
              "(see ../README.md).", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="cma-mcp-bench-") as cma_dir:
        print(f"Populating disposable CMA_DIR={cma_dir} with 100 captures...",
              flush=True)
        populate_corpus(cma_binary, cma_dir, n=100)
        print()
        print("MCP wire-latency benchmarks (lower is better)")
        print("Each call: stdin write → cma-mcp dispatch → cma binary spawn → "
              "stdout read")
        print()

        client = WireClient(cma_dir)
        try:
            cases: list[tuple[str, callable]] = [
                ("ping",
                 lambda c: c.call("ping")),
                ("tools/list",
                 lambda c: c.call("tools/list")),
                ("resources/list",
                 lambda c: c.call("resources/list")),
                ("tools/call cma_stats (default)",
                 lambda c: c.call("tools/call",
                                  {"name": "cma_stats",
                                   "arguments": {"view": "default"}})),
                ("tools/call cma_stats (recurrence)",
                 lambda c: c.call("tools/call",
                                  {"name": "cma_stats",
                                   "arguments": {"view": "recurrence"}})),
                ("tools/call cma_surface (surface=auth)",
                 lambda c: c.call("tools/call",
                                  {"name": "cma_surface",
                                   "arguments": {"surface": "auth", "limit": 5}})),
                ("tools/call cma_miss",
                 lambda c: c.call("tools/call",
                                  {"name": "cma_miss",
                                   "arguments": {
                                       "description": "bench probe",
                                       "surface": "general",
                                       "fm": "fm-1",
                                   }})),
                ("resources/read cma://decisions",
                 lambda c: c.call("resources/read",
                                  {"uri": "cma://decisions"})),
                ("resources/read cma://stats",
                 lambda c: c.call("resources/read",
                                  {"uri": "cma://stats"})),
            ]
            for label, fn in cases:
                mn, md, p95 = bench(client, label, fn)
                report(label, mn, md, p95)
        finally:
            client.close()

    print()
    print(f"Iterations per case: {MEASURED_ITERATIONS} measured "
          f"(after {WARMUP_ITERATIONS} warmup).")
    print("Reported latency is the full client-perceived round trip "
          "(stdin write → stdout read).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
