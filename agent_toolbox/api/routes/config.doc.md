# Config Routes (`config.py`)

FastAPI router for reading and writing GMX + Fireworks credentials via `config_manager`.

## Dependencies

- **Imported by:** `agent_toolbox/start_toolbox.py`
- **Imports:** `fastapi.APIRouter`, `pydantic.BaseModel`, `agent_toolbox.core.config_manager`

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/config` | GET | Read current config (GMX email/password, Fireworks password) |
| `/config` | POST | Save updated config |

## Models

| Model | Fields |
|-------|--------|
| `ConfigIn` | `gmx_email`, `gmx_password`, `fireworks_password` |
| `ConfigOut` | `gmx_email`, `gmx_password`, `fireworks_password` |

## Known Caveats

- No authentication — depends on network isolation
- Saves to `data/config.json` via `config_manager`
- POST response may return stale `fireworks_password` if setter is out of sync (line 26 references `cfg.fireworks_password` but saves may not update it)
