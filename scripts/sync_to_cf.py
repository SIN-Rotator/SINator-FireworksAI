#!/usr/bin/env python3
"""
Mac → Cloudflare D1 Sync (Issue #24)

Pusht den lokalen Pool (data/fireworksai-pool.json) zum CF Worker /pool/push.
Soll nach JEDER Rotation laufen, damit der Fallback-Worker aktuelle Keys hat.

Env-Vars (Question #3 — Key-Sync via Env-Var, kein Hardcoding):
    CF_WORKER_URL   z.B. https://sinatorpool-router.delqhi.com   (oder *.workers.dev)
    CF_SYNC_TOKEN   Bearer-Token, identisch zu `wrangler secret put SYNC_TOKEN`

Usage:
    python3 scripts/sync_to_cf.py                # einmalig
    python3 scripts/sync_to_cf.py --watch 60     # alle 60s
    # oder als Funktion: from scripts.sync_to_cf import sync_now

Exit-Codes: 0 = ok, 1 = config fehlt, 2 = http/transport error.
"""
import os
import sys
import json
import time
import argparse
from pathlib import Path

try:
    import httpx
except ImportError:  # pragma: no cover - httpx is a project dependency
    httpx = None

_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_POOL_PATH = _ROOT / "data" / "fireworksai-pool.json"


def _hydrate(keys: list[dict]) -> list[dict]:
    """Replace Keychain SENTINEL values with the real api_key (macOS only)."""
    try:
        sys.path.insert(0, str(_ROOT))
        from agent_toolbox.core.keychain_store import retrieve_key, SENTINEL
    except Exception:
        return keys  # not on Mac / module missing → assume plaintext keys

    out = []
    for k in keys:
        if k.get("api_key") == SENTINEL:
            real = retrieve_key(k.get("id", ""))
            if real:
                k = {**k, "api_key": real}
            else:
                continue  # cannot hydrate → skip, never push a SENTINEL
        out.append(k)
    return out


def _to_d1_rows(keys: list[dict]) -> list[dict]:
    """Map pool.json schema → D1 push schema (status derived from flags)."""
    rows = []
    for k in keys:
        status = "active"
        if k.get("suspended"):
            status = "suspended"
        elif k.get("used"):
            status = "used"
        rows.append(
            {
                "id": k.get("id"),
                "api_key": k.get("api_key"),
                "alias_email": k.get("alias_email", ""),
                "key_name": k.get("key_name", ""),
                "status": status,
                "created_at": k.get("created_at"),
                "suspended_at": k.get("suspended_at"),
                "suspended_reason": k.get("suspended_reason"),
                "credits_initial": k.get("credits_initial", 6.0),
                "credits_remaining": k.get("credits_remaining"),
            }
        )
    return rows


def sync_now(pool_path: Path = DEFAULT_POOL_PATH) -> dict:
    """Push the current pool to the CF Worker. Returns the worker's JSON reply."""
    worker_url = os.environ.get("CF_WORKER_URL", "").rstrip("/")
    sync_token = os.environ.get("CF_SYNC_TOKEN", "").strip()
    if not worker_url or not sync_token:
        raise SystemExit(
            "CF_WORKER_URL and CF_SYNC_TOKEN must be set (see scripts/sync_to_cf.py docstring)"
        )
    if httpx is None:
        raise SystemExit("httpx not installed (pip install httpx)")
    if not pool_path.exists():
        raise SystemExit(f"Pool file not found: {pool_path}")

    keys = json.loads(pool_path.read_text())
    keys = _hydrate(keys)
    rows = _to_d1_rows(keys)

    # Chunk to stay friendly with D1 batch limits and request size.
    CHUNK = 200
    total = 0
    last = {}
    with httpx.Client(timeout=30.0) as client:
        for i in range(0, len(rows), CHUNK):
            chunk = rows[i : i + CHUNK]
            r = client.post(
                f"{worker_url}/pool/push",
                headers={"Authorization": f"Bearer {sync_token}"},
                json={"keys": chunk},
            )
            if r.status_code != 200:
                print(f"[cf-sync] push failed {r.status_code}: {r.text[:200]}", flush=True)
                sys.exit(2)
            last = r.json()
            total += last.get("synced", len(chunk))
    print(f"[cf-sync] pushed {total} keys → {worker_url}", flush=True)
    return {**last, "synced_total": total}


def main():
    ap = argparse.ArgumentParser(description="Sync local pool to Cloudflare D1")
    ap.add_argument("--pool", default=str(DEFAULT_POOL_PATH), help="Path to pool JSON")
    ap.add_argument("--watch", type=int, default=0, help="Repeat every N seconds")
    args = ap.parse_args()
    pool_path = Path(args.pool)

    if args.watch > 0:
        print(f"[cf-sync] watch mode every {args.watch}s", flush=True)
        while True:
            try:
                sync_now(pool_path)
            except SystemExit as e:
                print(f"[cf-sync] {e}", flush=True)
            except Exception as e:  # keep the loop alive
                print(f"[cf-sync] error: {e}", flush=True)
            time.sleep(args.watch)
    else:
        sync_now(pool_path)


if __name__ == "__main__":
    main()
