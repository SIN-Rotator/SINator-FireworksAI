"""Verify Fireworks API keys with minimal token consumption.

Docs: test_keys.doc.md

Iterates all (or filtered) keys in the pool, sends a 1-token request to
Fireworks, and updates each key's `suspended` status based on the response.
Use this to find false-positive suspensions and pre-emptively detect
exhausted credits.

Cost: ~3 tokens per key at deepseek-v4-flash rates. A full 256-key scan
costs less than $0.001.
"""
import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional, Dict, List, Any

import aiohttp

# Repo root for pool_manager import
TOOLS_DIR = Path(__file__).parent
REPO_ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(REPO_ROOT))

from agent_toolbox.core.pool_manager import PoolManager  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("test_keys")

# Cheap model — minimize cost per probe. Override with --model if needed.
DEFAULT_MODEL = "accounts/fireworks/models/deepseek-v4-flash"
FIREWORKS_API_BASE = "https://api.fireworks.ai/inference/v1"

# HTTP status → outcome
ALIVE_CODES = {200, 204}
# 401/403: invalid/revoked, 402: payment required, 412: pre-condition failed (suspended)
DEAD_CODES = {401, 402, 403, 412}
# 429: rate limited — don't mark suspended, just leave alone
# 5xx: transient — leave alone, retry next scan


async def test_single_key(
    session: aiohttp.ClientSession,
    api_key: str,
    model: str,
    timeout: int,
) -> int:
    """Send a minimal probe to Fireworks. Returns HTTP status code."""
    url = f"{FIREWORKS_API_BASE}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "."}],
        "max_tokens": 1,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            # Drain the response body so the connection is released
            await resp.read()
            return resp.status
    except asyncio.TimeoutError:
        return 0  # special: timeout
    except aiohttp.ClientError:
        return -1  # special: client error


def classify(status: int) -> str:
    if status in ALIVE_CODES:
        return "alive"
    if status in DEAD_CODES:
        return "dead"
    if status == 429:
        return "rate_limited"
    if status == 0:
        return "timeout"
    if status == -2:
        return "no_api_key"
    if status < 0:
        return "client_error"
    return "transient"  # 5xx, etc.


async def test_key(
    key_record: Dict[str, Any],
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    model: str,
    timeout: int,
) -> Dict[str, Any]:
    api_key = key_record.get("api_key")
    if not api_key or api_key == "STORED_IN_KEYCHAIN":
        # Need to hydrate from keychain
        from agent_toolbox.core.keychain_store import retrieve_key
        api_key = retrieve_key(key_record["id"])
    if not api_key:
        return {**key_record, "_test_status": -2, "_tested": True}

    async with semaphore:
        status = await test_single_key(session, api_key, model, timeout)
    return {**key_record, "_test_status": status, "_tested": True}


async def run(args) -> int:
    pm = PoolManager()
    keys = pm.keys
    if not keys:
        logger.error("Pool is empty. Nothing to test.")
        return 1

    # Filter
    if args.only_suspended:
        targets = [k for k in keys if k.get("suspended")]
        logger.info(f"Testing {len(targets)} suspended keys (looking for false positives)")
    elif args.only_available:
        targets = [k for k in keys if not k.get("suspended") and not k.get("used")]
        logger.info(f"Testing {len(targets)} available keys (looking for true positives)")
    elif args.key:
        targets = [k for k in keys if k["id"] == args.key]
        if not targets:
            logger.error(f"Key {args.key} not found in pool")
            return 1
        logger.info(f"Testing 1 specific key: {args.key[:8]}...")
    else:
        targets = list(keys)
        logger.info(f"Testing all {len(targets)} keys")

    if not targets:
        logger.info("Nothing to test.")
        return 0

    connector = aiohttp.TCPConnector(limit=args.concurrency, force_close=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        semaphore = asyncio.Semaphore(args.concurrency)
        tasks = [test_key(k, session, semaphore, args.model, args.timeout) for k in targets]
        t0 = time.time()
        results = await asyncio.gather(*tasks)
        elapsed = time.time() - t0

    # Tally + collect changes
    counts: Dict[str, int] = {}
    changes: List[Dict[str, Any]] = []
    reactivated = 0
    newly_suspended = 0

    for orig, tested in zip(targets, results):
        outcome = classify(tested["_test_status"])
        counts[outcome] = counts.get(outcome, 0) + 1

        was_suspended = bool(orig.get("suspended"))
        is_dead = outcome == "dead"
        is_alive = outcome == "alive"

        if is_dead and not was_suspended:
            # Should be suspended
            changes.append({
                "id": orig["id"],
                "alias": orig.get("alias_email", ""),
                "action": "mark_suspended",
                "reason": f"test_failed_{tested['_test_status']}",
            })
            if not args.dry_run:
                pm.mark_suspended(orig["id"], reason=f"test_failed_{tested['_test_status']}")
            newly_suspended += 1
        elif is_alive and was_suspended:
            # False positive — re-activate
            changes.append({
                "id": orig["id"],
                "alias": orig.get("alias_email", ""),
                "action": "reactivate",
            })
            if not args.dry_run:
                pm.unsuspend_key(orig["id"])
            reactivated += 1
        elif is_dead and was_suspended:
            # Confirmed suspended — refresh reason timestamp
            pass
        elif is_alive and not was_suspended:
            # Confirmed alive — no change
            pass

    # Summary
    logger.info("=" * 60)
    logger.info(f"Tested {len(results)} keys in {elapsed:.1f}s ({len(results)/elapsed:.1f}/s)")
    for outcome in ("alive", "dead", "rate_limited", "timeout", "client_error", "transient", "no_api_key"):
        c = counts.get(outcome, 0)
        if c:
            logger.info(f"  {outcome:14s}: {c}")
    logger.info("-" * 60)
    logger.info(f"Newly suspended: {newly_suspended}")
    logger.info(f"Reactivated (false positives): {reactivated}")
    if args.dry_run:
        logger.info("[DRY RUN — no changes saved]")
    if changes:
        logger.info("=" * 60)
        logger.info("Changes:")
        for ch in changes[:20]:
            logger.info(f"  {ch['action']:18s} {ch.get('reason', ''):30s} {ch['alias']:40s}")
        if len(changes) > 20:
            logger.info(f"  ... and {len(changes) - 20} more")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="Test Fireworks API keys with minimal token consumption",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  %(prog)s                       # test all 256 keys (~5s, $0.001 cost)
  %(prog)s --only-suspended      # re-verify currently suspended (find false positives)
  %(prog)s --only-available      # verify available keys aren't actually dead
  %(prog)s --key <id>            # test single key
  %(prog)s --concurrency 32      # faster scan
  %(prog)s --dry-run             # report changes without saving
""",
    )
    ap.add_argument("--model", default=DEFAULT_MODEL, help=f"Fireworks model to probe (default: {DEFAULT_MODEL})")
    ap.add_argument("--timeout", type=int, default=15, help="Per-request timeout in seconds (default: 15)")
    ap.add_argument("--concurrency", type=int, default=8, help="Concurrent test requests (default: 8)")
    ap.add_argument("--only-suspended", action="store_true", help="Only test currently-suspended keys")
    ap.add_argument("--only-available", action="store_true", help="Only test available keys")
    ap.add_argument("--key", help="Test single key by ID")
    ap.add_argument("--dry-run", action="store_true", help="Report changes without saving")
    args = ap.parse_args()
    if args.only_suspended and args.only_available:
        ap.error("Cannot use --only-suspended and --only-available together")
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
