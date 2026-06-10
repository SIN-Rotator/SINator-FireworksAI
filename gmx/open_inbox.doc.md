# GMX Inbox Opener (`open_inbox.py`)

Open the GMX inbox and verify the session is active.

## Dependencies

- **Imported by:** `gmx/__init__.py`
- **Imports:** `gmx._lib` (for `connect_gmx_page`, `run`, `DEFAULT_CDP_PORT`)

## Key Functions

| Symbol | Purpose |
|--------|---------|
| `open_inbox(port)` | Navigate GMX tab to inbox; confirms logged-in state |

## Important Config/Limits

- **"Zum Postfach" strategy** — goes to `www.gmx.net`, clicks "Zum Postfach", never uses `goto(navigator.gmx.net/mail)` directly
- Returns `not_logged_in` for `status=inactive`, `session-expired`, or `logoutlounge` URLs

## Known Caveats

- Does NOT trigger a login flow — only navigates an existing session
- Checks body text for "Sie sind eingeloggt" or "Zum Postfach" to confirm session
- 4s initial wait, 6s wait after Postfach click
