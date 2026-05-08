# 📋 AGENTS.md — SINator Fireworks AI Rotator

## ⚠️ IMMUTABLE SYSTEM CONFIGURATION — NEVER DEVIATE

### Chrome Profile (ABSOLUTE TRUTH)
- **User Data Dir:** `/Users/simoneschulze/Library/Application Support/Google Chrome`
- **Active Profile:** `Profile 73`
- **Profile Owner:** simoneschulze (NOT jeremy!)
- **CDP Port:** `9222`
- **Chrome Binary:** `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`

### Chrome Start Command (COPY EXACTLY)
```bash
pkill -9 -f "Google Chrome" 2>/dev/null; sleep 2

nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="/Users/simoneschulze/Library/Application Support/Google Chrome" \
  --profile-directory="Profile 73" \
  --remote-debugging-port=9222 \
  --no-first-run \
  --no-default-browser-check \
  > /tmp/chrome_sinator.log 2>&1 &

sleep 5
curl -s http://127.0.0.1:9222/json/version
```

**NEVER:**
- Use `/Users/jeremy/...` paths (wrong user!)
- Create temp copies of the profile
- Use `--user-data-dir=/tmp/...` (loses session cookies)
- Start Chrome without `--profile-directory="Profile 73"`

---

## 🔄 SESSION RECOVERY & BACKUP-PROTOKOLL

### Warum?
Wenn Chrome neu gestartet wird oder Cookies ablaufen, ist die GMX Session tot.
Der Agent darf **NIEMALS** abgelaufene Cookies über funktionierende überschreiben.

### Backup-Struktur
```
backup/
└── session/
    ├── gmx-cookies-master.json     ← Goldener Master (READ-ONLY! chmod 444)
    ├── gmx-cookies-current.json    ← Aktueller Zustand (vor/nach Operation)
    └── last-known-good/            ← Kopie vor jeder Rotation
```

### Protokoll (REIHENFOLGE EINHALTEN)
1. **VOR jeder Operation:** Session validieren (GMX Homepage → "E-Mail" click → prüfen ob `navigator.gmx.net/mail?sid=...`)
2. **Wenn Session TOT:**
   - ❌ NICHTS speichern/extrahieren
   - 🛑 Browser SOFORT beenden (`pkill -9 -f "Google Chrome"`)
   - 🧹 `./data/gmx-cookies.json` LÖSCHEN (enthält abgelaufene Cookies)
   - 📦 Backup aus `backup/session/gmx-cookies-master.json` nach `./data/gmx-cookies.json` kopieren
   - 🔄 Chrome mit restored Cookies neu starten
3. **NACH erfolgreicher Operation:**
   - Cookies extrahieren → `./data/gmx-cookies.json` + `backup/session/gmx-cookies-current.json`
   - Wenn Session bestätigt funktioniert → zusätzlich nach `backup/session/gmx-cookies-master.json` kopieren (nur wenn besser als vorher)

### Session Validierung (Code-Pattern)
```python
async def _validate_gmx_session(client, session_id):
    # 1. Navigate zu GMX Homepage
    await client.navigate(session_id, "https://www.gmx.net/")
    await asyncio.sleep(3)
    # 2. Click "E-Mail"
    await client.click_at(session_id, x=302, y=44)
    await asyncio.sleep(5)
    # 3. Prüfe URL
    url = await client.evaluate(session_id, "window.location.href")
    return "navigator.gmx.net/mail?sid=" in url
```

### Master-Backup anlegen (einmalig)
1. Chrome mit Profile 73 starten (siehe oben)
2. Manuell bei GMX einloggen (oder funktionierende Cookies injizieren)
3. Cookies extrahieren via CDP: `Network.getAllCookies`
4. Nach `backup/session/gmx-cookies-master.json` speichern
5. Datei als READ-ONLY markieren: `chmod 444 backup/session/gmx-cookies-master.json`

---

## Projekt-Übersicht
**Zweck:** Automatisierte Erstellung von GMX E-Mail-Aliasen → Fireworks AI Account-Registrierung → API-Key-Pool-Rotation.

**Architektur:** Python + Raw CDP Websocket (Playwright ersetzt durch CDPClient wegen GMX SPA frame detachment crashes)

---

## 📁 Aktuelle Projekt-Struktur

```
SINator-fireworksai/
├── AGENTS.md              ← Diese Datei (ARCHITEKTUR & SYSTEM-KONFIGURATION)
├── banned.md              ← Verbotene Methoden & Patterns
├── debug/                 ← Temporäre Debug-Skripte (nur zur Entwicklung)
│   ├── debug_*.py         ← Experimente, nicht produktiv
│   └── test_*.py         ← Test-Skripte
├── data/
│   ├── gmx-cookies.json   ← Aktuelle GMX-Cookies (Session-State)
│   └── fireworksai-pool.json ← Generierte API-Keys
├── backup/
│   └── session/
│       └── gmx-cookies-master.json ← GOLDENER MASTER (nur lesen!)
└── agent_toolbox/
    ├── core/
    │   ├── cdp_client.py      ← Raw CDP Websocket Client
    │   ├── gmx_service.py     ← GMX Service (Alias Rotation, OTP, Session Recovery)
    │   ├── fireworks_service.py ← Fireworks Service (Registration, Login, API Key)
    │   ├── cookie_manager.py  ← Cookie Management (legacy, wird durch CDP ersetzt)
    │   └── browser_manager.py ← Browser Lifecycle Management
    ├── api/
    │   ├── routes/
    │   │   ├── rotation.py    ← Full Rotation Orchestrator
    │   │   ├── gmx.py         ← GMX API Endpoints
    │   │   ├── fireworks.py   ← Fireworks API Endpoints
    │   │   └── browser.py     ← Browser Management Endpoints
    │   └── schemas.py         ← Pydantic Models
    └── start_toolbox.py       ← FastAPI App Entry
```

