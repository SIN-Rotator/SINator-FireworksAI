#!/usr/bin/env python3
"""Recover SINator-fireworksai pool metadata from macOS Keychain.

Docs: recover_pool.doc.md

When `data/fireworksai-pool.json` is missing but the keychain still has
the API keys, this script reconstructs the pool metadata so the backend
can come back online with the surviving 255+ keys.

The reconstruction cannot restore the original alias_email, credits_remaining,
or used/suspended status flags (those live only in the deleted JSON).
All recovered keys are marked as:
  - used: False
  - used_at: None
  - credits_initial: 6.0 (default for new Fireworks accounts)
  - alias_email: "recovered-<short_id>@unknown.local"
  - key_name: "recovered-from-keychain"
  - recovered: True  ← marker so we know this was reconstructed

Usage:
  python tools/recover_pool.py              # dry-run
  python tools/recover_pool.py --apply      # actually write pool.json
  python tools/recover_pool.py --verify     # just check keychain count
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any

UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)

KEYCHAIN_SERVICE = "com.sinator.pool"
SENTINEL = "STORED_IN_KEYCHAIN"

REPO_ROOT = Path(__file__).resolve().parent.parent
POOL_PATH = REPO_ROOT / "data" / "fireworksai-pool.json"


def _dump_keychain_accounts() -> List[str]:
    """Return all keychain account names (UUIDs) for KEYCHAIN_SERVICE."""
    result = subprocess.run(
        ["security", "dump-keychain"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"security dump-keychain failed: {result.stderr.strip()}")
    accounts: List[str] = []
    capture_next = False
    for line in result.stdout.splitlines():
        if f'"svce"<blob>="{KEYCHAIN_SERVICE}"' in line:
            capture_next = True
            continue
        if capture_next and '"acct"<blob>=' in line:
            start = line.index('"acct"<blob>="') + len('"acct"<blob>="')
            end = line.index('"', start)
            accounts.append(line[start:end])
            capture_next = False
    # V19.13: Reject non-UUID entries (ghost IDs from botched recovery)
    filtered = [aid for aid in accounts if UUID_RE.match(aid)]
    rejected = len(accounts) - len(filtered)
    if rejected > 0:
        print(f"WARNING: Rejected {rejected} non-UUID ghost IDs from keychain (V19.13 guard)")
        for aid in accounts:
            if not UUID_RE.match(aid):
                print(f"  -> rejected: {aid[:80]}")
    return filtered


def _verify_keychain_entry(account: str) -> bool:
    """Confirm the keychain entry is readable (prompts may appear)."""
    result = subprocess.run(
        [
            "security", "find-generic-password",
            "-s", KEYCHAIN_SERVICE,
            "-a", account,
            "-w",
        ],
        capture_output=True, text=True, timeout=10,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def build_pool_entries(account_ids: List[str]) -> List[Dict[str, Any]]:
    """Build the pool.json entries from a list of keychain UUIDs."""
    import time
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    entries: List[Dict[str, Any]] = []
    for aid in account_ids:
        if not UUID_RE.match(aid):
            print(f"  SKIPPING non-UUID ghost ID: {aid[:80]}")
            continue
        short = aid.split("-")[0] if "-" in aid else aid[:8]
        entries.append({
            "id": aid,
            "api_key": SENTINEL,
            "alias_email": f"recovered-{short}@unknown.local",
            "key_name": "recovered-from-keychain",
            "created_at": now,
            "used": False,
            "used_at": None,
            "credits_initial": 6.0,
            "credits_remaining": 6.0,
            "suspended": False,
            "recovered": True,
            "recovery_note": "Reconstructed from macOS Keychain — original metadata lost",
        })
    return entries


def cmd_verify() -> int:
    accounts = _dump_keychain_accounts()
    print(f"Keychain '{KEYCHAIN_SERVICE}' has {len(accounts)} entries")
    print(f"Pool file: {POOL_PATH}")
    print(f"  exists: {POOL_PATH.exists()}")
    if POOL_PATH.exists():
        try:
            data = json.loads(POOL_PATH.read_text())
            if isinstance(data, list):
                print(f"  keys in pool.json: {len(data)}")
            elif isinstance(data, dict) and "accounts" in data:
                print(f"  keys in pool.json (legacy): {len(data['accounts'])}")
        except json.JSONDecodeError as e:
            print(f"  pool.json is corrupt: {e}")
    return 0


def cmd_recover(apply: bool) -> int:
    if POOL_PATH.exists() and not apply:
        print(f"Refusing to overwrite existing pool file without --apply")
        print(f"  {POOL_PATH}")
        return 1

    accounts = _dump_keychain_accounts()
    if not accounts:
        print(f"No keychain entries found for service '{KEYCHAIN_SERVICE}'")
        return 2

    print(f"Found {len(accounts)} keychain entries")
    if not apply:
        print("DRY-RUN — no file will be written. Use --apply to write.")
        sample = accounts[:3]
        print(f"Sample IDs: {sample}")
        return 0

    entries = build_pool_entries(accounts)
    POOL_PATH.parent.mkdir(parents=True, exist_ok=True)
    POOL_PATH.write_text(json.dumps(entries, indent=2))
    print(f"✅ Recovered {len(entries)} keys → {POOL_PATH}")
    print(f"   All keys marked as recovered=True (rebuildable from keychain)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = parser.add_subparsers(dest="cmd", required=False)

    sub.add_parser("verify", help="Check keychain + pool file state")
    p_recover = sub.add_parser("recover", help="Recover pool from keychain (default dry-run)")
    p_recover.add_argument("--apply", action="store_true",
                           help="Actually write the pool file (required for recovery)")

    args = parser.parse_args()
    if args.cmd == "verify":
        return cmd_verify()
    if args.cmd == "recover":
        return cmd_recover(apply=getattr(args, "apply", False))
    # No subcommand: default to verify (safe)
    return cmd_verify()


if __name__ == "__main__":
    sys.exit(main())
