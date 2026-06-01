# GMX Alias Tool (`gmx_alias_tool.py`)

Interactive CLI tool for GMX alias CRUD operations — wraps `GmxService` methods.
Marked READ-ONLY VERIFIED (do not modify this file; add new services instead).

## Dependencies

- **Imported by:** (standalone CLI)
- **Imports:** `sys`, `asyncio`, `argparse`, `pathlib.Path`, `agent_toolbox.core.gmx_service.GmxService`

## Key Classes/Functions

| Symbol | Purpose |
|--------|---------|
| `print_result(label, result)` | Formats a `GmxService` result dict as coloured/info CLI output |
| `cmd_status()` | Check GMX session + show current alias via `create_alias(None)` |
| `cmd_rotate(alias_name)` | Delete existing alias + create new one (auto-named or custom) |
| `cmd_create(alias_name)` | Create alias only (no deletion) |
| `cmd_delete()` | Delete alias with interactive confirmation |
| `cmd_check()` | Session validation (GMX Homepage → E-Mail → inbox check) |
| `main()` | argparse dispatch: `status`, `check`, `rotate`, `create`, `delete` |

## Important Config/Limits

All operations use CDP port `9222` hardcoded — Chrome must be running on that port.

## Known Caveats

- Browser must be running — use `POST /browser/start` first if using the API alternative.
- GMX FreeMail allows **only one alias** at a time — `rotate` deletes before creating.
