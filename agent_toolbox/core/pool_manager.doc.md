# File: `pool_manager.py`

Manages the Fireworks API key pool: add, lease, return, mark used/suspended, stats, and atomic swap (report+lease). Integrates with Keychain for secret storage and SSE for real-time events.

## Dependencies

- **Imported by:** `tools/rotate.py`, `agent_toolbox/api/routes/pool.py`, `tests/test_pool_manager.py`, `tools/sinator-cli.py`
- **Imports:** `json`, `time`, `uuid`, `pathlib`, from `keychain_store`: `store_key`, `retrieve_key`, `delete_key`, `SENTINEL`

## Key Classes/Functions

| Symbol | Purpose |
|--------|---------|
| `PoolManager` | Full key lifecycle: add, lease, return, mark, report+swap, stats, credit tracking |
| `get_pool_manager()` | Singleton accessor for PoolManager (lazy-init) |
| `register_sse_listener()` | Register an `asyncio.Queue` for SSE events (key_leased, key_returned, key_swapped) |
| `unregister_sse_listener()` | Remove an SSE listener queue |

## Important Config/Limits

- Pool file: `data/fireworksai-pool.json` (auto-created)
- Default credits initial: `$6.00`
- Lease TTL: 1800s (30min) default
- Stats formula: `available = total - used - suspended - leased`
- Auto-suspend when `credits_remaining <= 0.01`
- SSE events: `key_leased`, `key_returned`, `key_swapped`

## Known Caveats

- `report_key()` suspends + leases atomically — caller must use the returned new key
- Lease expiry is checked on every `get_stats()` and `lease_key()` call — no background cleanup
- `lease_backup=True` tries to lease a second key (may return partial result)
- Pool format supports both `{"accounts": [...]}` (legacy) and `[...]` (new) on load
