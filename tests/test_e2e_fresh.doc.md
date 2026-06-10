# E2E Fresh Tests (`test_e2e_fresh.py`)

End-to-end regression tests for the full rotation flow (GMX alias rotation + Fireworks signup + onboarding + API key). **DESTRUCTIVE** — creates real Fireworks accounts.

## Dependencies

- **Imported by:** (test runner only)
- **Imports:** `pytest`, `pytest_asyncio`, `playwright.async_api`
- **External state:** Chrome with CDP port 9222 (User Chrome Profile 73)
- **External state:** Valid GMX session, valid Fireworks account for sign-in
- **Requires:** All conftest fixtures (`chrome_ok`, `browser`, `cua_ok`, `cua_window`)

## ⚠️ Destructive Tests

```python
destructive = pytest.mark.destructive
```

These tests interact with real GMX and Fireworks accounts. They will:
- Create new Fireworks accounts
- Consume real email aliases
- Generate real API keys
- Leave the pool with new keys added

**DO NOT** run on production systems without explicit intent.

## Test Classes

| Class | Tests | Purpose |
|-------|-------|---------|
| `TestE2ESession` | multiple | Verify Chrome has GMX/Fireworks session, prerequisites for rotation |
| (destructive) | multiple | Run full rotation end-to-end (GMX delete + create + FW signup + onboarding + API key) |

## Why CUA tests are NOT here

GMX alias operations (`rotate_alias`, delete/create) depend on **CUA (Computer Use API) + macOS AX**, which are unreliable in Playwright's test-driven Chromium. They are NOT tested via pytest.

**Test GMX alias ops manually**:
```bash
python3 tools/rotate.py
```

## Important Config/Limits

| Setting | Value |
|---------|-------|
| Destructive marker | `pytest.mark.destructive` |
| Skip destructive | `pytest tests/ -v -m "not destructive"` |
| Per-test timeout | None (rotation takes ~160s) |
| Chrome CDP port | 9222 (via conftest fixture) |

## Known Caveats

- **Cannot fully test GMX alias rotation in pytest** — relies on cua-driver + macOS Accessibility APIs that don't work in headless test runners.
- **Destructive tests modify external systems** — running them on a real GMX/Fireworks account will consume resources and create new accounts.
- **Session-dependent** — if GMX session is dead, all tests will time out.

## Usage

```bash
# Session checks only (safe)
pytest tests/test_e2e_fresh.py::TestE2ESession -v

# Skip destructive tests
pytest tests/ -v -m "not destructive"

# Full E2E (WARNING: real accounts)
pytest tests/test_e2e_fresh.py -v

# Manual full rotation (recommended)
python3 tools/rotate.py
```
