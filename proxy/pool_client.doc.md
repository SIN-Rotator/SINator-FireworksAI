# Pool API Client (`pool_client.py`)

Async HTTP client that communicates with the backend pool API (`agent_toolbox`) for key leasing, reporting, and stats.

## Dependencies

- **Imported by:** `proxy.server`
- **Imports:** `logging`, `typing`, `httpx`, `proxy.config.load_config`

## Key Class

| Symbol | Purpose |
|--------|---------|
| `PoolClient` | HTTP client for the backend pool API |

### Methods

| Method | Purpose |
|--------|---------|
| `lease(leased_to="proxy")` | POST `/pool/lease` — obtain a key with TTL |
| `return_key(key_id, lease_id)` | POST `/pool/return` — return a leased key |
| `report(api_key, key_id, reason, leased_to)` | POST `/pool/report` — report dead/suspended key, atomically get replacement |
| `stats()` | GET `/pool/stats` — pool availability stats |
| `close()` | Close the underlying httpx session |

## Configuration

Uses `proxy.config.load_config()` for:
- `pool_api_url` (default: `http://localhost:8000/api/v1`)
- `lease_ttl_seconds` (default: 1800)
- `lease_backup` (default: false)

## Error Handling

- `lease()` returns `None` on any failure (logged)
- `return_key()` returns `False` on failure
- `report()` returns `None` on 404 (key not in pool); logs errors for other failures
- `stats()` returns `None` on failure
