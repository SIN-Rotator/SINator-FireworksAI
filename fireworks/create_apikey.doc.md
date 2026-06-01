# API Key Generator (`create_apikey.py`)

Generate a new Fireworks AI API key using Playwright. Requires an already logged-in Fireworks session in the running Chrome.

## Dependencies

- **Imported by:** `fireworks/__init__.py`
- **Imports:** `fireworks._lib` (for `run`, `DEFAULT_CDP_PORT`), `agent_toolbox.core.fireworks_service.create_api_key`

## Key Functions

| Symbol | Purpose |
|--------|---------|
| `create_apikey(name="sinator-key", port=9222)` | Navigate to API keys page, click Generate, return `fw_...` key |

## CLI

```bash
python3 -m fireworks.create_apikey --name sinator-key --port 9222
```

## Returns

```json
{"status": "success", "api_key": "fw_...", "error": "..."}
```

## Playwright Flow

1. Navigate to Fireworks API keys page
2. Wait for "Generate" button to become enabled
3. Click Generate, poll DOM for the generated key text
4. Return the key value
