# Swap Key (`swap_key.py`)

Reports a bad Fireworks API key to the pool and replaces it in OpenCode's
`auth.json` — no session restart needed.

## Dependencies

- **Imported by:** (standalone CLI)
- **Imports:** `json`, `sys`, `urllib.request`, `pathlib.Path`

## Key Classes/Functions

| Symbol | Purpose |
|--------|---------|
| `api(path, data)` | Generic HTTP helper for `POST`/`GET` to `localhost:8100/api/v1` |
| `get_current_key()` | Reads `~/.local/share/opencode/auth.json` → returns `fireworks` field |
| `swap_key(bad_key)` | POST `/pool/report` to swap key, then writes new key into OpenCode auth.json |

## Important Config/Limits

| Path | Value |
|------|-------|
| `AUTH_FILE` | `~/.local/share/opencode/auth.json` |
| `SINATOR_API` | `http://localhost:8100/api/v1` |

## Known Caveats

- Requires the SINator backend to be running on port 8100.
- If no available keys remain in the pool, the swap fails with a message to run rotation.
- Designed for the `accounts/fireworks/models/deepseek-v4-pro` model specifically.
