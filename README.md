# SINator — Fireworks AI Account Rotator

Automated GMX email alias rotation → Fireworks AI account registration → API key pool management.

**Stack:** Playwright + CUA Driver (macOS AX) + CDP Websocket  
**Architecture:** CUA for navigation & React checkboxes, Playwright for form interaction, CDP for session/cookies/OTP

---

## Quick Start

```bash
# 1. Chrome starten (Profile 901, OHNE --force-renderer-accessibility!)
nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="/Users/jeremy/Library/Application Support/Google Chrome" \
  --profile-directory="Profile 901" \
  --remote-debugging-port=9222 \
  --no-first-run --no-default-browser-check \
  > /tmp/chrome_sinator.log 2>&1 &
sleep 6

# 2. CUA Daemon starten (--no-relaunch!)
cua-driver serve --no-relaunch &

# 3. Full Rotation (Single Command)
python tools/rotate.py

# 4. Oder: API Server starten
python agent_toolbox/start_toolbox.py
# → http://localhost:8000/docs (Swagger UI)
```

---

## E2E Flow (V9 — ~173s)

```
Step 0:  GMX Login via Playwright                      → frische Cookies
Step 1:  GMX Alias Rotation (CUA+Playwright)            → cosmic-raven-683@gmx.de
Step 2:  Fireworks Signup (Playwright + CDP)            → Account created
Step 3:  OTP Polling (GMX MailCheck Extension + CDP)    → Verify URL extracted
Step 4:  Verify + Login + Onboarding (CUA+Playwright)   → Dashboard reached
Step 5:  API Key Creation (Playwright PopUpButton)      → fw_G93EigYuyQnbeCfNiSCZwy
Step 6:  Save to Pool                                   → 30 keys total

**Pool:** 45 API Keys (45 available, 0 used)
**Cycle Time:** ~173s (nach V9 sleep-Reduktion)

---

## API Reference

All endpoints are prefixed with `/api/v1` unless noted.

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Service info + version |
| GET | `/health` | Detailed health check (browser, gmx-alias-tool) |

```bash
curl http://localhost:8000/health
```

### Browser Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/browser/start` | Start Chrome with Profile 901 |
| POST | `/api/v1/browser/stop` | Stop Chrome (SIGTERM) |
| GET | `/api/v1/browser/status` | Browser status + page count |

```bash
curl -X POST http://localhost:8000/api/v1/browser/start \
  -H 'Content-Type: application/json' \
  -d '{"profile_name":"Profile 901","cdp_port":9222}'

curl -X POST http://localhost:8000/api/v1/browser/stop

curl http://localhost:8000/api/v1/browser/status
```

### GMX Services

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/gmx/session/check` | Check if GMX session is active |
| POST | `/api/v1/gmx/session/ensure` | **Flow 0** — Login or recover session |
| POST | `/api/v1/gmx/email-addresses` | Navigate to alias settings page |
| POST | `/api/v1/gmx/alias/delete` | Delete existing alias |
| POST | `/api/v1/gmx/alias/rotate` | **ATOMIC** — delete + create |
| POST | `/api/v1/gmx/alias/create` | Create new alias |
| POST | `/api/v1/gmx/inbox/open` | Open GMX inbox |
| POST | `/api/v1/gmx/otp/read` | Poll OTP email from GMX inbox |

```bash
# Session prüfen
curl -X POST http://localhost:8000/api/v1/gmx/session/check

# Session wiederherstellen
curl -X POST http://localhost:8000/api/v1/gmx/session/ensure \
  -H 'Content-Type: application/json' \
  -d '{"email":"opensin@gmx.de","password":"ZOE.jerry2024"}'

# Alias rotieren (V8: Playwright inbox + CUA + new-tab iframe)
curl -X POST http://localhost:8000/api/v1/gmx/alias/rotate \
  -H 'Content-Type: application/json' \
  -d '{"new_alias_name":"swift-fox"}'

