# key_cache.py — Primary/Backup Key Cache

## What
On-disk persistent cache for the proxy's currently leased primary and backup
API keys, plus the V19.11 "previous" key (expired, pending return to pool).

## Why
- **Survive proxy restarts**: Without disk persistence, every restart would
  lease a new key → 1 key wasted per restart per proxy (10 keys/min in a crash loop)
- **Instant backup swap**: Pre-fetched backup key gives 0ms failover when
  primary returns 401/402/403/412/429
- **V19.11 crash recovery**: `previous-key.json` lets a restarted proxy return
  the expired key it never got to return before dying

## Touched by
- `proxy/server.py` — calls `set_primary()`, `set_backup()`, `get_primary()`,
  `promote_backup()`, `pop_previous()`

## Cache files (in `~/.sin-pool/`)
- `current-key.json` — primary key, expires_at tracked
- `backup-key.json` — pre-fetched backup for instant swap
- `previous-key.json` — V19.11: expired key waiting to be returned to pool

## Methods
- `_load()` / `_save()` — disk persistence (auto-called on every mutation)
- `set_primary(key_info)` — new primary, resets request_count
- `set_backup(key_info)` — new backup
- `get_primary()` — returns primary OR None if expired
  - **V19.11**: on expiry, saves to `self.previous` and persists
- `promote_backup()` — backup → primary (used after primary dies)
- `pop_previous()` — V19.11: get and clear `previous` for return-to-pool
- `clear_primary()` / `clear_backup()` / `clear_all()` — wipe from disk
- `status()` — for `/health` endpoint

## Expiry behavior
```python
expires = self.primary.get("expires_at", 0)
if expires and time.time() > expires:
    # V19.11: save to previous instead of just clearing
    self.previous = self.primary
    self.primary = None
    self._save()
    return None
```

## Usage
```python
cache = KeyCache()
cache.set_primary({"key_id": "...", "api_key": "fw_...", "expires_at": time.time()+1800})
key = cache.get_primary()  # Returns the key, or None if expired (saved to previous)
```

## Caveats
- **`expires_at` must be set**: If 0/missing, the cache never auto-expires
- **No locking**: If two processes share `~/.sin-pool/`, they'll race on writes
- **`previous` cleared on `set_primary`**: A new primary means the old expired one
  has been handled (returned) — no need to keep it
