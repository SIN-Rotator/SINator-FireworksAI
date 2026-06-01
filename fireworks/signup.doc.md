# Fireworks Signup (`signup.py`)

Register a new Fireworks AI account using a GMX alias email. Fills the signup form, then polls GMX for the verification email and opens the verify URL.

## Dependencies

- **Imported by:** `fireworks/__init__.py`
- **Imports:** `fireworks._lib` (for `get_password`, `run`, `DEFAULT_CDP_PORT`), `agent_toolbox.core.fireworks_service.signup_fireworks`

## Key Functions

| Symbol | Purpose |
|--------|---------|
| `signup(email, password=None, port=9222)` | Sign up new account, poll GMX for verify email, open verify URL |

## CLI

```bash
python3 -m fireworks.signup --email new-account@gmx.de --password secret --port 9222
```

## Returns

```json
{"status": "success"|"partial"|"error", "verify_url": "...", "steps_completed": [...], "error": "..."}
```

## Playwright Flow

1. Navigate to `app.fireworks.ai/auth/signup`
2. Fill email, password, click Sign Up
3. Poll GMX for Fireworks verification email (25×8s = 200s max)
4. Extract verify URL from email body
5. Open verify URL to confirm the account
