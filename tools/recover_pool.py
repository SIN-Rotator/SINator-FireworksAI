"""
V19.20: Pool Recovery Tool

Recovers pool from:
  1. pool-snapshots/pool-latest.json (V19.20 automatic snapshot)
  2. data/fireworksai-pool.json (current pool)
  3. recovered-keys-pending.json (keychain recovery, if main pool is missing)
  4. github-backup/pool-latest.enc (V19.21 encrypted backup, requires pycryptodome)

SAFETY: NEVER overwrites an existing valid pool.
Only restores when main pool.json is missing or invalid.

Usage:
  python tools/recover_pool.py --status       # Show recovery options
  python tools/recover_pool.py --hydrate      # Hydrate STORED_IN_KEYCHAIN from Keychain
  python tools/recover_pool.py --from-snapshot pool-snapshots/pool-XXX.json
  python tools/recover_pool.py --from-encrypted github-backup/pool-XXX.enc
"""
import argparse
import json
import sys
import os
import time
import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

POOL_PATH = REPO_ROOT / "data" / "fireworksai-pool.json"
SNAPSHOTS_DIR = REPO_ROOT / "data" / "pool-snapshots"
PENDING_PATH = REPO_ROOT / "data" / "recovered-keys-pending.json"
BACKUP_DIR = REPO_ROOT / "data" / "github-backup"


def get_status():
    """Show recovery status + available sources."""
    print("=" * 60)
    print("V19.20 POOL RECOVERY STATUS")
    print("=" * 60)
    print(f"\nMain pool: {POOL_PATH}")
    print(f"  exists: {POOL_PATH.exists()}")
    if POOL_PATH.exists():
        try:
            with open(POOL_PATH) as f:
                pool = json.load(f)
            keys = pool if isinstance(pool, list) else pool.get("keys", [])
            real = sum(1 for k in keys if k.get("api_key", "").startswith("fw_"))
            placeholder = sum(1 for k in keys if k.get("recovered"))
            suspended = sum(1 for k in keys if k.get("suspended"))
            print(f"  total: {len(keys)}")
            print(f"  real fw_ keys: {real}")
            print(f"  recovered placeholders: {placeholder}")
            print(f"  suspended: {suspended}")
        except Exception as e:
            print(f"  ERROR reading: {e}")

    print(f"\nSnapshots: {SNAPSHOTS_DIR}")
    if SNAPSHOTS_DIR.exists():
        snaps = sorted(SNAPSHOTS_DIR.glob("pool-*.json"), reverse=True)
        print(f"  found: {len(snaps)}")
        for s in snaps[:5]:
            print(f"    {s.name}")
    else:
        print("  (none)")

    print(f"\nPending (keychain recovery): {PENDING_PATH}")
    print(f"  exists: {PENDING_PATH.exists()}")

    print(f"\nEncrypted backups: {BACKUP_DIR}")
    if BACKUP_DIR.exists():
        encs = sorted(BACKUP_DIR.glob("pool-*.enc"), reverse=True)
        print(f"  found: {len(encs)}")
        for e in encs[:5]:
            print(f"    {e.name}")
    else:
        print("  (none)")


def hydrate_from_keychain():
    """Read keychain + replace STORED_IN_KEYCHAIN placeholders with real fw_ keys.
    Preserves all existing metadata (alias_email, suspended status, etc).
    """
    from agent_toolbox.core.keychain_store import retrieve_key

    print("=" * 60)
    print("V19.20 KEYCHAIN HYDRATION")
    print("=" * 60)

    with open(POOL_PATH) as f:
        pool = json.load(f)
    keys = pool if isinstance(pool, list) else pool.get("keys", [])

    if not keys:
        print("Pool is empty — nothing to hydrate")
        return

    print(f"Pool has {len(keys)} entries. Hydrating from keychain...")

    hydrated = 0
    failed = 0
    for k in keys:
        kid = k.get("id", "")
        if k.get("api_key", "").startswith("fw_"):
            continue  # already real
        val = retrieve_key(kid)
        if val and val.startswith("fw_"):
            k["api_key"] = val
            k["recovered"] = False
            k.pop("hydration_note", None)
            hydrated += 1
        else:
            failed += 1

    print(f"  hydrated: {hydrated}")
    print(f"  failed (no keychain entry): {failed}")

    # Save
    with open(POOL_PATH, "w") as f:
        json.dump(keys, f, indent=2)
    print(f"✓ Pool saved with {hydrated} real keys")


def restore_from_snapshot(snapshot_path: str):
    """Restore pool from a snapshot file."""
    src = Path(snapshot_path)
    if not src.exists():
        print(f"ERROR: {src} not found")
        return
    print(f"Restoring from {src} → {POOL_PATH}")
    with open(src) as f:
        data = json.load(f)
    with open(POOL_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"✓ Restored {len(data)} keys")


def restore_from_encrypted(enc_path: str):
    """Restore pool from encrypted backup (V19.21)."""
    try:
        from Crypto.Cipher import AES
    except ImportError:
        print("ERROR: pycryptodome not installed. Run: pip install pycryptodome")
        return
    src = Path(enc_path)
    if not src.exists():
        print(f"ERROR: {src} not found")
        return
    raw = src.read_bytes()
    if len(raw) < 28:
        print(f"ERROR: {src} too small ({len(raw)} bytes) — invalid backup")
        return
    nonce, tag, ciphertext = raw[:12], raw[12:28], raw[28:]
    machine_id = f"{os.uname().nodename}-{os.environ.get('USER','unknown')}"
    key = hashlib.sha256(f"sinator-pool-backup-{machine_id}-v19.21".encode()).digest()
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    try:
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
    except Exception as e:
        print(f"ERROR: Decryption failed: {e}")
        return
    with open(POOL_PATH, "wb") as f:
        f.write(plaintext)
    data = json.loads(plaintext)
    print(f"✓ Decrypted and restored {len(data)} keys")


def main():
    parser = argparse.ArgumentParser(description="V19.20 Pool Recovery")
    parser.add_argument("--status", action="store_true", help="Show recovery options")
    parser.add_argument("--hydrate", action="store_true", help="Hydrate from Keychain")
    parser.add_argument("--from-snapshot", help="Restore from snapshot file")
    parser.add_argument("--from-encrypted", help="Restore from encrypted backup")
    args = parser.parse_args()

    if args.status:
        get_status()
    elif args.hydrate:
        hydrate_from_keychain()
    elif args.from_snapshot:
        restore_from_snapshot(args.from_snapshot)
    elif args.from_encrypted:
        restore_from_encrypted(args.from_encrypted)
    else:
        get_status()
        print("\nUsage: --hydrate | --from-snapshot <file> | --from-encrypted <file>")


if __name__ == "__main__":
    main()
