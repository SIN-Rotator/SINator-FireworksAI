# Account Verification (`verify_account.py`)

Open a Fireworks account verify/confirm URL in the running Chrome browser to activate a newly registered account.

## Dependencies

- **Imported by:** `fireworks/__init__.py`
- **Imports:** `fireworks._lib` (for `run`, `DEFAULT_CDP_PORT`), `agent_toolbox.core.fireworks_service.verify_account`

## Key Functions

| Symbol | Purpose |
|--------|---------|
| `verify_account(url, port=9222)` | Navigate to the confirmation URL to activate the account |

## CLI

```bash
python3 -m fireworks.verify_account --url "https://app.fireworks.ai/signup/confirm?..." --port 9222
```

## Returns

```json
{"status": "verified"|"error", "verify_url": "...", "error": "..."}
```

## Playwright Flow

1. Navigate browser tab to the given verify/confirm URL
2. Wait for redirect/confirmation
3. Return `verified` status on success
