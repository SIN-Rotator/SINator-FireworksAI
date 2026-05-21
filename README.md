# SINator-FireworksAI — Agent Toolbox

**Purpose:** Automated GMX email alias rotation → Fireworks AI account registration → API key pool management.

**Architektur:** CUA Driver (Navigation + Dialog) + Playwright (Form Interaction) + CDP (Session/Cookies).

## ✅ VERIFIED FLOW (2026-05-21)

`neon-hawk-042@gmx.de` erfolgreich erstellt. Hier die exakten Commands:

### Alias löschen (Playwright im Iframe + CUA OK)
```python
# 1. Mouseover existierende Alias-Email → Delete Icon erscheint
frame.locator('text=laramiuex@gmx.de').first.hover()

# 2. Delete Icon klicken (force=True weil nur nach hover sichtbar)
frame.locator('[title*="löschen"]').first.click()

# 3. CUA click OK im Bestätigungsdialog
#    Vorher: cua-driver call get_window_state um OK element_index zu finden
cua-driver call click '{"pid": 12465, "window_id": 244, "element_index": 1033}'
```

### Alias erstellen (Playwright im Iframe)
```python
# 1. Input füllen (iframe => mail_settings -> allEmailAddresses)
frame.locator('input[type="text"]').first.fill("neon-hawk-042")

# 2. Hinzufügen Button klicken (force=True für Wicket)
frame.locator('button:has-text("Hinzufügen")').first.click(force=True)

# 3. Verify: Input muss LEER sein nach Submit (= Erfolg)
await inp.input_value()  # → '' = erfolgreich erstellt!
```

### Session auffrischen (nur bei Session-Expiry nötig)
```python
# Klick auf "E-Mail" Link auf www.gmx.net → leitet zu Inbox mit frischem SID
gmx_page.get_by_role("link", name="E-Mail", exact=True).first.click()

# Oder via CUA:
cua-driver call click '{"pid": 12465, "window_id": 244, "element_index": 29}'
```

---

```bash
cd agent_toolbox
pip install -r requirements.txt
python3 start_toolbox.py
```

Server starts on `http://localhost:8000` — Swagger UI at `/docs`.

---

## ⚠️ WICHTIG: CUA Driver primär, CDP nur als Fallback

**CUA kann ALLES anklicken. Du musst nur fähig genug sein!**

```
✅ CUA click     → Buttons, Links, Checkboxes, MenuItems, PopUpButtons
✅ CUA type_text → Normale Inputs (NICHT React controlled!)
✅ CUA set_value → PopUpButton Menus nach click
✅ CUA get_window_state → AX-Tree scannen für Elemente
```

**CDP NUR für:**
- React controlled inputs (CUA type_text funktioniert NICHT!)
- Target management (neue Tabs)
- GMX Extension Email-Zugriff

---

## API Endpoints

### Browser Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/browser/start` | Start Chrome with Profile 901 |
| POST | `/browser/stop` | Stop Chrome (SIGTERM) |
| GET | `/browser/status` | Get browser status |

### GMX Services

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/gmx/session/check` | Check GMX session active |
| POST | `/gmx/session/ensure` | **Flow 0** — Login or recover GMX session |
| POST | `/gmx/email-addresses` | Navigate to alias settings page |
| POST | `/gmx/alias/delete` | Delete existing alias |
| POST | `/gmx/alias/create` | Create new alias |
| POST | `/gmx/alias/rotate` | **ATOMIC** — delete + create in one call |
| POST | `/gmx/inbox/open` | Open GMX inbox |

### Fireworks AI

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/fireworks/register` | Register new Fireworks account |
| POST | `/fireworks/confirm` | Confirm account via OTP URL |
| POST | `/fireworks/apikey` | Create API key |

### Pool Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/pool/stats` | Get pool statistics |
| GET | `/pool/key` | Get available API key |
| POST | `/pool/key/use` | Mark key as used |
| POST | `/pool/add` | Add key to pool |

### Rotation (HAUPT)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/rotation/full` | Complete rotation: GMX Alias → Fireworks → API Key |

---

## Core Endpoints Detail

### `POST /rotation/full` — Complete Account Rotation

**Atomically rotates GMX alias → Fireworks registration → API key extraction.**

```bash
curl -X POST http://localhost:8000/rotation/full \
  -H "Content-Type: application/json" \
  -d '{"fireworks_password": "YourPassword123!"}'
```

**Flow 0 (Session):** GMX Session prüfen → Login via Shadow DOM wenn nötig

**Flow 1 (GMX Alias):** Delete existing alias → Create new alias (`{adj}-{noun}-{3digits}@gmx.de`)

**Flow 2 (Fireworks):** Navigate to /signup → Cookie Banner dismiss (CUA) → Email (CDP nativeInputValueSetter) → Password (CDP) → Create Account (CUA)

**Flow 3 (OTP):** GMX Extension öffnen → Email finden → OTP URL klicken

**Flow 4 (Setup):** FirstName/LastName (CUA) → Terms checkbox (CUA) → Continue → 2x Checkboxes (CUA) → Submit for $5 Credits

**Flow 5 (API Key):** Settings → Users & Access → API Keys → Create API Key → Name eingeben (CDP) → Generate Key (CUA)

