# BUILDING PLAN — SINator Fireworks AI v5 (2026-05-21)

## ✅ COMPLETE FLOW VERIFIED

```
GMX Rotation (19.8s) → Fireworks Signup → GMX Email Verify → Login
→ Onboarding (CUA) → Use-Case + $5 → API Key: fw_8d1PLFjvQMdgJFzjDZSTRx
```

| Flow | Name | Status | Tool |
|------|------|:---:|------|
| #0 | GMX Session | ✅ | Cookie-based, "E-Mail" click for SID |
| #1 | GMX Alias Delete | ✅ | Playwright iframe hover+click + CUA OK |
| #1 | GMX Alias Create | ✅ | Playwright iframe fill+click, verify empty input |
| #2 | Fireworks Signup | ✅ | Playwright `input[name="email"]` + CUA type_text |
| #3 | GMX OTP Email | ✅ | MailCheck Extension + CDP OOPIF |
| #4 | Fireworks Login | ✅ | `/login` → "Email Login" → `input[name="email"]` |
| #5 | Onboarding | ✅ | CUA: names type_text + Terms AXPress + Continue |
| #6 | Use-Case + $5 | ✅ | CUA: checkboxes + Submit |
| #7 | API Key | ✅ | `/settings/users/api-keys` → PopUpButton → menuitem → Generate |

## 🔴 TODO — was noch fehlt

### PRIO 1: Full-Flow Automation (1-2 Tage)
**Datei:** `agent_toolbox/api/routes/rotation.py`
**Problem:** Ruft noch altes `fireworks_service.py` (CDP, 155KB, broken)
**Fix:** Ersetzen durch Playwright+CUA Flow:
```python
# 1. GMX Rotation (Playwright iframe)
alias = rotate_alias_via_playwright()
# 2. Fireworks Signup (Playwright + CUA)
signup_fireworks(alias)
# 3. GMX OTP read (Extension + CDP OOPIF)
verify_url = read_otp_from_gmx("fireworks")
# 4. Confirm + Login (Playwright)
login_fireworks(alias, password)
# 5. Onboarding + $5 (CUA)
onboarding_via_cua()
# 6. API Key (Playwright)
api_key = create_api_key()
```

### PRIO 2: API-Key Pool aktivieren (1 Tag)
**Datei:** `agent_toolbox/core/pool_manager.py` ✅
**Status:** Bereits implementiert + getestet. Pool hat 2 Keys.
- `fw_8d1PLFjvQMdgJFzjDZSTRx` → super-cheetah-687 (2026-05-21)
- `fw_4SyZoeCFsyn5L4hpT63LGV` → blaze-scorpion-746 (used)
- Rotation.py speichert Keys automatisch via `pool.add_key()`

### PRIO 3: fireworks_service.py ersetzen (1-2 Tage)
**Datei:** `agent_toolbox/core/fireworks_service.py` (155KB, 3103 Zeilen)
**Problem:** 100% CDP-basiert, komplett veraltet
**Fix:** Neuschreiben als dünner Wrapper um Playwright+CUA-Flows

### PRIO 4: Cleanup (1 Tag)
- [ ] `cookie_manager.py` — Legacy, durch CDP Cookie-Handling ersetzen
- [ ] `browser_manager.py` — Vereinfachen (Playwright managed Browser jetzt)
- [ ] `decrypt_cookies.py` — ✅ Bereits gelöscht
- [ ] `preflight.py` — ✅ Bereits gelöscht
- [ ] `verify_hashes.py` — ✅ Bereits gelöscht

### PRIO 5: Single Command (1 Tag)
```bash
python tools/rotate.py  # → GMX Alias + FW Signup + API Key in einem Lauf
```

## ✅ Bereits erledigt

- [x] GMX Alias Rotation 3/3, 19.8s
- [x] Fireworks Signup + Login
- [x] Onboarding (Names + Terms + Use-Cases)
- [x] API Key Creation
- [x] Alle .md Dateien dokumentiert
- [x] Obsolete v3 Dateien gelöscht
- [x] Knowledge Base aktuell
