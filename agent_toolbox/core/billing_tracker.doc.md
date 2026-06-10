# File: `billing_tracker.py`

Fireworks billing page scraper. Checks remaining credits for an API key by navigating to `app.fireworks.ai/account/billing` and parsing the dollar amount from the page body.

## Dependencies

- **Imported by:** (not imported by any file — standalone utility)
- **Imports:** `re`, `json`, `time`, `logging`, from `cdp_client`: `CDPClient`, `get_browser_ws_endpoint`, and `playwright.async_api`

## Key Functions

| Symbol | Purpose |
|--------|---------|
| `check_key_credits_via_cdp()` | Navigate to billing page via existing CDP browser, extract `$XX.XX` credits via regex |
| `check_key_credits_via_playwright()` | Same logic but uses `chromium.launch()` (Playwright) |

## Important Config/Limits

- CDP port: 9222 (hardcoded)
- Regex patterns detect: `$X.XX credits`, `credits $X.XX`, `$X.XX / $6`
- Wait time: 5s after page load for client-side rendering

## Known Caveats

- Requires being logged into Fireworks — redirects to login if not authenticated
- Regex-based parsing is fragile — depends on page rendering format
- CDP version attaches to the first available page target, may interfere with other tabs
- No retry logic — single attempt, fails fast
