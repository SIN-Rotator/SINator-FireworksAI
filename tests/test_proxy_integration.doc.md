# Test Proxy Integration (`test_proxy_integration.py`)

Integration tests for the Pool Proxy V13 — 10 instances behind the pool-router. Tests verify that the proxy correctly handles Fireworks error codes the way the opencode TUI would experience them.

## Dependencies

- **Imported by:** (test runner only)
- **Imports:** `httpx`, `json`, `time`
- **External state:** 10 proxy instances on `localhost:8888`-`localhost:8897`
- **External state:** Pool-Router on `localhost:9998` (default test target)
- **External state:** Pool API on `localhost:8100/api/v1`
- **External state:** Cache files at `~/.sin-pool/current-key.json` and `~/.sin-pool/backup-key.json` (backed up/restored)

## Test Targets

| Endpoint | Purpose |
|----------|---------|
| `PROXY_URL = http://localhost:9998` | Pool-Router (default entry, single endpoint) |
| `PROXY_URLS` | All 10 individual proxies (`8888`-`8897`) for direct testing |
| `POOL_API = http://localhost:8100/api/v1` | Pool management API |

## Test Coverage

| Test | Verifies |
|------|----------|
| `test_proxy_health` | `/health` returns 200, status `ok` or `no_key`, backup key present |
| `test_proxy_pool_status` | `/pool-status` returns pool + cache + proxy_id info |
| `test_api_through_proxy` | Non-streaming `/inference/v1/models` succeeds through proxy |
| `test_chat_completion_streaming` | SSE streaming chat completion yields chunks |
| `test_error_handling` | Bad key → 401 from Fireworks → proxy reports as suspended |
| `test_failover` | Primary key fails → backup key used → pool reports dead key |
| (more) | Cache invalidation, model listing, rate limit handling |

## Cache State Preservation

```python
CACHE_FILE = "/Users/jeremy/.sin-pool/current-key.json"
BACKUP_CACHE = "/Users/jeremy/.sin-pool/backup-key.json"

def _save_cache_state():
    """Save current cache files so we can restore after tests."""
    ...

def _restore_cache_state(state):
    """Restore cache files after tests."""
    ...
```

Tests **save and restore** the proxy cache state to avoid breaking the running proxy.

## Important Config/Limits

| Setting | Value |
|---------|-------|
| Pool-Router port | 9998 |
| Proxy instance range | 8888-8897 (10 instances) |
| Default test timeout | 5-15s depending on test |
| Streaming timeout | 30s (chat completion) |
| Cache files | `~/.sin-pool/{current-key,backup-key}.json` |

## Known Caveats

- **Requires all 10 proxy instances running** — tests will fail with connection refused if any proxy is down. Start with `cd proxy && ./start-multi.sh`.
- **Tests can leave the pool in a degraded state** — bad-key tests report keys as `used` or `suspended`. Use the `suspended` filter in `tools/swap_key.py` to recover.
- **Pool-Router auth** — V19.2+ requires `Authorization: Bearer <token>` for `/v1/models` and `/v1/chat/completions`. Health endpoints remain public.
- **Cache files must exist** — `_save_cache_state()` returns `None` for missing files; if both cache files are missing, the test will skip with a clear error.
- **Streaming tests are slow** — expect 15-30s for chat completion round-trips.

## Usage

```bash
# All proxy integration tests
pytest tests/test_proxy_integration.py -v

# Specific test
pytest tests/test_proxy_integration.py::test_api_through_proxy -v

# Test against a specific proxy instance directly (bypass pool-router)
pytest tests/test_proxy_integration.py -v --proxy-url=http://localhost:8888
```

## See Also

- `proxy/server.py` — the proxy system under test
- `proxy/server.doc.md` — proxy architecture, model list, error handling
- `scripts/pool-router.py` — the pool-router (load balancer + auth)
- `agent_toolbox/core/pool_manager.py` — pool state management
