# config_manager.py — Runtime Configuration

## Purpose
Stores and retrieves SINator runtime configuration: GMX credentials, Fireworks password. Persists to `data/config.json`.

## Dependencies
- **Imports from:** Nothing (standalone)
- **Imported by:** `tools/rotate.py`, `agent_toolbox/api/routes/config.py`
- **Reads/Writes:** `data/config.json`

## Config Priority
1. Environment variables (`GMX_EMAIL`, `GMX_PASSWORD`, `FIREWORKS_PASSWORD`)
2. `data/config.json` file
3. Empty string (no config)

## API
- `GET /api/v1/config` — Returns current config (passwords masked)
- `POST /api/v1/config` — Updates config fields

## Security
- Passwords stored in plaintext JSON (not Keychain) — acceptable for local-only service
- API endpoint is public (no auth required) — intentional for dashboard setup page
