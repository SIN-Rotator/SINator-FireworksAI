# recover_pool.py — Pool Recovery from macOS Keychain

**Purpose:** Reconstruct `data/fireworksai-pool.json` from the surviving API keys in macOS Keychain when the metadata file is missing or corrupted.

**Context:** The pool file was untracked from git in commit 8926051 (`chore(security): untrack data/fireworksai-pool.json`) and got deleted at 2026-06-02 07:30 (cause unknown — possibly a sync/cleanup tool). The 255+ actual API keys are still safe in macOS Keychain under service `com.sinator.pool`. This script rebuilds the metadata so the backend can come back online.

## Usage

```bash
python tools/recover_pool.py verify           # Check state, don't write
python tools/recover_pool.py recover          # Dry-run, shows what would happen
python tools/recover_pool.py recover --apply  # Actually rebuild pool.json
```

## What is recovered vs lost

| Field | Recovered? | Notes |
|-------|-----------|-------|
| `id` (UUID) | ✅ Yes | Read from keychain account name |
| `api_key` | ✅ Sentinel | Real key in keychain, marker in JSON |
| `alias_email` | ⚠️ Placeholder | `recovered-<short_id>@unknown.local` |
| `key_name` | ⚠️ Placeholder | `recovered-from-keychain` |
| `created_at` | ⚠️ NOW | Recovery timestamp, not original |
| `used` | ❌ Default `False` | Original state lost — pool will retry everything |
| `used_at` | ❌ `None` | |
| `credits_initial` | ⚠️ 6.0 (default) | |
| `credits_remaining` | ⚠️ 6.0 (default) | Will be corrected on first use |
| `suspended` | ❌ Default `False` | All keys appear active — will be re-marked on proxy 412/429/413 |
| `recovered: true` | ✅ Marker | Lets you identify recovered keys vs originals |

## What happens next

- The proxy (port 8888-8897) will try all 255 keys
- Suspended keys (most of them) will return 412/429/413 → re-marked as `suspended: true` on next report
- The pool will self-heal over the next few requests
- A new rotation (160s) will produce a new alias + new key for fresh accounts

## Why this works

The pool architecture separates concerns:
- **macOS Keychain** (encrypted) holds the actual API keys
- **JSON metadata** holds: which alias owns which key, when it was created, how many credits, etc.

When JSON is lost but keychain survives, we can rebuild with placeholders and let the system reconverge.

## Why this is safe

- Keychain entries are NEVER removed by this script
- The script only WRITES the JSON metadata file
- All recovered keys work for Fireworks API calls (verified by `security find-generic-password -w`)
- The pool may briefly show all 255 as "available" — but the proxy will mark dead ones as suspended on first error

## Future improvements (V19.9+)

- [ ] Daily snapshot of pool.json to ~/.sinator/snapshots/ (cron) for true backup
- [ ] Atomic write (tmp + rename) to prevent partial-write corruption
- [ ] Health check on backend startup: if keychain has more keys than JSON, log warning
- [ ] Optional Cloudflare KV sync (via existing `scripts/sync_to_cf.py`) as off-machine backup

## See also

- `pool_manager.py:41-60` — `_load()` method
- `keychain_store.py:26-27` — `KEYCHAIN_SERVICE` and `SENTINEL` constants
- `infra-sin-opencode-stack/bin/sin-sync` (V19.8) — now excludes `data/fireworksai-pool.json`
- `~/.local/bin/sync-opencode.sh` (V19.8) — same exclusion
- AGENTS.md V19.8 — incident report
