# GMX Routes (`gmx.py`)

FastAPI router for GMX email operations: session management, alias CRUD, inbox access, and OTP reading.

## Dependencies

- **Imported by:** `agent_toolbox/start_toolbox.py` (router inclusion)
- **Imports:** `fastapi.APIRouter`, `httpx`, `agent_toolbox.core.gmx_service`, `agent_toolbox.api.schemas`

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/gmx/session/check` | POST | Check if GMX session is active |
| `/gmx/session/ensure` | POST | Restore session or fresh login via Playwright |
| `/gmx/email-addresses` | POST | Navigate to alias management page |
| `/gmx/alias/delete` | POST | Delete existing alias (API → fallback) |
| `/gmx/alias/rotate` | POST | Atomic delete+create alias (API → fallback) |
| `/gmx/alias/create` | POST | Create new alias (API → fallback) |
| `/gmx/inbox/open` | POST | Open GMX inbox |
| `/gmx/otp/read` | POST | Poll inbox for OTP/verification emails |

## Key Functions

| Symbol | Purpose |
|--------|---------|
| `_call_alias_api()` | HTTP helper to delegate to standalone gmx-alias-tool on port 8001 |
| `_gmx_create_via_api()` | Proxy alias creation to gmx-alias-tool |
| `_gmx_create_fallback()` | Direct GmxService alias creation fallback |
| `_gmx_rotate_via_api_noauth()` | Proxy alias rotation to gmx-alias-tool |
| `_gmx_delete_via_api()` | Proxy alias deletion to gmx-alias-tool |
| `_gmx_delete_fallback()` | Direct GmxService alias deletion fallback |

## Important Config/Limits

- **GMX_CDP_PORT:** `9222` — Chrome DevTools Protocol port
- **GMX_ALIAS_API_URL:** `http://localhost:8001` — standalone alias tool
- All alias operations try gmx-alias-tool first, fall back to direct GmxService CDP calls
- Uses raw CDP websocket (not Playwright page) — Playwright's `page` interface crashes on GMX Navigator SPA

## Known Caveats

- Rotate endpoint has a **Python indentation bug** on lines 40-49 (2-space indent instead of 4-space) which will cause `IndentationError` if the happy path falls through to the gmx-alias-tool response. The API fallback path below is unaffected.