**Response:**
```json
{
  "status": "success",
  "gmx_alias": "blaze-scorpion-746@gmx.de",
  "fireworks_account": "blaze-scorpion-746@gmx.de",
  "api_key": "fw_4SyZoeCFsyn5L4hpT63LGV",
  "api_key_name": "blaze-scorpion-746",
  "steps_completed": ["session_active", "gmx_alias_rotated", "fw_registered", "fw_otp_received", "fw_setup_complete", "api_key_created"],
  "steps_failed": [],
  "execution_time": "~300s"
}
```

### `POST /gmx/alias/rotate`

**Atomically rotates GMX alias — delete existing + create new in one call.**

```bash
curl -X POST http://localhost:8000/gmx/alias/rotate \
  -H "Content-Type: application/json" \
  -d '{"new_alias_name": "turbo-mantis"}'
```

---

## Chrome Configuration (IMMUTABLE)

```
Chrome Binary:     /Applications/Google Chrome.app/Contents/MacOS/Google Chrome
User Data Dir:     /Users/jeremy/Library/Application Support/Google Chrome
Profile:           Profile 901 ("SINator (Fireworks AI)")
CDP Port:          9222
```

**Chrome Start:**
```bash
kill $(ps aux | grep "[c]hrome.*user-data-dir" | awk '{print $2}' | head -1)
nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="/Users/jeremy/Library/Application Support/Google Chrome" \
  --profile-directory="Profile 901" \
  --remote-debugging-port=9222 \
  --no-first-run --no-default-browser-check \
  > /tmp/chrome_sinator.log 2>&1 &
sleep 6 && curl -s http://127.0.0.1:9222/json/version
```

**⚠️ NIEMALS `--force-renderer-accessibility` verwenden!**
- MIT Flag: GMX zeigt "Barrierefreies Postfach" (Email-Rows NICHT klickbar!)
- OHNE Flag: GMX funktioniert normal + CUA-Driver AX-Tree funktioniert trotzdem

---

## GMX Extension für Email (EINZIG ERLAUBTER WEG)

```
Extension ID: camnampocfohlcgbajligmemmabnljcm
Popup: chrome-extension://camnampocfohlcgbajligmemmabnljcm/pages/mail-panel.html
Email IDs: 18 Ziffern (z.B. 1778454231729833464)
```

**VERBOTEN:**
```
❌ lightmailer-bs.gmx.net URLs (HTTP 500 errors!)
❌ webmailer.gmx.net direkt navigieren
```

---

## CUA Driver Usage

### Window finden:
```bash
cua-driver call list_windows '{"query": "Chrome"}'
```

### AX-Tree scannen:
```bash
echo '{"pid": 12345, "window_id": 67890}' | cua-driver call get_window_state
```

### Element klicken:
```bash
echo '{"pid": 12345, "window_id": 67890, "element_index": 42}' | cua-driver call click
```

### PopUpButton Menü:
```bash
# Nach "This is a popup/select button" Warning:
echo '{"pid": 12345, "window_id": 67890, "element_index": 74, "value": "Create API Key"}' | cua-driver call set_value
```

### Text eingeben (NICHT React!):
```bash
echo '{"pid": 12345, "window_id": 67890, "element_index": 42}' | cua-driver call type_text '{"text": "mein-text"}'
```

---

## API Key Pool

**Pool Format:** Plain list (JSON array)
```json
[
  {
    "id": "bs746-20260511001",
    "api_key": "fw_4SyZoeCFsyn5L4hpT63LGV",
    "alias_email": "blaze-scorpion-746@gmx.de",
    "key_name": "blaze-scorpion-746",
    "created_at": "2026-05-11T00:00:00Z",
    "used": false,
    "used_at": null
  }
]
```

**PoolManager API:**
- `add_key(api_key, alias_email, key_name)` → {status, key_id}
- `get_available_key()` → {api_key, alias_email, ...} oder None
- `mark_used(key_id)` → True/False
- `get_stats()` → {total, used, available, keys: [...]}

---

## Status

- ✅ Chrome startup with Profile 901 (Original, keine Kopie!)
- ✅ CUA Driver für alle interaktiven Elemente
- ✅ **Flow 0:** GMX session ensure / login recovery via Shadow DOM
- ✅ GMX email-addresses page navigation
- ✅ GMX alias deletion
- ✅ GMX alias creation
- ✅ GMX alias rotation (atomic delete+create)
- ✅ GMX Extension für Email-Zugriff
- ✅ Fireworks AI registration + OTP
- ✅ API key pool management
- ✅ Fireworks API Key Erstellung (CDP für React Inputs!)
- ✅ Full pipeline: `POST /rotation/full`

---

## Environment Variables

```bash
GMX_EMAIL=opensin@gmx.de
GMX_PASSWORD=ZOE.jerry2024
FIREWORKS_PASSWORD=YourPassword123!
CDP_PORT=9222
```

---

## Command Registry

Siehe: `agent_toolbox/command_registry.json`

Enthält alle Commands mit Pre-Flight Check Anweisungen und Learnings.

---

*Letzte Aktualisierung: 2026-05-11*