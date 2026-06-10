# CF Sync (`sync_to_cf.py`)

Pushes the local key pool from the Mac into the Cloudflare Worker's D1 database
(**Issue #24**). Runs after every rotation so the CF fallback always has fresh
keys. The Mac stays the source of truth — this is push-only.

## Dependencies

- **Imports:** `os`, `sys`, `json`, `time`, `argparse`, `urllib.request`, `urllib.error`, `pathlib.Path`
- **Optional:** `agent_toolbox.core.keychain_store` to hydrate Keychain-sentinel keys
- **Config:** `CF_WORKER_URL`, `CF_SYNC_TOKEN` (env or `proxy.config`)

## Key Functions

| Symbol | Purpose |
|--------|---------|
| `_hydrate(keys)` | Replace Keychain sentinels with real API keys via `keychain_store` |
| `_to_d1_rows(keys)` | Map pool entries to the D1 `pool_keys` row shape |
| `sync_now(pool_path=DEFAULT_POOL_PATH)` | Load → hydrate → map → `POST /pool/push`, returns counts |
| `main()` | CLI entry; supports `--pool` and `--watch N` |

## CLI Usage

```bash
# one-shot sync (after a rotation)
CF_WORKER_URL=https://... CF_SYNC_TOKEN=... python3 scripts/sync_to_cf.py

# continuous — re-sync every N seconds
python3 scripts/sync_to_cf.py --watch 60

# custom pool file
python3 scripts/sync_to_cf.py --pool data/fireworksai-pool.json
```

## Env Vars

| Variable | Purpose |
|----------|---------|
| `CF_WORKER_URL` | Worker base URL (push target) |
| `CF_SYNC_TOKEN` | Bearer token matching the Worker's `SYNC_TOKEN` secret |

## Known Caveats

- Keychain hydration only works on the Mac where the keys were stored; sentinels without a matching Keychain entry are skipped (logged).
- Exits non-zero if `CF_WORKER_URL` / `CF_SYNC_TOKEN` are unset so it can be wired into rotation hooks safely.
- Push-only: D1 never writes back to the Mac pool, keeping the Mac authoritative.
