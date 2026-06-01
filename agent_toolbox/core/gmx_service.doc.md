# GMX Service (`gmx_service.py`)

Playwright-native GMX Service für Alias-Rotation und OTP-Extraktion im SINator Fireworks AI Rotator.

## Dependencies

- **Imported by:** `agent_toolbox/api/routes/gmx.py`, `tools/rotate.py`, `tools/gmx_open_email.py`
- **Imports:** `agent_toolbox/core/cdp_client.py` (CDP fallback), Playwright async API
- **Depends on:** User Chrome Profile 73 (simoneschulze) via Playwright connect_over_cdp

## Key Methods

| Section | Method | Purpose |
|---|---|---|
| **Multi-Tab** | `initialize_architecture()` | Creates `work_tab` + `inbox_tab` in same browser context |
| **Multi-Tab** | `navigate_inbox()` | Keeps inbox_tab pinned at GMX Posteingang |
| **Connection** | `_pw_connect()` | Playwright-Page aus CDP, SID-Tab-Priorisierung |
| **Login** | `_login()` | GMX Login via Form (email+password) |
| **Navigation** | `_navigate_to_all_email_addresses()` | Zum E-Mail-Adressen-Settings-Bereich |
| **Alias Delete** | `_delete_alias()` | Löscht existierenden Alias via Playwright iframe |
| **Alias Create** | `_create_alias()` | Erstellt neuen Alias via Playwright iframe |
| **Rotation** | `rotate_alias()` | Kombiniert delete + create + verify |
| **Legacy OTP** | `read_otp_cdp_axtree()` | CDP-basierte OTP-Suche (deprecated) |
| **Playwright OTP** | `read_otp_via_playwright()` | Playwright-native OTP-Suche (V14, falls V2 versagt) |
| **V2 OTP** | `read_otp_v2()` | Browser_scan_frames + browser_eval_in_frame (V18.2, bevorzugt) |
| **Session** | `check_session()` | Prüft ob GMX Session noch aktiv |
| **Helpers** | `open_email_addresses()` | Navigiert zu E-Mail Settings |
| **Legacy** | `_inject_cookies()` | Cookie-Injection via CDP (deprecated, nicht mehr verwendet) |
| **Singleton** | `get_gmx_service()` | Module-level Singleton |

## GMX Shadow DOM Structure

```
page → iframe#mail (webmailer.gmx.net)
  → mail-list-container > shadowRoot
    → list-mail-list > shadowRoot
      → list-mail-item (50 Stück) ← EMAIL LISTE
    → webmailer-mail-detail > shadowRoot
      → detail-body > iframe.detail-body--full-height ← separate Playwright Frame
```

## OTP Extraction Strategy (V18.2 — `read_otp_v2()`)

1. **Check inbox_tab** for existing GMX mail list
2. **`browser_eval_in_frame(frame_name="mail")`** — shadow-piercing JS scan for Fireworks emails
3. **`mail_frame.locator('list-mail-item').nth(N).click(force=True)`** — click via Playwright locator
4. **`browser_scan_frames(regex=...)`** — scan ALL unnamed about:blank frames for verify URL
5. Return `{"status":"success", "otp_url": "..."}`

Fallback: `read_otp_via_playwright()` (legacy, falls CDP nicht verfügbar)

## Important Constants

- `GMX_HOME_URL = "https://www.gmx.net/"` — **NIEMALS direkt `navigator.gmx.net/mail` navigieren** (verliert SID)
- Alias-Format: `{adjektiv}-{substantiv}-{NNN}` (32×32 Adj/Noun Pool)
- OTP Polling: max 25×8s = 200s für read_otp_cdp_axtree, 15×6s für read_otp_via_playwright

## Known Caveats

- `force=True` required for `locator().click()` — webmailer-mail-detail overlay intercepts pointer events
- Email body lives in **separate unnamed Playwright frame** (about:blank) — NOT in the mail frame
- `goto(navigator.gmx.net/mail)` redirects to `www.gmx.net` without SID — use "Zum Postfach" strategy
- GMX FreeMail: only ONE alias at a time (delete before create)
