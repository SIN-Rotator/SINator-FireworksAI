# Test GMX Session (`test_gmx_session.py`)

Tests for GMX session access via the E-Mail link click flow. Verifies that the SPA hash routing establishes a valid session (cookie-based, not URL-based).

## Dependencies

- **Imported by:** (test runner only)
- **Imports:** `pytest`, `pytest_asyncio`, `playwright.async_api`
- **External state:** Chrome with CDP port 9222
- **External state:** Valid GMX session (User Chrome Profile 73)
- **Requires:** `chrome_ok`, `browser`, `gmx_page` fixtures from `conftest.py`

## Test Methods

| Test | Verifies |
|------|----------|
| `test_email_click_returns_sid` | Clicking "E-Mail" on `www.gmx.net` → SPA hash URL, session cookie set |
| `test_gmx_inbox_accessible` | After click, page body contains GMX mailbox content |
| `test_gmx_alias_page_navigable` | Cookies contain a GMX session token (`sid` or `session` in name) |

## Why SID is not in the URL

GMX uses **SPA hash routing** — the URL becomes `www.gmx.net/mail/#...` instead of `?sid=...`. The session lives in cookies, not the URL. This test verifies cookie presence, not URL pattern.

## Important Config/Limits

| Setting | Value |
|---------|-------|
| E-Mail link selector | `a:has-text("E-Mail")` (Playwright text selector) |
| Click timeout | 5s |
| Post-click sleep | 5s (lets SPA hydrate) |
| Session cookie detection | `name contains "sid" or "session"` |

## Known Caveats

- **SPA-dependent** — test passes only if the SPA fully loads. Slow networks or partial loads will fail with `Body too short` assertion.
- **Session may expire between runs** — if the user's GMX session is dead, the test will fail. Use AGENTS.md's Session Recovery protocol.
- **Cookie format may change** — GMX occasionally renames session cookies. The detection heuristic (`sid` or `session` substring) is intentionally permissive.

## Usage

```bash
# All GMX session tests
pytest tests/test_gmx_session.py -v

# Single test
pytest tests/test_gmx_session.py::TestGMXSession::test_email_click_returns_sid -v

# Quick smoke test
pytest tests/test_gmx_session.py::TestGMXSession::test_gmx_alias_page_navigable -v
```

## See Also

- `agent_toolbox/core/gmx_service.py` — production GMX session handling
- `AGENTS.md` — GMX session recovery protocol
- `tests/conftest.py` — `gmx_page` fixture used by all tests here
