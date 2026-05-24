#!/usr/bin/env python3
"""Batch rotation — generates N API keys sequentially."""
import sys, os, asyncio, time, logging, re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "agent_toolbox" / "core"))
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger("batch")

TARGET = int(sys.argv[1]) if len(sys.argv) > 1 else 50
FAIL_LIMIT = 5

async def run_one(i):
    proc = await asyncio.create_subprocess_exec(
        "python3", str(Path(__file__).parent / "rotate.py"),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=str(Path(__file__).parent.parent),
    )
    output = []
    async for line_bytes in proc.stdout:
        line = line_bytes.decode("utf-8", errors="replace").rstrip()
        output.append(line)
        if any(k in line for k in ['✅', '❌', '⚠️', 'ROTATION COMPLETE', 'API Key creation failed']):
            logger.info(f"[{i}/{TARGET}] {line}")
    await proc.wait()
    success = any("ROTATION COMPLETE" in l for l in output)
    key = None
    for l in output:
        m = re.search(r'fw_[a-zA-Z0-9]{20,}', l)
        if m:
            key = m.group(0)
            break
    return success, key, output[-5:] if not success else []

async def main():
    from pool_manager import PoolManager
    pool = PoolManager()
    start_total = pool.get_stats()['total']
    logger.info(f"Starting batch: {TARGET} keys, pool has {start_total}")

    ok = 0
    fail_streak = 0
    t0 = time.time()

    for i in range(1, TARGET + 1):
        logger.info(f"\n{'='*40} ROTATION {i}/{TARGET} {'='*40}")
        try:
            success, key, tail = await asyncio.wait_for(run_one(i), timeout=360)
        except asyncio.TimeoutError:
            logger.error(f"[{i}/{TARGET}] TIMEOUT (>6min)")
            fail_streak += 1
            if fail_streak >= FAIL_LIMIT:
                logger.error(f"{FAIL_LIMIT} consecutive failures — stopping")
                break
            continue
        except Exception as e:
            logger.error(f"[{i}/{TARGET}] ERROR: {e}")
            fail_streak += 1
            if fail_streak >= FAIL_LIMIT:
                logger.error(f"{FAIL_LIMIT} consecutive failures — stopping")
                break
            continue

        if success:
            ok += 1
            fail_streak = 0
            elapsed = time.time() - t0
            rate = ok / (elapsed / 60)
            remaining = (TARGET - ok) / rate if rate > 0 else 0
            logger.info(f"[{i}/{TARGET}] ✅ #{ok} key={key} | {rate:.1f}/min | ETA {remaining:.0f}min")
        else:
            fail_streak += 1
            logger.error(f"[{i}/{TARGET}] ❌ FAIL (streak={fail_streak})")
            for l in tail:
                logger.error(f"  {l}")
            if fail_streak >= FAIL_LIMIT:
                logger.error(f"{FAIL_LIMIT} consecutive failures — stopping")
                break
            await asyncio.sleep(10)

    elapsed = time.time() - t0
    pool.reload()
    final = pool.get_stats()
    logger.info(f"\n{'='*50}")
    logger.info(f"BATCH DONE: {ok}/{TARGET} keys in {elapsed/60:.1f}min")
    logger.info(f"Pool: {final['total']} total, {final['available']} available, {final['used']} used")
    logger.info(f"Added: {final['total'] - start_total} new keys")

if __name__ == "__main__":
    asyncio.run(main())
