"""
macOS Keychain-backed secret store for API keys.

Strategy:
  - Pool JSON stores metadata ONLY (id, alias_email, status flags, etc.)
  - Actual api_key values live in macOS Keychain as generic passwords
  - Service name: "com.sinator.pool"
  - Account name: key_id (UUID)
  - On read: Keychain lookup replaces masked values with real ones
  - On write: api_key stored to Keychain, pool JSON gets "STORED_IN_KEYCHAIN" sentinel

Migration:
  - One-shot migration from plaintext JSON → Keychain
  - After migration, api_key field in JSON contains sentinel or is absent
"""
import json
import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

KEYCHAIN_SERVICE = "com.sinator.pool"
SENTINEL = "STORED_IN_KEYCHAIN"


def _run_security(args: list) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["security"] + args,
        capture_output=True, text=True, timeout=10,
    )


def store_key(key_id: str, api_key: str) -> bool:
    result = _run_security([
        "add-generic-password",
        "-s", KEYCHAIN_SERVICE,
        "-a", key_id,
        "-w", api_key,
        "-U",
    ])
    if result.returncode != 0:
        logger.error(f"Keychain store failed for {key_id[:8]}...: {result.stderr.strip()}")
        return False
    return True


def retrieve_key(key_id: str) -> Optional[str]:
    result = _run_security([
        "find-generic-password",
        "-s", KEYCHAIN_SERVICE,
        "-a", key_id,
        "-w",
    ])
    if result.returncode != 0:
        logger.warning(f"Keychain retrieve failed for {key_id[:8]}...: {result.stderr.strip()[:100]}")
        return None
    return result.stdout.strip()


def delete_key(key_id: str) -> bool:
    result = _run_security([
        "delete-generic-password",
        "-s", KEYCHAIN_SERVICE,
        "-a", key_id,
    ])
    if result.returncode != 0:
        logger.warning(f"Keychain delete failed for {key_id[:8]}...: {result.stderr.strip()[:100]}")
        return False
    return True


def migrate_pool(pool_path: Path, dry_run: bool = False) -> Dict[str, Any]:
    """
    Migrate all plaintext API keys from pool JSON into macOS Keychain.
    After migration, the api_key field in JSON is replaced with SENTINEL.
    
    Returns migration stats.
    """
    if not pool_path.exists():
        return {"status": "no_pool", "migrated": 0, "failed": 0}

    with open(pool_path, "r") as f:
        keys = json.load(f)

    if isinstance(keys, dict) and "accounts" in keys:
        keys = keys["accounts"]

    migrated = 0
    failed = 0
    already = 0

    for k in keys:
        api_key = k.get("api_key", "")
        key_id = k.get("id", "")
        if not api_key or not key_id:
            continue
        if api_key == SENTINEL:
            already += 1
            continue

        if dry_run:
            migrated += 1
            continue

        if store_key(key_id, api_key):
            k["api_key"] = SENTINEL
            migrated += 1
        else:
            failed += 1

    if not dry_run and migrated > 0:
        with open(pool_path, "w") as f:
            json.dump(keys, f, indent=2)
        logger.info(f"Migration complete: {migrated} keys → Keychain, {failed} failed, {already} already migrated")

    return {
        "status": "success" if failed == 0 else "partial",
        "migrated": migrated,
        "failed": failed,
        "already_migrated": already,
        "dry_run": dry_run,
    }


def hydrate_keys(keys: List[Dict[str, Any]], include_api_key: bool = True) -> List[Dict[str, Any]]:
    """
    Replace SENTINEL api_key values with real values from Keychain.
    If include_api_key is False, api_key is set to empty string (for stats/overview).
    """
    if not include_api_key:
        for k in keys:
            k["api_key"] = ""
        return keys

    for k in keys:
        api_key = k.get("api_key", "")
        if api_key == SENTINEL:
            key_id = k.get("id", "")
            real_key = retrieve_key(key_id)
            if real_key:
                k["api_key"] = real_key
            else:
                k["api_key"] = ""
                logger.warning(f"Could not hydrate key {key_id[:8]}... from Keychain")
    return keys


def hydrate_single(key: Dict[str, Any]) -> Dict[str, Any]:
    """Hydrate a single key dict."""
    return hydrate_keys([key])[0]
