# test_otp_mailcheck.py — OTP via MailCheck Extension + CDP OOPIF Test

## Purpose
Test script for OTP extraction via the GMX MailCheck Chrome extension (`chrome-extension://camnampocfohlcgbajligmemmabnljcm`) using CDP OOPIF (Out-Of-Process Iframe) attachment to read email bodies from `mailbody-ui.de`.

Restored from commit `7ce418a` (2026-05-21) — the working approach before the frame-tools refactor.

## Dependencies
- **Imports:** `cdp_client.CDPClient`, `playwright.async_api`
- **Requires:** Chrome CDP on port 9222 with active GMX session + MailCheck extension installed
- **Extension URL:** `chrome-extension://camnampocfohlcgbajligmemmabnljcm/pages/mail-panel.html`

## Flow
1. Connect to Chrome via CDP
2. Open MailCheck extension popup
3. Find Fireworks verification email by scanning email subjects
4. Click the email → GMX opens a new tab with the email content
5. Find the `mailbody-ui.de` OOPIF among new CDP targets
6. Attach to the OOPIF via CDP `Target.attachToTarget`
7. Extract email body text via `Runtime.evaluate`
8. Regex-search for Fireworks verify URLs

## Usage
```bash
python tools/test_otp_mailcheck.py
```

## Known Caveats
- MailCheck extension must be installed in Profile 73
- OOPIF detection relies on URL containing `mailbody-ui.de` — fragile if GMX changes iframe provider
- CDP direct attachment bypasses Playwright's frame tree (OOPIFs are invisible to Playwright)
- Port 9222 hardcoded — must match the running Chrome instance
