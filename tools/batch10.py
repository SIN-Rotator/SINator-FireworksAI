#!/usr/bin/env python3
"""Generate 10 fresh Fireworks API keys via sequential rotate.py calls.

Docs: tools/batch10.doc.md
"""
import asyncio
import json
import subprocess
import time
import sys
from pathlib import Path

LOG = Path(__file__).parent / "batch10.log"
ROTATE = Path(__file__).parent / "rotate.py"


def log(msg):
    """Timestamped log to stdout + LOG file. Defensive against BlockingIOError."""
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    # stdout may be non-blocking under nohup/redirect — guard against Errno 35
    try:
        print(line, flush=True)
    except BlockingIOError:
        pass
    try:
        with LOG.open("a") as f:
            f.write(line + "\n")
    except BlockingIOError:
        pass


async def get_pool_stats():
    """Read pool stats via curl. Returns (available, total) or (-1, -1) on error."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "curl", "-s", "http://127.0.0.1:8100/api/v1/pool/stats",
            stdout=asyncio.subprocess.PIPE
        )
        out, _ = await proc.communicate()
        data = json.loads(out)
        return data.get("available", 0), data.get("total", 0)
    except Exception:
        return -1, -1


async def rotate_one(idx):
    """Spawn rotate.py once, return success bool.

    Uses proc.communicate() instead of streaming `async for line in proc.stdout`
    to avoid BlockingIOError when the child writes more than the pipe buffer
    holds. Cost: no real-time output (acceptable for batch processing).
    """
    log(f"=== Rotation {idx}/10 START ===")
    t0 = time.time()
    proc = await asyncio.create_subprocess_exec(
        "python3", str(ROTATE),
        "--cdp-port", "9222",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=str(ROTATE.parent.parent)
    )
    # Drain all output in one shot — prevents pipe-buffer deadlock on long runs
    stdout_bytes, _ = await proc.communicate()
    output = stdout_bytes.decode("utf-8", errors="replace").splitlines() if stdout_bytes else []

    # Surface only the relevant lines (ROTATION marker, API key, errors)
    for line in output:
        if "ROTATION COMPLETE" in line or "API Key:" in line or "DELETION" in line or "Error" in line:
            log(f"  {line}")

    dt = time.time() - t0
    success = proc.returncode == 0 and any("ROTATION COMPLETE" in l for l in output)
    log(f"=== Rotation {idx}/10 {'SUCCESS' if success else 'FAILED'} ({dt:.0f}s) ===")
    return success

async def main():
    LOG.write_text("")
    log("BATCH START: 10 rotations target")
    avail_start, total_start = await get_pool_stats()
    log(f"Start: {avail_start} available / {total_start} total")

    successes = 0
    failures = 0
    t0 = time.time()
    for i in range(1, 11):
        try:
            ok = await rotate_one(i)
            if ok:
                successes += 1
                failures = 0
            else:
                failures += 1
                if failures >= 3:
                    log("3 consecutive failures — STOPPING")
                    break
                log("Waiting 15s before retry...")
                await asyncio.sleep(15)
        except Exception as e:
            log(f"Exception: {e}")
            failures += 1
            if failures >= 3:
                break
            await asyncio.sleep(15)

    avail_end, total_end = await get_pool_stats()
    dt = time.time() - t0
    log(f"\n{'='*50}")
    log(f"DONE: {successes}/10 in {dt/60:.1f}min ({dt/max(1,successes):.0f}s avg)")
    log(f"Pool: {avail_start} → {avail_end} available, {total_start} → {total_end} total")
    log(f"Net: +{total_end - total_start} keys")

asyncio.run(main())
