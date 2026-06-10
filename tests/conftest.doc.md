# Shared pytest fixtures (`conftest.py`)

Provides session-scoped and function-scoped fixtures for the SINator integration test suite. All test files in `tests/` automatically import this via pytest discovery.

## Dependencies

- **Imported by:** All test files in `tests/` (automatic via pytest)
- **Imports:** `pytest`, `pytest_asyncio`, `subprocess`, `asyncio`, `logging`, `pathlib`
- **External:** `playwright.async_api`, `cua_helper` (lazy-imported in fixtures)
- **Requires:** Chrome with CDP port 9222, cua-driver daemon (for some tests)

## Fixtures Provided

| Fixture | Scope | Purpose |
|---------|-------|---------|
| `chrome_ok` | session | Skips test if Chrome CDP not reachable on :9222 |
| `cua_ok` | session | Skips test if cua-driver not running |
| `browser` | function | Connect to running Chrome via `connect_over_cdp(":9222")` |
| `gmx_page` | function | Return a page on `www.gmx.net` (reuse existing GMX tab if open) |
| `cua_window` | function | Find first on-screen Chrome window via cua-driver, return `(pid, wid)` |
| `fireworks_page` | function | Return a fresh page on `app.fireworks.ai/login` (closes existing FW tabs) |

## Important Config/Limits

| Setting | Value |
|---------|-------|
| Chrome CDP port | 9222 (hardcoded in `_chrome_available()`) |
| cua-driver check | `cua-driver status` (5s timeout) |
| Default navigation | `https://www.gmx.net/` for `gmx_page`, `https://app.fireworks.ai/login` for `fireworks_page` |
| Pre-navigation sleep | 2-4s (lets SPA hydrate before test runs) |

## Known Caveats

- **`connect_over_cdp` reuses the user's Chrome** — this means tests share state with the operator's browsing. DO NOT run tests while the user is actively navigating.
- **`cua_window` and `fireworks_page` use `page.close()`** — only safe on the Bot Chrome, not the User Chrome.
- **GMX session is required for most tests** — if the user's GMX session is dead, the test will time out trying to navigate. Use the Session Recovery protocol from AGENTS.md.
- **`gmx_page` may pick up a different page** than expected if multiple GMX tabs are open (uses `gmx in url.lower()` as heuristic).

## Usage

```bash
# All tests (requires Chrome + cua-driver)
pytest tests/ -v

# Specific test file
pytest tests/test_gmx_session.py -v

# Skip cua-dependent tests
pytest tests/ -v --deselect tests/test_cua_helper.py
```

## See Also

- `agent_toolbox/core/cua_helper.py` — window detection used by `cua_window` fixture
- `AGENTS.md` — Chrome Profile 73 + cua-driver setup prerequisites