# OTP aus Inbox lesen
curl -X POST http://localhost:8000/api/v1/gmx/otp/read \
  -H 'Content-Type: application/json' \
  -d '{"sender_filter":"fireworks","max_retries":18}'
```

### Fireworks AI

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/fireworks/login` | Login + CUA onboarding |
| POST | `/api/v1/fireworks/apikey` | Create API key (PopUpButton) |

```bash
# Login
curl -X POST http://localhost:8000/api/v1/fireworks/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"swift-fox-123@gmx.de","password":"ZOE.jerry2024!"}'

# API Key erstellen
curl -X POST http://localhost:8000/api/v1/fireworks/apikey \
  -H 'Content-Type: application/json' \
  -d '{"key_name":"swift-key"}'
```

### Cookie Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/cookies/extract` | Extract cookies from browser |
| POST | `/api/v1/cookies/inject` | Inject cookies into browser |

```bash
# GMX Cookies extrahieren
curl -X POST http://localhost:8000/api/v1/cookies/extract \
  -H 'Content-Type: application/json' \
  -d '{"domain_filter":"gmx","save_to_file":true}'

# Cookies injizieren
curl -X POST http://localhost:8000/api/v1/cookies/inject \
  -H 'Content-Type: application/json' \
  -d '{"filename":"gmx-cookies.json","verify_session":true}'
```

### API Key Pool

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/pool/stats` | Pool statistics |
| POST | `/api/v1/pool/add` | Add key to pool |
| POST | `/api/v1/pool/use` | Mark key as used |
| DELETE | `/api/v1/pool/{key_id}` | Remove key from pool |

```bash
# Pool-Status
curl http://localhost:8000/api/v1/pool/stats

# Key hinzufügen
curl -X POST http://localhost:8000/api/v1/pool/add \
  -H 'Content-Type: application/json' \
  -d '{"api_key":"fw_xxx","alias_email":"swift-fox@gmx.de","key_name":"swift"}'

# Key als verwendet markieren
curl -X POST http://localhost:8000/api/v1/pool/use?key_id=sf-20260522-001

# Key löschen
curl -X DELETE http://localhost:8000/api/v1/pool/sf-20260522-001
```

### Rotation (Haupt-Endpoint)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/rotation/full` | Complete rotation: GMX → Fireworks → API Key |

```bash
curl -X POST http://localhost:8000/api/v1/rotation/full \
  -H 'Content-Type: application/json' \
  -d '{"new_alias_name":"swift-hawk","fireworks_password":"ZOE.jerry2024!","save_to_pool":true}'
```

**Response:**
```json
{
  "status": "success",
  "gmx_alias": "swift-hawk-842@gmx.de",
  "fireworks_account": "swift-hawk-842@gmx.de",
  "api_key": "fw_4SyZoeCFsyn5L4hpT63LGV",
  "api_key_name": "swift",
  "steps_completed": [
    "gmx_alias_rotated",
    "fireworks_login",
    "api_key_created",
    "api_key_saved_to_pool"
  ],
  "steps_failed": [],
  "execution_time": "~173s"
}
```

---

## Chrome Configuration (IMMUTABLE)

```
Chrome Binary:     /Applications/Google Chrome.app/Contents/MacOS/Google Chrome
User Data Dir:     /Users/jeremy/Library/Application Support/Google Chrome
Profile:           Profile 901
CDP Port:          9222
```

**⚠️ NIEMALS `--force-renderer-accessibility` verwenden!**  
MIT Flag → GMX zeigt "Barrierefreies Postfach" (Email-Rows nicht klickbar).  
OHNE Flag → GMX funktioniert normal + CUA AX-Tree funktioniert trotzdem.

**⚠️ NIEMALS `pkill -9 -f "Google Chrome"`!** Killt User-Chrome → Session tot.  
Nur SIGTERM: `kill $(ps aux | grep "[c]hrome.*user-data-dir" | awk '{print $2}' | head -1)`

---

## CUA Driver Usage

