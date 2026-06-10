# File: `cdp_client.py`

Raw Chrome DevTools Protocol (CDP) client via WebSocket. Provides low-level browser automation without Playwright/Puppeteer — only `websockets` + `asyncio`.

## Dependencies

- **Imported by:** `agent_toolbox/core/gmx_service.py`, `agent_toolbox/core/billing_tracker.py`, `tests/test_e2e_fresh.py`, `tools/test_otp_mailcheck.py`
- **Imports:** `websockets`, `asyncio`, `json`, `base64`, `urllib.request`

## Key Classes/Functions

| Symbol | Purpose |
|--------|---------|
| `OopifContext` | Dataclass holding OOPIF (cross-origin iframe) position/session info |
| `CDPClient` | Raw CDP WebSocket client — send commands, receive events, manage sessions |
| `get_browser_ws_endpoint()` | Get Chrome DevTools WebSocket URL from a CDP port (default 9222) |
| `get_page_target()` | Find best matching page target (prefers non-auth, non-empty pages) |

## Important Config/Limits

- Default CDP port: `9222`
- Default timeout: `30s` for commands, `10s` for evaluate, `15s` for browser WS discovery
- `OopifContext.to_top()` / `OopifContext.contains()` — coordinate translation for cross-origin iframes
- `send_to_session()` — sends commands to a specific CDP session (tab/iframe)
- `attach_to_target()` / `attach_to_iframe()` — create CDP sessions for targets

## Known Caveats

- Requires Chrome already running with `--remote-debugging-port=9222`
- No built-in reconnection logic — `connect()` must be called again after disconnect
- DOM helpers (`query_selector`, `get_box_model`) rely on CDP DOM domain being enabled
- `get_iframe_viewport_box()` may return wrong coordinates if iframe is not fully rendered
