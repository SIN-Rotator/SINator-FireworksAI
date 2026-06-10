# Pool Routes (`pool.py`)

FastAPI router for the Fireworks API Key Pool: stats, CRUD, leasing, health checks, and SSE live updates.

## Dependencies

- **Imported by:** `agent_toolbox/start_toolbox.py`
- **Imports:** `fastapi.APIRouter`, `fastapi.responses.StreamingResponse`, `agent_toolbox.core.pool_manager`, `agent_toolbox.core.keychain_store`, `agent_toolbox.api.schemas`

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/pool/stats` | GET | Pool statistics (total, used, leased, suspended, available) |
| `/pool/add` | POST | Add a new API key to the pool |
| `/pool/use` | POST | Mark a key as used |
| `/pool/key` | GET | Get next available key (plaintext) |
| `/pool/lease` | POST | Atomically lease a key with TTL |
| `/pool-lease` | GET | Lease a key via GET (Dashboard compatibility) |
| `/pool/return` | POST | Return a leased key |
| `/pool/report` | POST | Report bad key, mark used, return replacement |
| `/pool/events` | GET | SSE stream for dashboard live updates |
| `/pool/health` | GET | Validate all keys via Fireworks API |
| `/pool/reveal/{key_id}` | GET | Reveal actual API key from Keychain |
| `/pool/migrate-to-keychain` | POST | Migrate plaintext keys to macOS Keychain |
| `/pool/{key_id}` | DELETE | Remove a key from the pool |

## Key Functions

| Symbol | Purpose |
|--------|---------|
| `get_pool_stats()` | Return key pool statistics |
| `add_key_to_pool()` | Add a new API key with alias metadata |
| `mark_key_used()` | Mark key as consumed |
| `get_api_key()` | Return next available hydrated key |
| `report_bad_key()` | Mark key as used and atomically lease a replacement |
| `lease_key()` / `lease_key_get()` | Lease a key with configurable TTL |
| `return_leased_key()` | Return key to available pool |
| `pool_events()` | SSE generator for real-time dashboard updates |
| `check_pool_health()` | Validate all keys via `/v1/models` endpoint |
| `reveal_key()` | Decrypt key from Keychain for display |
| `delete_key()` | Remove key entry entirely |

## Important Config/Limits

- Pool data stored in `data/fireworksai-pool.json`
- Leased keys have a TTL (default 1800s/30min)
- Health check hits `https://api.fireworks.ai/inference/v1/models` with `Authorization: Bearer {key}`
- SSE events: `key_leased`, `key_returned`, `key_swapped`, `stats` (every 30s)

## Known Caveats

- No authentication on any endpoint — relies on localhost/network isolation
- `/pool/reveal/{key_id}` exposes plaintext keys — must not be exposed publicly
