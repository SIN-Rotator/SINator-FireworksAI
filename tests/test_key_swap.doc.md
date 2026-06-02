# Test Key Swap (`test_key_swap.py`)

Tests for the auto-key-swap feature: `POST /api/v1/pool/report` (FastAPI endpoint) + `tools/swap_key.py` (CLI tool). Verifies the full round-trip from key report to auth file update.

## Dependencies

- **Imported by:** (test runner only)
- **Imports:** `pytest`, `httpx`, `json`, `shutil`, `subprocess`
- **External state:** `data/fireworksai-pool.json` (backed up/restored via `pool_backup` fixture)
- **External state:** `~/.local/share/opencode/auth.json` (backed up/restored via `auth_backup` fixture)
- **Requires:** Pool backend running on `http://localhost:3000/api/v1` (Tauri dashboard API)

## ⚠️ Critical: Pool Backup Protocol

```python
@pytest.fixture(scope="module", autouse=True)
def pool_backup():
    """Backup pool before module, restore after."""
    _backup_pool()
    yield
    _restore_pool()
```

The pool file is **automatically backed up** to `fireworksai-pool.json.test_backup` before any test runs and **restored** after. **NEVER** remove this fixture — it prevents real keys from being consumed by tests.

## Test Classes

| Class | Tests | Purpose |
|-------|-------|---------|
| `TestPoolReport` | 5 | API endpoint behavior (by api_key, by key_id, unknown key, empty body, no echo) |
| `TestSwapKeyCLI` | 3 | `tools/swap_key.py` CLI: explicit key, auth file update, output format |
| `TestIntegration` | 1 | Round-trip: report via API → verify key swapped + auth updated |

## Key Test Scenarios

| Test | Expectation |
|------|-------------|
| `test_report_by_api_key` | 200, `swapped=True`, new key starts with `fw_`, alias ends with `@gmx.de` |
| `test_report_by_key_id` | 200, new key != reported key |
| `test_report_unknown_key` | 404, "not found" in detail |
| `test_report_empty_body` | 400, "missing" in detail |
| `test_swap_with_explicit_key` | exit 0, "Key swapped" in stdout |
| `test_swap_updates_auth_file` | `auth.json` contains new `fw_` key, different from reported |
| `test_roundtrip` | API report → key consumed → pool stats reflect change |

## Important Config/Limits

| Setting | Value |
|---------|-------|
| API base URL | `http://localhost:3000/api/v1` (Tauri dashboard) |
| Auth file | `~/.local/share/opencode/auth.json` |
| Pool file | `data/fireworksai-pool.json` |
| Pool backup | `data/fireworksai-pool.json.test_backup` (auto-deleted after restore) |
| Subprocess timeout | 15s per swap_key invocation |

## Known Caveats

- **Consumes real keys during testing** — each `test_report_*` permanently swaps a pool key. The backup fixture restores the file, but if a test crashes mid-run, manual restore is needed.
- **Requires Tauri dashboard running** on port 3000 (not the FastAPI backend on :8000).
- **`auth_backup` fixture is per-test** — each `TestSwapKeyCLI` test gets a fresh auth snapshot.
- **Tauri API may differ from FastAPI** — these tests target the Tauri-bundled API, not the standalone FastAPI.

## Usage

```bash
# All key-swap tests
pytest tests/test_key_swap.py -v

# Single test
pytest tests/test_key_swap.py::TestPoolReport::test_report_by_api_key -v

# If a test crashes mid-run, manually restore:
mv data/fireworksai-pool.json.test_backup data/fireworksai-pool.json
```
