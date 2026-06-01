# Key Cache (`key_cache.py`)

On-disk key cache with a primary/backup pattern for zero-downtime key rotation. Persists leases to JSON files in `CACHE_DIR` so keys survive proxy restart.

## Dependencies

- **Imported by:** `proxy.server`
- **Imports:** `json`, `time`, `logging`, `pathlib.Path`, `typing`

## Key Class

| Symbol | Purpose |
|--------|---------|
| `KeyCache` | Primary + backup key cache with file persistence and lease expiry |

### Methods

| Method | Purpose |
|--------|---------|
| `set_primary(key_info)` | Set primary key, reset request count, persist |
| `set_backup(key_info)` | Set backup key, persist |
| `get_primary()` | Get primary if not expired, increment request count |
| `promote_backup()` | Move backup → primary if not expired |
| `clear_primary()` / `clear_backup()` | Remove individual slot |
| `clear_all()` | Remove both slots and reset counters |
| `status()` | Return diagnostic dict (key_ids truncated, expiration, request count) |

## File Persistence

| File | Path |
|------|------|
| Primary | `CACHE_DIR / current-key.json` |
| Backup | `CACHE_DIR / backup-key.json` |

## Lease Expiry

If `key_info["expires_at"] < time.time()` the key is treated as expired and the cache returns `None` / auto-clears the file.
