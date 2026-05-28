#!/usr/bin/env python3
"""Batch generate remaining keys via direct rotate.py calls."""
import asyncio, json, time, sys, subprocess
from pathlib import Path

TARGET = 69
LOG_FILE = Path(__file__).resolve().parent.parent / "data" / "batch-rotate.log"
ROTATE_SCRIPT = Path(__file__).resolve().parent / "rotate.py"

log_lines = []

def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    log_lines.append(line)
    print(line, flush=True)
    LOG_FILE.write_text("\n".join(log_lines))

async def count_available():
    import http.client
    conn = http.client.HTTPConnection("localhost", 8000, timeout=5)
    conn.request("GET", "/api/v1/pool/stats")
    resp = conn.getresponse()
    data = json.loads(resp.read())
    conn.close()
    return data.get("available", 0), data.get("total", 0)

async def rotate_one():
    proc = await asyncio.create_subprocess_exec(
        "python3", str(ROTATE_SCRIPT),
        "--gmx-email", "delqhi@gmx.de",
        "--gmx-password", "ZOE.jerry2024",
        "--password", "ZOE.jerry2024!",
        "--cdp-port", "9222",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=str(ROTATE_SCRIPT.parent.parent),
    )
    output = []
    gmx_alias = None
    api_key = None
    async for line_bytes in proc.stdout:
        line = line_bytes.decode("utf-8", errors="replace").rstrip()
        output.append(line)
        if "ROTATION COMPLETE" in line or "API Key:" in line or "Alias:" in line:
            log(line)
    await proc.wait()
    
    success = any("ROTATION COMPLETE" in l for l in output) and any("API Key:" in l for l in output)
    return {"status": "success" if success else "failed", "output": output}

async def main():
    avail, total_start = await count_available()
    log(f"Start: {avail} available / {total_start} total — Ziel: {TARGET} neue Keys")

    successes = 0
    failures = 0
    t0 = time.time()

    while successes < TARGET:
        log(f"\n--- Rotation #{successes + 1} ({failures} fails) ---")
        try:
            result = await rotate_one()
            if result["status"] == "success":
                successes += 1
                failures = 0
                log(f"✅ #{successes}/{TARGET} complete")
            else:
                failures += 1
                last_err = [l for l in result["output"] if "failed" in l.lower() or "error" in l.lower()]
                log(f"❌ #{successes + 1} FAILED: {last_err[-1] if last_err else 'unknown'}")
                if failures >= 3:
                    log("⚠️  3 consecutive failures — STOPPING. Check Chrome/GMX session.")
                    break
                log("🕐  waiting 30s before retry...")
                await asyncio.sleep(30)
        except Exception as e:
            failures += 1
            log(f"💥 Exception: {e}")
            if failures >= 3:
                log("⚠️  3 consecutive failures — STOPPING")
                break
            await asyncio.sleep(30)

        if successes % 5 == 0 and successes > 0:
            avail, total = await count_available()
            log(f"📊 Checkpoint: {avail} available / {total} total")

    avail, total_end = await count_available()
    t = time.time() - t0
    log(f"\n{'='*50}")
    log(f"FERTIG: {successes} keys in {t/60:.1f}min ({t/max(1,successes):.0f}s avg)")
    log(f"Pool: {avail} available / {total_end} total")

if __name__ == "__main__":
    asyncio.run(main())
