# GMX Alias Deletion (`delete_alias.py`)

Delete the existing GMX alias, if any.

## Dependencies

- **Imported by:** `gmx/__init__.py`, `gmx/rotate_alias.py`
- **Imports:** `gmx._lib` (for `connect_gmx_page`, `get_credentials`, `run`, `DEFAULT_CDP_PORT`)

## Key Functions

| Symbol | Purpose |
|--------|---------|
| `delete_alias(email, password, port)` | Delete current alias; returns `no_alias` if none exists |

## Important Config/Limits

- Uses `connect_gmx_page()` for page connection rather than bare `get_service()`
- Verifies deletion via `_verify_alias()` after a 2-second wait

## Known Caveats

- Returns `no_alias` status, not an error, when no alias exists
- Credentials passed through call chain for `_navigate_to_all_email_addresses()`
