# GMX Login (`login.py`)

Log in to GMX via the two-step form (email → Weiter → password → Login).

## Dependencies

- **Imported by:** `gmx/__init__.py`
- **Imports:** `gmx._lib` (for `connect_gmx_page`, `get_credentials`, `get_service`, `run`, `DEFAULT_CDP_PORT`)

## Key Functions

| Symbol | Purpose |
|--------|---------|
| `login(email, password, port)` | Log into GMX; idempotent — skips if already logged in |

## Important Config/Limits

- Idempotent: checks session state before attempting login
- Uses `get_credentials()` to resolve email/password from args or config
- Sleeps 3 seconds after login for session to stabilise

## Known Caveats

- Returns `not_logged_in` if `_login()` returns `True` but `check_session()` disagrees
- Does not handle CAPTCHA — requires a profile with established session cookies
