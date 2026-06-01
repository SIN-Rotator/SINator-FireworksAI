---
name: sinator-gmx-flow
description: GMX Alias Rotation, OTP Extraction, Session Recovery — Profile 73 via CDP 9222. Kein Login-Flow, nur Cookie-basierte Session.
license: MIT
---

# SINator GMX Flow

## Chrome Profile (ABSOLUTE TRUTH — NIEMALS ÄNDERN)
| Parameter | Wert |
|-----------|------|
| User Data Dir | `/Users/simoneschulze/Library/Application Support/Google Chrome` |
| Profile | `Profile 73` |
| CDP Port | `9222` |
| Binary | `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` |

## Chrome Start
```bash
pkill -9 -f "Google Chrome" 2>/dev/null; sleep 2
nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="/Users/simoneschulze/Library/Application Support/Google Chrome" \
  --profile-directory="Profile 73" \
  --remote-debugging-port=9222 \
  --no-first-run --no-default-browser-check \
  > /tmp/chrome_sinator.log 2>&1 &
sleep 5
curl -s http://127.0.0.1:9222/json/version
```
**NIEMALS** `/Users/jeremy/...` Pfade, **NIEMALS** `/tmp/` Profile, **NIEMALS** Chrome ohne `--profile-directory="Profile 73"`.

## Session Recovery
1. **Validieren**: GMX Homepage → "E-Mail" click → URL `navigator.gmx.net/mail?sid=...`
2. **Wenn TOT**: Cookies nicht speichern, Browser killen, `data/gmx-cookies.json` löschen, Master-Backup aus `backup/session/gmx-cookies-master.json` kopieren, Chrome neu starten
3. **Wenn OK**: Cookies extrahieren → `data/gmx-cookies.json` + Backup

## Alias Rotation
1. `navigator.gmx.net/mail_settings/email_addresses`
2. Existierenden Alias löschen (Hover → löschen → OK)
3. Neuen Alias erstellen: `{adjektiv}-{substantiv}-{zahl}@gmx.de`
4. Verifizieren dass Alias in der Liste erscheint

## OTP Extraction
- Frame-aware scan via `GmxService.read_otp_main_frame_only(sender_keyword="fireworks", timeout=80)`
- OOPIF fallback via `cdp_client.CDPClient` (MailCheck Extension)
- Confirm-URL extrahieren: `https://app.fireworks.ai/signup/confirm?client_id=...`

## Referenzen
- `agent_toolbox/core/gmx_service.py` — GMX Service (Alias, OTP, Session Recovery)
- `backup/session/gmx-cookies-master.json` — Goldener Session-Backup (chmod 444)
- `AGENTS.md` — Session Recovery Protokoll
