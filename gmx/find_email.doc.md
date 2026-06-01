# GMX Email Finder (`find_email.py`)

Find an email by keyword in the GMX inbox and return its verify/confirm URL — Shadow-DOM aware.

## Dependencies

- **Imported by:** `gmx/__init__.py`
- **Imports:** `gmx._lib` (for `run`, `DEFAULT_CDP_PORT`), `playwright.async_api`

## Key Functions

| Symbol | Purpose |
|--------|---------|
| `find_email(keyword, timeout, port)` | Find & open inbox mail by keyword, extract verify URL |

## Important Config/Limits

- Inline JS constants: `_SCAN_JS`, `_CLICK_JS`, `_TEXT_JS` for Shadow-DOM traversal
- `_URL_PATTERN` matches `app.fireworks.ai` confirm/verify URLs
- `_navigate_to_inbox(page)` — "Zum Postfach" click strategy (not direct `goto`)
- `_wait_for_inbox_content(page, max_wait=30)` — polls for `list-mail-item` elements in webmailer frame
- Connects via `playwright.chromium.connect_over_cdp` internally

## Known Caveats

- **Self-contained** — does NOT use `get_service()` or `connect_gmx_page()` from `_lib`; connects its own Playwright instance
- Searches ALL page frames for keyword after frame click
- Falls back to text preview if no URL found in body
- 30s max wait for inbox content to load before giving up
