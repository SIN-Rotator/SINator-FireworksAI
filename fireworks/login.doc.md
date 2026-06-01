# Fireworks Login (`login.py`)

Log in to Fireworks AI with email/password. Handles first-login onboarding (name, use-case checkboxes) via CUA or Playwright fallback.

## Dependencies

- **Imported by:** `fireworks/__init__.py`
- **Imports:** `fireworks._lib` (for `get_password`, `run`, `DEFAULT_CDP_PORT`), `agent_toolbox.core.fireworks_service.login_fireworks`

## Key Functions

| Symbol | Purpose |
|--------|---------|
| `login(email, password=None, port=9222)` | Log in, complete onboarding if presented |

## CLI

```bash
python3 -m fireworks.login --email acc@gmx.de --password secret --port 9222
```

## Returns

```json
{"status": "success", "steps_completed": [...], "error": "..."}
```

## Playwright / CUA Flow

1. Navigate to `app.fireworks.ai/auth/login`
2. Fill email, click Next
3. Fill password, click Sign In
4. If onboarding appears, fill "First" + "Last" name fields, select use-case checkboxes
5. Skip any optional survey steps
