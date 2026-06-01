# GMX Session Check (`check_session.py`)

Check whether the running Chrome has a logged-in GMX session.

## Dependencies

- **Imported by:** `gmx/__init__.py`, other tools that need session pre-check
- **Imports:** `gmx._lib` (for `get_service`, `run`, `DEFAULT_CDP_PORT`)

## Key Functions

| Symbol | Purpose |
|--------|---------|
| `check_session(port)` | Returns `logged_in`, `not_logged_in`, or `error` status |

## Important Config/Limits

- Delegates to `GmxService.check_session()`
- Returns `current_url` for debugging session redirects (e.g. `status=inactive`)

## Known Caveats

- Does not attempt to log in — reports session state only.
