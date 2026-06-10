# Shared Helpers (`_lib.py`)

Internal utilities shared by all `fireworks` tools — ensures repo-importability, password resolution, and CLI entry-point boilerplate.

## Dependencies

- **Imported by:** `fireworks.signup`, `fireworks.login`, `fireworks.create_apikey`, `fireworks.verify_account`
- **Imports:** `sys`, `json`, `asyncio`, `argparse`, `pathlib.Path`, `typing`

## Key Functions

| Symbol | Purpose |
|--------|---------|
| `get_password(password=None)` | Resolve FW password from arg or project config |
| `run(action, *, description, add_args, ok_statuses)` | CLI wrapper: parse args, run coroutine, print JSON, exit 0/1 |

## Constants

| Name | Value |
|------|-------|
| `DEFAULT_CDP_PORT` | `9222` |
| `_OK_STATUSES` | `{"success", "ok", "verified"}` |

## Contract

Every tool in this package:
- exposes ONE async function returning `Dict[str, Any]` with a `"status"` field
- is runnable from CLI: `python3 -m fireworks.<tool>`
- attaches to a running Chrome via CDP (default port 9222)
- delegates to `agent_toolbox.core.fireworks_service` for the actual browser logic
