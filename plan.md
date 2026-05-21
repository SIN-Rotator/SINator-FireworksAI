# BUILDING PLAN — SINator Fireworks AI V5 ✅ (2026-05-21)

## ✅ Status: COMPLETE FLOW VERIFIED

```
GMX Rotation (19.8s) → Fireworks Login → Onboarding → API Key: fw_8d1PLFjvQMdgJFzjDZSTRx
```

| Flow | Name | Status | Tool |
|------|------|:---:|------|
| #0 | GMX Session | ✅ | CUA "E-Mail" click → SID |
| #1 | GMX Alias Delete | ✅ | Playwright iframe hover+click + CUA OK |
| #1 | GMX Alias Create | ✅ | Playwright iframe fill+click, verify empty |
| #2 | Fireworks Login | ✅ | Playwright form `input[name="email"]` |
| #3 | Onboarding | ✅ | CUA: names type_text + Terms AXPress |
| #4 | Use-Case + $5 | ✅ | CUA: checkboxes + Submit |
| #5 | API Key | ✅ | PopUpButton + menuitem + Generate |
| #6 | Pool | ✅ | 2 Keys gespeichert |

## ✅ Alle 5 Prioritäten erledigt

| # | Task | Ergebnis |
|---|------|----------|
| 1 | Full-Flow Automation | `rotation.py` V5 — Playwright+CUA |
| 2 | API-Key Pool | 2 Keys, auto-save |
| 3 | fireworks_service.py | 3103→114 Zeilen (-96%) |
| 4 | Cleanup | 4 files + 1 dir gelöscht, 4 Schemas entfernt |
| 5 | Single Command | `python tools/rotate.py` |

## 🔴 TODO — Phase 2

### 1. OTP Email Reader automatisieren
**Was:** Verify-URL aus GMX MailCheck Extension extrahieren
**Status:** Manuell bewiesen (CDP OOPIF → mailbody-ui.de)
**Code:** Noch nicht in `gmx_service.py` integriert

### 2. Fireworks Signup (neuer Account)
**Was:** Create Account Flow: Signup-Form → OTP Email → Verify → Login
**Status:** Existierender Account Login funktioniert
**Fehlt:** Signup-Form mit 2x Passwort + Create Account Button + OTP Polling

### 3. Full E2E mit neuem Alias
**Was:** GMX Rotation → Fireworks Signup → OTP → Verify → Login → API Key
**Status:** Rotation + Login + API Key funktioniert einzeln
**Fehlt:** Orchestrierung in einem durchgehenden Lauf

### 4. gmx-alias-tool API updaten
**Was:** Standalone API auf Playwright umbauen
**Status:** Läuft noch mit altem CDP-Code (server.py)
**Repo:** `/Users/jeremy/dev/gmx-alias-tool`

## 📂 Cleanup erledigt
- [x] `decrypt_cookies.py` gelöscht
- [x] `preflight.py` gelöscht
- [x] `verify_hashes.py` gelöscht
- [x] `protection/gmx_hashes.json` gelöscht
- [x] `command_registry.json` gelöscht
- [x] 4 obsolete Fireworks Schemas entfernt
- [x] `fireworks_service.py` 3103→114 Zeilen

## 📚 Dokumentation
- [x] AGENTS.md — V5 Login + Onboarding + API Key
- [x] README.md — Complete Flow + Code Snippets
- [x] plans/knowledge-base.md — All Learnings
- [x] banned.md — Neue Patterns
- [x] plan.md — Diese Datei
- [x] sinrules.md — Updated Rules
- [x] gmx-alias-tool/README.md — Updated

## 🚀 Quick Start

```bash
# Chrome mit Debug-Port
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 --no-first-run &

# CUA Daemon
cua-driver serve &

# Full Rotation (Single Command)
python tools/rotate.py

# API Server
python agent_toolbox/start_toolbox.py
curl -X POST http://localhost:8000/rotation/full \
  -H 'Content-Type: application/json' \
  -d '{"fireworks_password": "ZOE.jerry2024!"}'
```
