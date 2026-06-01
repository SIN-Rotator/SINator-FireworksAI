# GMX Alias Rotation (`rotate_alias.py`)

Atomically delete the old GMX alias and create a new one in a single pass.

## Dependencies

- **Imported by:** `gmx/__init__.py`
- **Imports:** `gmx._lib` (for `get_credentials`, `get_service`, `run`, `DEFAULT_CDP_PORT`)

## Key Functions

| Symbol | Purpose |
|--------|---------|
| `rotate_alias(name, email, password, port)` | Delete current alias + create new one; returns both old and new addresses |

## Important Config/Limits

- Delegates to `GmxService.rotate_alias()` (production rotator logic)
- Random name generated if `name` is `None`
- Credentials fall back to project config

## Known Caveats

- Requires active GMX session
- GMX FreeMail allows only one alias, so rotation is delete-then-create (not parallel)