---

## 🔑 Wichtige Pfade & Credentials

| Item | Wert |
|------|------|
| Chrome Binary | `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` |
| **User Data Dir** | `/Users/simoneschulze/Library/Application Support/Google Chrome` |
| **Profile** | `Profile 73` |
| Local State | `/Users/simoneschulze/Library/Application Support/Google/Chrome/Local State` |
| CDP Port | `9222` |
| GMX Email | `zukunftsorientierte.energie@gmail.com` (Google-Login via GMX) |
| GMX Password | `ZOE.jerry2024` |
| GMX Alias Page | `https://navigator.gmx.net/mail_settings/email_addresses` |
| GMX Inbox | `https://navigator.gmx.net/mail` |
| Fireworks AI | `https://app.fireworks.ai` |

---

## ⚠️ Bekannte Probleme & Workarounds

### GMX Login CAPTCHA
**Problem:** GMX zeigt nach Email-Eingabe im Login-Flow einen CAPTCHA.
**Workaround:** Profil-Kopie + Cookie-Injektion → Session ist bereits aktiv → kein Login nötig. Siehe Session Recovery Protokoll oben.

### auth.gmx.net JavaScript-Transitions
**Problem:** `waitForNavigation()` funktioniert nicht (SPA, keine Page-Reloads).
**Workaround:** Auf DOM-Elemente warten statt auf Navigation.

### GMX FreeMail: Nur EIN Alias
**Problem:** GMX FreeMail erlaubt nur einen Alias gleichzeitig.
**Workaround:** Vor neuer Alias-Erstellung existierenden Alias löschen.

### Cookie-Verschlüsselung (macOS Keychain)
**Problem:** Cookies sind an `user-data-dir` Pfad gebunden.
**Workaround:** Chrome IMMER mit dem exakten `--user-data-dir` starten (siehe Immutable Config oben). Keine Kopien, keine Temp-Dirs.

---

## 🚀 Flow: Alias-Erstellung

1. **Chrome starten** → Mit korrektem `--user-data-dir` + `--profile-directory="Profile 73"` + `--remote-debugging-port=9222`
2. **Session validieren** → GMX Homepage → "E-Mail" click → prüfen ob `navigator.gmx.net/mail?sid=...`
3. **Wenn Session tot:** Recovery-Protokoll ausführen (siehe oben)
4. **CDP verbinden** → Raw Websocket zu `ws://127.0.0.1:9222/devtools/browser/...`
5. **GMX öffnen** → `navigator.gmx.net/mail_settings/email_addresses` (bereits eingeloggt!)
6. **Existierenden Alias löschen** (falls vorhanden)
7. **Neuen Alias erstellen** → `{adjektiv}-{substantiv}@gmx.de`
8. **Fireworks AI registrieren** → mit neuem Alias
9. **API-Key speichern** → `./data/fireworksai-pool.json`
10. **Cookies sichern** → Master-Backup aktualisieren (nur wenn Session bestätigt)

---

## 📝 Namens-Generator Pattern

```javascript
const ADJECTIVES = ['elron', 'dark', 'swift', 'iron', 'silver', ...]; // 32 Einträge
const NOUNS = ['vader', 'runner', 'hawk', 'wolf', 'fox', ...];        // 32 Einträge

// Pattern: {adjektiv}-{substantiv}@gmx.de
// Beispiel: elron-vader@gmx.de, swift-hawk@gmx.de
// Total: 32 × 32 = 1.024 mögliche Kombinationen
```

---

## 🔍 Debugging

### Chrome startet nicht mit CDP?
```bash
# Prüfen ob Chrome bereits läuft:
ps aux | grep -i "chrome" | grep -v grep

# Falls ja: Beenden (hart)
pkill -9 -f "Google Chrome"

# Dann neu starten mit KORREKTEM Profil (siehe Immutable Config oben)
```

### CDP-Port nicht erreichbar?
```bash
# Port prüfen:
lsof -i :9222

# Falls belegt: Anderen Port verwenden
# In .env: CDP_PORT=9223
```

### GMX Session abgelaufen?
Siehe **Session Recovery & Backup-Protokoll** oben.

---

## 📚 Referenzen

- **banned.md** — Liste verbotener Methoden
- **agent_toolbox/core/gmx_service.py** — Session Recovery, Alias-Management
- **agent_toolbox/core/fireworks_service.py** — Fireworks AI Registrierung
- **backup/session/gmx-cookies-master.json** — Goldener Session-Backup (chmod 444)

---

*Letzte Aktualisierung: 2026-05-08*
*Profile: Profile 73 (simoneschulze)*
*Chrome: /Users/simoneschulze/Library/Application Support/Google Chrome*
