# Fireworks Routes (`fireworks.py`)

FastAPI router for Fireworks AI account operations: login and API key creation.

## Dependencies

- **Imported by:** `agent_toolbox/start_toolbox.py`
- **Imports:** `fastapi.APIRouter`, `agent_toolbox.core.fireworks_service`, `agent_toolbox.api.schemas`

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/fireworks/login` | POST | Login to Fireworks AI (Playwright + CUA onboarding) |
| `/fireworks/apikey` | POST | Create a new Fireworks API key |

## Key Functions

| Symbol | Purpose |
|--------|---------|
| `_require_browser()` | Returns CDP port for chromium.launch() |
| `login()` | Thin wrapper around `fireworks_service.login_fireworks()` |
| `apikey()` | Thin wrapper around `fireworks_service.create_api_key()` |

## Important Config/Limits

- CDP port hardcoded to `9222`
- Delegates all logic to `agent_toolbox.core.fireworks_service`

## Known Caveats

- Minimal routing layer — no retry, no fallback, no complex error handling
