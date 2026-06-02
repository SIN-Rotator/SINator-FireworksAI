# Test Pool Manager (`test_pool_manager.py`)

Unit tests for `PoolManager` — covers lease, return, expire, and report logic. **Pure logic tests** — no network, no real pool data. Uses temporary file fixtures for isolation.

## Dependencies

- **Imported by:** (test runner only)
- **Imports:** `pytest`, `json`, `time`, `tempfile`, `pathlib`
- **Imports:** `agent_toolbox.core.pool_manager.PoolManager` (the system under test)
- **No network, no Chrome, no external state** — safe to run anywhere

## Test Architecture

```python
@pytest.fixture
def temp_pool():
    """PoolManager backed by a temp file with sample data."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump([...], f)  # 4 sample keys: alpha/beta/gamma/delta
    yield PoolManager(str(f.name))
    # cleanup
```

Each test gets a **fresh, isolated pool** in a temp file. Tests cannot interfere with each other or the real `data/fireworksai-pool.json`.

## Test Coverage

| Area | What's tested |
|------|---------------|
| `lease_key()` | Returns available key, marks leased, sets timestamps |
| `return_key()` | Releases lease, returns key to available pool |
| `expire_leases()` | Auto-expires leases past `leased_until` |
| `report_key()` | Marks key as used, leases replacement atomically |
| `stats()` | Returns correct counts (total, available, used, suspended) |
| Edge cases | Empty pool, all-used pool, double-lease prevention |

## Important Config/Limits

| Setting | Value |
|---------|-------|
| Sample pool size | 4 keys (alpha, beta, gamma, delta) |
| Initial credits | 6.0 per key |
| Test isolation | Per-test temp file (auto-cleanup) |
| Lease duration | Configurable per test (typically 60s) |

## Known Caveats

- **No real API calls** — these tests verify the in-memory logic only. They do NOT verify Fireworks API behavior.
- **Sample data may not reflect production state** — production keys have additional fields (`created_at`, `last_used`, `metadata`) that sample data omits.
- **Temp file path is platform-dependent** — uses Python's `tempfile` module, no hardcoded paths.

## Usage

```bash
# All pool manager tests
pytest tests/test_pool_manager.py -v

# Single test class
pytest tests/test_pool_manager.py::TestLease -v

# With coverage
pytest tests/test_pool_manager.py -v --cov=agent_toolbox.core.pool_manager
```

## See Also

- `agent_toolbox/core/pool_manager.py` — the system under test
- `agent_toolbox/core/pool_manager.doc.md` — architecture and API documentation
