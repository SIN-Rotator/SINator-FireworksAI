# Rotation Tool (`rotate.py`)

Main orchestrator for GMX alias rotation + Fireworks AI account registration + API key generation.

## Usage

```bash
python3 tools/rotate.py [--gmx-email E] [--gmx-password P] [--password P] [alias-name]
```

## Flow (V8.2 Multi-Tab Architecture)

1. **Start Chrome** or connect to existing CDP port
2. **`initialize_architecture()`** → creates `work_tab` + dedicated `inbox_tab`
3. **GMX Login** via work_tab (if not already logged in)
4. **`GmxService.rotate_alias()`** → delete old alias → create new alias
5. **`FireworksService.signup_fireworks()`** → register with new alias
6. **`GmxService.read_otp_v2()`** → poll inbox_tab for Fireworks verify email
7. **`FireworksService.verify_account()`** → open confirm URL
8. **`FireworksService.login_fireworks()`** → complete onboarding
9. **`FireworksService.create_api_key()`** → generate and persist
10. **`PoolManager.add_key()`** → save to pool JSON

## Dependencies

- **Imports:** `agent_toolbox.core.gmx_service.GmxService`, `agent_toolbox.core.fireworks_service.FireworksService`, `agent_toolbox.core.pool_manager.PoolManager`
- **Called by:** `tools/batch_rotate.py`, manual CLI invocations
- **Imported by:** None (standalone CLI tool)

## Key Architecture Decisions

- **Two tabs**: `work_tab` for active work (login, alias, Fireworks) + `inbox_tab` permanently parked at GMX inbox for OTP polling. This prevents session poisoning.
- **No CDP in rotate.py**: All operations via Playwright service calls. CDP only used inside `read_otp_via_playwright()` fallback.
- **OTP via `read_otp_v2()`**: Uses `browser_scan_frames` + `browser_eval_in_frame` from SIN-Browser-Tools (V18.2)

## Config

- Read from `data/config.json` (GMX email/password, Fireworks password)
- API keys saved to `data/fireworksai-pool.json`
- Pool endpoint: `sinatorpool-router.delqhi.com:9998`

## Known Caveats

- `_goto_postfach()` is required before any GMX inbox navigation — do NOT use `page.goto("navigator.gmx.net/mail")`
- OTP can take up to 180s (Fireworks sends email with delay)
- Unverified accounts get `partial` status — login may still work
- After rotation, all non-essential Chrome tabs are closed (only Dashboard + 1 GMX inbox remain)
