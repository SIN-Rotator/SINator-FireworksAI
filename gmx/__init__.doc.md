# GMX Package (`__init__.py`)

Re-exports all single-purpose GMX tools as composable async functions.

## Dependencies

- **Imported by:** `from gmx import check_session, login, ...`
- **Imports:** Each tool module individually (`gmx.check_session`, `gmx.login`, etc.)

## Key Exports

| Symbol | Purpose |
|--------|---------|
| `check_session()` | Check active GMX session |
| `login()` | Log into GMX |
| `open_inbox()` | Open the inbox |
| `create_alias()` | Create a new alias |
| `delete_alias()` | Delete current alias |
| `rotate_alias()` | Delete + create in one pass |
| `read_otp()` | Poll inbox for verify URL / OTP |
| `find_email()` | Find & open a mail, return its verify URL |

## Known Caveats

- Each tool attaches to an **already running** Chrome (CDP, port 9222). No tools launch their own browser.
- All return JSON-serialisable dicts with `"status"` field.
