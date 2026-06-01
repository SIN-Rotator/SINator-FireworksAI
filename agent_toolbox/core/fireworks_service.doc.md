# File: `fireworks_service.py`

Fireworks AI account automation — signup, login (with onboarding), API key creation, and account verification. Playwright-first with CUA fallback for React onboarding checkboxes.

## Dependencies

- **Imported by:** `fireworks/signup.py`, `fireworks/login.py`, `fireworks/create_apikey.py`, `fireworks/verify_account.py`, `tools/rotate.py`, `agent_toolbox/api/routes/fireworks.py`, `tools/sinator-cli.py`
- **Imports:** `playwright.async_api`, `asyncio`, `re`, `subprocess`, from `cua_helper`: `find_cua_window`, `cua_get_window_state`

## Key Functions

| Symbol | Purpose |
|--------|---------|
| `signup_fireworks()` | Full signup flow: fill email → Next → 2× password → Create Account. OTP polling is delegated to caller. |
| `login_fireworks()` | Login via Playwright + CUA/Playwright onboarding fallback. Handles name fields, terms, use-cases, submit. |
| `create_api_key()` | Open API Keys page → Create API Key dialog → Generate → Poll for `fw_*` key. Auto-retry on missing-name modal. |
| `verify_account()` | Open a Fireworks verify URL to confirm account. |
| `_fireworks_playwright_onboarding()` | Pure Playwright onboarding fallback (no CUA). |
| `_generate_and_poll_key()` | Core key-generation loop: fill name, wait for Generate enabled, click, poll for key string. |

## Important Config/Limits

- OTP polling: delegated to caller (rotate.py) — 25 attempts × 8s = 200s max
- API key creation: 3 retries, 15s poll per attempt for `fw_` regex match
- API key polling: checks `document.body.innerText` for `fw_[a-zA-Z0-9]{20,}`
- Default key name: `sinator-key`
- Browser modes: reuse existing (`browser=` param), connect via CDP (`cdp_port=`), or launch fresh

## Known Caveats

- `cua_type_text()` fails on React controlled inputs — signs up with non-React field detection
- Onboarding `Continue` / `Submit` buttons may not trigger page redirect — fallback force-navigates to api-keys page
- After CUA Submit, page may be stale — uses fresh page to verify login success
- Missing Name modal triggers automatic retry with `-1`/`-2` suffix