```bash
# Window finden
cua-driver call list_windows '{"query": "Chrome"}'

# AX-Tree scannen
echo '{"pid": 12345, "window_id": 67890}' | cua-driver call get_window_state

# Element klicken
echo '{"pid": 12345, "window_id": 67890, "element_index": 42}' | cua-driver call click

# Text eingeben (NICHT für React controlled inputs!)
echo '{"pid": 12345, "window_id": 67890}' | cua-driver call type_text '{"text": "mein-text"}'

# PopUpButton (z.B. "Create API Key")
# 1. Click auf PopUpButton → Menu erscheint
# 2. SCAN → MenuItems finden
# 3. MenuItem klicken
```

**Wichtig:** CUA kann alles anklicken (Buttons, Checkboxes, MenuItems, PopUpButtons).  
CDP `NativeInputValueSetter` NUR für React controlled inputs (Fireworks Signup-Formular).

---

## API Key Pool

**Format:** Plain JSON array in `data/fireworksai-pool.json`

```json
[
  {
    "id": "3d4eeb2e",
    "api_key": "fw_xxxx...",
    "alias_email": "alias-123@gmx.de",
    "key_name": "pulse",
    "created_at": "2026-05-22T17:00:00Z",
    "used": false,
    "used_at": null
  }
]
```

**PoolManager API:**
- `add_key(api_key, alias_email, key_name)` → `{status, key_id}`
- `get_available_key()` → key dict or None
- `mark_used(key_id)` → True/False
- `get_stats()` → `{total, used, available, keys}`
- `delete_key(key_id)` → True/False

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GMX_EMAIL` | `opensin@gmx.de` | GMX login email |
| `GMX_PASSWORD` | `ZOE.jerry2024` | GMX login password |
| `FIREWORKS_PASSWORD` | `ZOE.jerry2024!` | Password for new FW accounts |
| `CDP_PORT` | `9222` | Chrome remote debugging port |
| `TOOLBOX_PORT` | `8000` | API server port |
| `TOOLBOX_HOST` | `0.0.0.0` | API server bind address |
| `TOOLBOX_RELOAD` | `false` | Auto-reload on file changes |

---

## Tools

| Script | Description |
|--------|-------------|
| `python tools/rotate.py` | Full E2E rotation in one command |
| `python tools/gmx_alias_tool.py status` | Check GMX session status |
| `python tools/gmx_alias_tool.py rotate` | Standalone GMX alias rotation |

---

## Status

| Feature | Status |
|---------|:------:|
| Chrome startup with Profile 901 | ✅ |
| CUA Driver for navigation & dialogs | ✅ |
| GMX session ensure / login recovery | ✅ |
| GMX alias deletion (iframe Playwright + CUA) | ✅ |
| GMX alias creation (Playwright iframe) | ✅ |
| GMX alias rotation (atomic delete+create) | ✅ |
| GMX MailCheck Extension for OTP emails | ✅ |
| Fireworks AI signup + verify (Playwright+CDP) | ✅ |
| Fireworks AI login + onboarding (CUA+Playwright) | ✅ |
| API key creation (PopUpButton + DOM polling) | ✅ |
| API key pool management | ✅ |
| Full pipeline: `POST /rotation/full` | ✅ |
| Rate-limit circuit breaker (exponential backoff) | ✅ |
| OOPIF polling (zuverlässiges OTP-Finden) | ✅ |
| API Key "Missing Name" auto-retry | ✅ |
| V8 GMX Nav Fix: Playwright inbox + CUA + JS hidden-nav + New-Tab iframe | ✅ |
| V9 Cleanup: 10 dead methods removed, sleep-Reduktion 209s→173s | ✅ |
| V9 Bugfix: Health-Check mark_used() removed (zerstörte 7 Keys) | ✅ |
| V9 Bugfix: Dashboard /pool/health override entfernt | ✅ |
| V9 Bugfix: purge_gmx_cookies löscht nicht mehr Master-Backup | ✅ |
| V9 Bugfix: PoolManager reload() vor jeder public Methode | ✅ |

---

*V9 — 2026-05-23 | 45 API Keys | ~173s per rotation*
