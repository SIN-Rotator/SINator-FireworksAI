# GMX Alias Creation (`create_alias.py`)

Create a new GMX alias address.

## Dependencies

- **Imported by:** `gmx/__init__.py`, `gmx/rotate_alias.py`
- **Imports:** `gmx._lib` (for `get_credentials`, `get_service`, `run`, `DEFAULT_CDP_PORT`)

## Key Functions

| Symbol | Purpose |
|--------|---------|
| `create_alias(name, email, password, port)` | Create an alias; random name if `name` is `None` |

## Important Config/Limits

- Credentials fall back to project config when not provided
- Alias name should not include `@gmx.de`
- Random names generated if `name` is `None`

## Known Caveats

- GMX FreeMail allows only **one** alias — must delete existing alias first (use `rotate_alias` or `delete_alias`)
- Requires active GMX session
