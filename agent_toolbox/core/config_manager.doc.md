# File: `config_manager.py`

Stores SINator runtime configuration (GMX + Fireworks credentials) as a singleton loaded from/saved to `data/config.json`.

## Dependencies

- **Imported by:** `tools/rotate.py`, `gmx/_lib.py`, `fireworks/_lib.py`, `tools/batch_rotate.py`, `agent_toolbox/api/routes/rotation.py`, `agent_toolbox/api/routes/gmx.py`, `agent_toolbox/api/routes/config.py`
- **Imports:** `json`, `pathlib`, `logging`

## Key Classes/Functions

| Symbol | Purpose |
|--------|---------|
| `Config` | Singleton holding `gmx_email`, `gmx_password`, `fireworks_password` with JSON persistence |
| `get_config()` | Returns the global Config singleton (lazy-init) |

## Important Config/Limits

- Config file: `data/config.json`
- Default credentials (fallback): `delqhi@gmx.de` / `ZOE.jerry2024` / `ZOE.jerry2024!`
- Saved on every `save()` call — no auto-save on attribute change

## Known Caveats

- Hardcoded default credentials in source — should be overridden via API or env
- No locking — concurrent writes may race
