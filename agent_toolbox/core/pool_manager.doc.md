# pool_manager.py — API Key Pool Manager

## What
Core pool management: add, lease, return, mark, report, stats, SSE events.
Backs the entire Fireworks AI key pool (261 keys, 253 currently suspended).

## Why
- **Atomic leasing**: Multi-process safe — proxies + dashboard all lease from
  the same pool without conflicts
- **TTL-based**: Leases auto-expire (30 min default) so crashed consumers
  don't lock keys forever (supplemented by V19.10 background cleanup)
- **Atomic report+lease**: `report_key()` suspends a bad key AND leases a
  replacement in one call — avoids the "double-key waste" pattern

## Touched by
- `agent_toolbox/api/routes/pool.py` — REST endpoints
- `agent_toolbox/start_toolbox.py` — V19.10 background cleanup loop
- `agent_toolbox/core/keychain_store.py` — macOS Keychain for API key values
- `proxy/pool_client.py` — async HTTP client called by proxy server

## Key methods
- `add_key()` — new key to pool
- `lease_key()` — atomic lease with TTL + optional backup lease
- `return_key()` — release a lease (V19.11 flow returns expired keys)
- `mark_suspended()` — mark as dead (V19.11 also clears lease fields)
- `unsuspend_key()` — re-activate false-positive suspensions (V19.9, used by test_keys.py)
- `report_key()` — atomic suspend + lease replacement
- `expire_leases()` — clear expired leases (called by V19.10 cleanup loop)
- `get_stats()` — pool totals (used by dashboard)

## V19.11: mark_suspended lease-field cleanup
Before: `mark_suspended()` only set `suspended=True`. Lease fields
(`leased_until`, `leased_to`, `lease_id`, `leased_at`) remained set.
This didn't affect stats (suspended keys are excluded from leased count)
but left "phantom" lease records in the JSON.

After: `mark_suspended()` also sets lease fields to `None`. Cleaner state,
easier debugging, prevents confusion in tools that iterate lease fields.

## Storage
- `data/fireworksai-pool.json` — 261 entries, each with id, alias_email,
  api_key (stub, real value in keychain), leased_*, suspended_*, etc.
- `com.sinator.pool` Keychain — actual API key values (macOS encrypted)

## Usage
```python
from agent_toolbox.core.pool_manager import get_pool_manager
pm = get_pool_manager()
key = pm.lease_key(leased_to="my-app")
pm.return_key(key["key_id"])
```

## Caveats
- **No row-level locking**: Multi-process safety relies on `reload()` + `save()`
  being fast (single JSON file, ~261 entries, <100ms typical)
- **Keychain dependency**: On macOS, real API key values are in Keychain. The
  pool.json has empty `api_key` fields. The `_hydrate_key()` method retrieves
  from Keychain on demand.
- **V19.8 auto-recovery**: If pool.json is missing, `_load()` tries to
  reconstruct from Keychain entries.
