# BUILDING PLAN — SINator Fireworks AI V11 ✅ (2026-05-25)

## ✅ V11 Status: COMPLETE

```
GMX Login (built-in, Step 0) → Alias Rotation (~63s) → Fireworks Signup
→ OTP → Verify → Login → Onboarding → Playwright Fallback → API Key → Pool
Pool: 112 Keys (60 verfügbar, 44 gesperrt, 8 verbraucht)
Cycle Time: ~210s avg (Strecke: 198-224s)
Pool Proxy V2: :8888 (aiohttp SSE + auto-swap)
Dashboard SSE live
```

| Flow | Name | Status | Tool |
|------|------|:---:|------|
| #0 | GMX Session | ✅ | Playwright "Zum Postfach" click → SID |
| #1 | GMX Alias Delete | ✅ | New-Tab allEmailAddresses URL → hover+click+OK |
| #1 | GMX Alias Create | ✅ | New-Tab allEmailAddresses URL → fill+click, verify empty |
| #2 | Fireworks Signup | ✅ | Playwright + CUA: email→pw→Create→OTP→Verify |
| #3 | Fireworks Login | ✅ | Playwright form `a:has-text("Email Login")` + CUA onboarding |
| #4 | Onboarding | ✅ | CUA: "First"+"Last" type_text + Terms AXPress + Playwright Fallback |
| #5 | Use-Case + $5 | ✅ | CUA dynamic scan text-based checkboxes |
| #6 | API Key | ✅ | PopUpButton force-click + menuitem + Generate (disabled-wait + polling) |
| #7 | Pool | ✅ | Auto-save to keychain (112 keys total) |

## ✅ V11 Changes (2026-05-25)

### Config Manager — GMX + Fireworks Credentials
- `agent_toolbox/core/config_manager.py` — speichert `gmx_email`, `gmx_password`, `fireworks_password` in `data/config.json`
- `agent_toolbox/api/routes/config.py` — `GET /api/v1/config` + `POST /api/v1/config` (public, kein Auth)
- Rotation nutzt `get_config()` → `--gmx-email` + `--gmx-password` + `--password` (nicht mehr hardcodiert!)
- Setup-Seite `/setup` im Dashboard — Formular für alle Credentials

### Pool-Stats: `leased` entfernt
- `available = total - used - suspended` (geleastete Keys zählen als verfügbar)
- Dashboard zeigt: Gesamt / Verfügbar / Verbraucht

### Chat-Assistent (Dashboard /hilfe)
- Rust-Command `chat_send` ruft Pool-Proxy (:8888) auf
- Modell: `accounts/fireworks/models/gpt-oss-120b` ($0.15/M input)
- System-Prompt in `src-tauri/chat-system-prompt.txt` (include_str!)
- Live-Pool-Stats + Backend-Health in Rust geholt → in System-Prompt injiziert

### Pool-Verschlüsselung
- 112/112 API-Keys in macOS Keychain (`com.sinator.pool`)
- `keychain_store.py` mit CRUD + Migration
- `GET /pool/reveal/{key_id}` hydratisiert Key aus Keychain
- Pool-JSON enthält nur SENTINEL-Werte (keine Keys im Klartext)

### CORS + Auth
- `/api/v1/config` in `public_prefixes` (kein Auth-Token nötig)
- CORS Origins: `https://tauri.localhost`, `tauri://localhost`, `http://localhost:3000`, `http://localhost:8000`

---

## ✅ V5-V10 Completed Milestones

| # | Task | Ergebnis |
|---|------|----------|
| 1 | Full-Flow Automation | `rotation.py` V9 — Playwright+CUA+CDP hybrid |
| 2 | API-Key Pool | 112 Keys (60 available), auto-save + Keychain |
| 3 | fireworks_service.py | 3103→114 Zeilen (-96%), V5 Playwright+CUA |
| 4 | V5 Cleanup | Obsolete files gelöscht (preflight.py, command_registry.json, etc.) |
| 5 | Single Command | `python tools/rotate.py` — E2E in einem Befehl |
| 6 | Dynamic CUA Scanning | Text-based `_find_element()` — keine Hardcoded-Indizes |
| 7 | Chrome Config | NON-accessibility mode: `--profile-directory="Profile 901"`, Port 9222 |
| 8 | V7 Self-Healing | Rate-Limit Backoff, OOPIF Polling, API Key Retry |
| 9 | V8 GMX Nav Fix | Playwright inbox goto + CUA Einstellungen + JS hidden-nav + New-Tab iframe |
| 10 | V9 Sleep-Reduktion + Bugfixes | health mark_used(), Dashboard override, PoolManager reload |
| 11 | V10 CUA PID Targeting | lsof PID-Ermittlung, target_pid an find_cua_window |
| 12 | V11 Config Manager + Chat + Keychain | Credentials API, Rust chat_send, Keychain encryption |

---

## 📌 PROJECT COMPLETE — Maintenance Mode

**Keine neuen Features mehr.** V11 = letzte geplante Version.
Ab jetzt nur noch:

| Aktivität | Beschreibung |
|-----------|-------------|
| 🐛 Bugfixes | Wenn was im Live-Betrieb kaputt geht |
| 🔄 Live Runs | `python tools/rotate.py` — Keys generieren |
| 📝 AGENTS.md | Learnings aus Live-Runs dokumentieren |

**Status:** Feature-Complete ✅ — 112 Keys, ~210s/Rotation, Config Manager, Keychain, Chat-Assistent.

---

## 📌 Known Issue: Account Suspension

Fireworks suspendiert Accounts bei Spending Limit ($5 Credits aufgebraucht):
```
Account golden-cobra-560-66c is suspended, possibly due to reaching the monthly
spending limit or failure to pay past invoices.
```
**Workaround:** Key via `POST /pool/report` als suspended markieren → neuen Key holen.

---

## 🚀 Quick Start (V11)

```bash
# Chrome mit Profile 901 (OHNE accessibility!)
nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="/Users/jeremy/Library/Application Support/Google Chrome" \
  --profile-directory="Profile 901" \
  --remote-debugging-port=9222 \
  --no-first-run --no-default-browser-check \
  > /tmp/chrome_sinator.log 2>&1 &

# CUA Daemon
cua-driver serve &

# Full Rotation (Single Command — liest Config aus data/config.json)
python tools/rotate.py

# API Server
python agent_toolbox/start_toolbox.py

# Pool Stats
curl -s http://localhost:8000/pool/stats | python3 -m json.tool

# Config setzen (GMX + FW Credentials)
curl -X POST http://localhost:8000/api/v1/config \
  -H 'Content-Type: application/json' \
  -d '{"gmx_email":"opensin@gmx.de","gmx_password":"ZOE.jerry2024","fireworks_password":"ZOE.jerry2024!"}'
```

---

## 🏗️ Services (LaunchAgents)

| Service | Port | Beschreibung |
|---------|------|-------------|
| `com.sinator.backend` | :8000 | FastAPI Backend |
| `com.sinator.pool-proxy` | :8888 | aiohttp SSE + auto-swap Proxy |
| `com.sinator.tunnel` | — | Cloudflare Named Tunnel (`sinator.delqhi.com`) |
| `com.sinator.pages` | :8040 | Landing Page |
| `com.sinator.chrome` | :9222 | Chrome mit Profile 901 |
| `com.sinator.cua-driver` | — | CUA AX-Daemon |

### Tunnel-Routing
- `/` → `:8040` (Landing Page)
- `/inference/v1/*`, `/v1/*` → `:8888` (Pool-Proxy)
- `/api/*`, `/docs` → `:8000` (Backend)
