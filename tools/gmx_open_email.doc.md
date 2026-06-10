# GMX Email Opener (`gmx_open_email.py`)

Standalone tool to find, click, and extract OTP/verify URLs from Fireworks AI emails in GMX.

## Usage

```bash
python3 tools/gmx_open_email.py [--keyword fireworks] [--timeout 120]
```

## Flow

1. Connect to Chrome CDP (port 9222, Profile 73)
2. Find GMX page or navigate to `www.gmx.net` → click "Zum Postfach"
3. Get the `mail` iframe (webmailer.gmx.net)
4. Scan email list via shadow DOM pierce (`browser_eval_in_frame` with `FIND_FIREWORKS_JS`)
5. Click latest Fireworks email via Playwright `frame.locator('list-mail-item').nth(N).click(force=True)`
6. Wait 5s for detail view to load
7. Scan ALL Playwright frames via `browser_scan_frames(VARIFY_URL_RE)` for verify URL
8. Extract `confirmation_code=XXXXXX` from matched text
9. Return structured result with otp_url + otp_code + email content

## Dependencies

- **Imports:** SIN-Browser-Tools (`browser_eval_in_frame`, `browser_scan_frames`)
- **Imported by:** None (standalone CLI tool for testing/debugging)
- **Related:** `agent_toolbox/core/gmx_service.py:read_otp_v2()` — production version of same logic

## Key Constants

- `VERIFY_URL_RE = r'https://app\.fireworks\.ai/signup/confirm\?[^\s"\'<>]+'`
- `OTP_RE = r'confirmation_code=(\d{6})'`
- `FIND_FIREWORKS_JS` — JS function for shadow-DOM piercing in mail-frame

## Known Caveats

- Email body requires 5s delay after click for lazy-loading
- `force=True` required for `click()` due to webmailer-mail-detail overlay
- Only works with User Chrome Profile 73 (simoneschulze) — GMX session cookies
- Primarily a debug/development tool — production uses `gmx_service.read_otp_v2()`
