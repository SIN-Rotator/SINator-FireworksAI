# GMX Shared Library (`_lib.py`)

Shared helpers and CLI wrapper for all GMX tools.

## Dependencies

- **Imported by:** All `gmx.*` tool modules
- **Imports:** `agent_toolbox.core.gmx_service.GmxService`, `agent_toolbox.core.config_manager.get_config`

## Key Functions

| Symbol | Purpose |
|--------|---------|
| `get_service()` | Return a fresh `GmxService` instance |
| `get_credentials()` | Resolve GMX email/password, fall back to config |
| `connect_gmx_page(port)` | Connect to running Chrome via CDP, return a GMX-inbox `Page` |
| `run(action, description, ...)` | Standard CLI entry point: parse args, run coroutine, print JSON, exit with code |

## Important Config/Limits

- Default CDP port: `9222`
- Success statuses: `success`, `logged_in`, `found`, `no_alias`, `ok`, `verified`
- Exit code 0 on success status, 1 otherwise

## Known Caveats

- `run()` calls `sys.exit()` — not suitable for interactive use.
- `connect_gmx_page()` prefers tabs with `allEmailAddresses` in URL, then any valid `gmx.net` tab.
