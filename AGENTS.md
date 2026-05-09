# AGENTS.md — SINator Fireworks AI Rotator

## 🎯 PROJECT VISION

Automatisierte Erstellung von GMX E-Mail-Aliasen → Fireworks AI Account-Registrierung → API-Key-Pool-Rotation.

**Das Endprodukt:** Ein Pool von Fireworks AI API-Keys die via `POST /rotation/full` automatisch generiert werden. Jeder Key = ein neuer Account mit neuem GMX Alias.

**Architektur:** Python + FastAPI + Raw CDP Websocket (kein Playwright — Playwright crashed bei GMX SPA frame detachment).

---

## 🚨 ABSOLUTE REGELN — NIEMALS ÜBERTRETEN

| VERBOTEN | WARUM |
|---|---|
| `git checkout -- .` / `git reset --hard` | Zerstört alle Arbeitsfortschritte |
| `pkill -9 -f "Google Chrome"` | Zerstört unflushed SQLite → GMX Session tot |
| Profil 901 nach /tmp kopieren | Cookies sind an Original-Pfad gebunden (macOS Keychain) → Session unbrauchbar |
| `--user-data-dir=/tmp/...` | GMX-Session geht verloren |
| `waitForNavigation()` bei GMX | GMX ist SPA — keine Page-Reloads → hängt ewig |

---

## 🏗️ SYSTEM CONFIGURATION (IMMUTABLE)

### Chrome Profile

```
User Data Dir: /Users/jeremy/Library/Application Support/Google Chrome
Profile:       Profile 901 ("SINator (Fireworks AI)")
CDP Port:      9222
Chrome Binary: /Applications/Google Chrome.app/Contents/MacOS/Google Chrome
```

Chrome läuft unter User `simoneschulze` (macOS login profile). Profile 901 wurde von jeremy erstellt und enthält GMX-Sessions. Das ist normal — wichtig ist dass Profile 901 auf Port 9222 funktioniert.

### Chrome Start (DER EINZIG RICHTIGE BEFEHL)

```bash
rtk nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="/Users/jeremy/Library/Application Support/Google Chrome" \
  --profile-directory="Profile 901" \
  --remote-debugging-port=9222 \
  --no-first-run \
  --no-default-browser-check \
  > /tmp/chrome_sinator.log 2>&1 & \
  sleep 6 && \
  rtk curl -s http://127.0.0.1:9222/json/version \
  | python3 -c "import sys,json; print('Chrome OK')"
```

### Chrome Beenden

```bash
kill $(ps aux | grep "[c]hrome.*user-data-dir" | awk '{print $2}' | head -1)
```

(SIGTERM — nicht SIGKILL. pkill -9 zerstört unflushed SQLite.)

---

## 🔄 ZUSTANDSMASCHINE — Rotation Flow

### State: Idle (Browser gestartet, Session valid)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  POST /browser/start  → Browser läuft auf Port 9222                     │
│  POST /rotation/full  → Vollständige Rotation startet                   │
└─────────────────────────────────────────────────────────────────────────┘
```

### State: Rotation in Progress (Phasen)

```
Phase 1: GMX Session validieren
         └─ GMX Homepage → "E-Mail" click → prüfe navigator.gmx.net/mail?sid=...
         └─ Wenn tot → Session Recovery Protokoll ausführen

Phase 2: GMX Alias löschen (falls vorhanden)
         └─ navigate to allEmailAddresses
         └─ Force-reveal hidden template → Delete-Icon click → OK

Phase 3: GMX Alias erstellen
         └─ {adjektiv}-{substantiv}@gmx.de (aus Namensgenerator)
         └─ Input[name*="localPart"] füllen + Hinzufügen-Button click

Phase 4: Fireworks Cookie-Clear (nur Fireworks-Domain!)
         └─ GMX-Cookies BLEIBEN (shared browser, Profile 901)

Phase 5: Fireworks /signup laden + Cookie Banner dismissen
         └─ Cookiebot: .cky-btn-accept per CDP coordinate click
         └─ Button ist in DOM aber _find_element() findet ihn nicht
         └─ Fix: direktes JS-Query + evaluate-basierte rect lookup

Phase 6: Email → Next → Password → Create Account
         └─ URL muss zu /signup/verify wechseln (account_created)
         └─ Wenn URL nicht wechselt → create_account_clicked aber account_created fehlt

Phase 7: GMX OTP Polling (30 retries × 6s = 180s)
         └─ navigate(gmx.net) → "E-Mail" click → inbox
         └─ Suche nach "fireworks" + "verif" im Email-Text
         └─ Falls Email gefunden aber kein URL → Email klicken → Email-Page scrapen
         └─ Timeout erhöhen von 60s auf 180s (Email-Delay kann 2-5min sein)

Phase 8: OTP URL öffnen → Account verifiziert

Phase 9-17: Login + Setup
         └─ /login → "Sign In" → "Email Login" → Email+Password → Next
         └─ FirstName/LastName (aus Alias extrahieren) + Terms Checkbox
         └─ Use Case Checkboxes → "Submit to get $5 Credits"
         └─ 15s + 5×2s Polling auf Credits-Aktivierung

Phase 18-20: API Key
         └─ navigate(/settings/workspace/api-keys)
         └─ Create → Name eingeben → Generate → Key extrahieren (fw-... Pattern)
         └─ Key speichern in data/fireworksai-pool.json
```

### State: Rotation Complete

```
Erfolg: API-Key in Pool, Account verifiziert, Credits aktiv
Partial: Account erstellt aber OTP/Setup/Key fehlgeschlagen
Failed: Account-Erstellung fehlgeschlagen (Email taken, Bot-Detection, etc.)
```

---

## 🔧 SESSION RECOVERY PROTOKOLL

### Wenn GMX Session TOT:

```
1. Browser SOFORT beenden: kill $(ps aux | grep "[c]hrome.*user-data-dir" ...)
2. data/gmx-cookies.json LÖSCHEN (enthält abgelaufene Cookies)
3. backup/session/gmx-cookies-master.json → data/gmx-cookies.json kopieren
4. Chrome neu starten (siehe Chrome Start Befehl oben)
5. Cookies via CDP injizieren (Network.setCookie)
6. GMX Homepage → "E-Mail" click → navigator.gmx.net/mail?sid=... prüfen
```

### Backup-Struktur

```
backup/session/
├── gmx-cookies-master.json  ← Goldener Master (chmod 444, READ-ONLY!)
├── gmx-cookies-current.json ← Aktueller Zustand
└── last-known-good/         ← Snapshot vor jeder Rotation
```

### Session Validierung (IMMER VOR JEDER OPERATION)

```python
async def _validate_gmx_session(client, session_id):
    await client.navigate(session_id, "https://www.gmx.net/")
    await asyncio.sleep(3)
    await client.click_at(session_id, 302, 44)  # "E-Mail" Header
    await asyncio.sleep(5)
    url = await client.evaluate(session_id, "window.location.href")
    return "navigator.gmx.net/mail?sid=" in url
```

---

## 📁 DATENMODELL

### data/fireworksai-pool.json

```json
{
  "accounts": [
    {
      "email": "swift-hawk@gmx.de",
      "api_key": "fw-...",
      "key_name": "alias-2026-05-09",
      "created_at": "2026-05-09T12:00:00Z",
      "used_count": 0
    }
  ]
}
```

### data/gmx-cookies.json

429 Entries, Chrome CDP Export Format. Nur GMX-relevante Cookies (domain enthält "gmx") werden injiziert.

### backup/session/gmx-cookies-master.json

Goldener Master-Backup. Nach jeder erfolgreichen Rotation aktualisieren (nur wenn Session bestätigt funktioniert). chmod 444 setzen.

---

## 🧠 NAMENS-GENERATOR

```javascript
const ADJECTIVES = ['elron', 'dark', 'swift', 'iron', 'silver', ...]; // 32 Einträge
const NOUNS = ['vader', 'runner', 'hawk', 'wolf', 'fox', ...];        // 32 Einträge

// Pattern: {adjektiv}-{substantiv}@gmx.de
// Beispiel: elron-vader@gmx.de, swift-hawk@gmx.de
// Total: 32 × 32 = 1.024 mögliche Kombinationen
```

---

## 📂 PROJEKT-STRUKTUR

```
agent_toolbox/
├── core/
│   ├── cdp_client.py          ← Raw CDP Websocket Client (IMMER via CDP, nie Playwright)
│   ├── gmx_service.py         ← GMX Session, Alias-Erstellung/Löschung
│   ├── fireworks_service.py   ← Fireworks E2E Registrierung (20-Phasen Flow)
│   ├── browser_manager.py     ← Singleton Browser Lifecycle
│   └── pool_manager.py        ← API-Key Pool CRUD
├── api/
│   ├── routes/
│   │   ├── rotation.py        ← POST /rotation/full (HAUPT-ENDPOINT)
│   │   ├── gmx.py             ← POST /gmx/alias/create, /gmx/alias/delete
│   │   ├── fireworks.py       ← Fireworks API Endpoints
│   │   ├── browser.py         ← POST /browser/start, /browser/stop, /browser/status
│   │   ├── cookies.py         ← POST /cookies/extract, /cookies/inject, /cookies/recover
│   │   └── pool.py            ← GET /pool/stats, GET /pool/key, POST /pool/reset
│   └── schemas.py             ← Pydantic Models
└── start_toolbox.py           ← FastAPI App Entry
```

**Start:** `python agent_toolbox/start_toolbox.py` oder `uvicorn agent_toolbox.start_toolbox:app --reload`

---

## 🐛 BEKANNTE PROBLEME & FIXES

### Cookie Banner dismiss
**Problem:** `_find_element()` findet `.cky-btn-accept` nicht (Shadow DOM). JS locator returned `found: false` obwohl Button in DOM existiert.
**Fix:** Direktes JS-Query im `_dismiss_cookie_banner()` fallback-path. Button ist BEWIESEN an `(1113.7, 805.5)` — harte Koordinaten als Fallback.

### `_fill_input` React Controlled Components
**Problem:** Fireworks.ai verwendet React `useState` für alle Inputs. `input.value = ''` + `dispatchEvent(input)` dispatcht EIGENTLICH ein Event aber React's `onChange` Handler reagiert NICHT auf synthetische Events wenn `value` direkt gesetzt wird. Das Ergebnis: Input zeigt den Text aber React-State ist LEER → "Next" klicken hat keinen Effekt, Form advance nicht.
**Fix:** `nativeInputValueSetter` — `Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, value)` umgeht das React synthetic event system und setzt den internen State direkt. Dazu `input.dispatchEvent(new Event('input', {bubbles: true, composed: true}))` für React.
**Critical:** KeyEvents (`Input.dispatchKeyEvent`) funktionieren NICHT für React controlled inputs bei Sonderzeichen (`.`, `@`). Immer `nativeInputValueSetter` verwenden.

### GMX SPA Navigation
**Problem:** Direkte Navigation zu `navigator.gmx.net/mail` redirected zu `www.gmx.net/`.
**Fix:** Navigate zu GMX Homepage → "E-Mail" Header-Button clicken → Warten → URL prüfen. Niemals `waitForNavigation()` verwenden (GMX ist SPA).

### OTP Email Detection
**Problem:** OTP Polling JS scannt den falschen DOM-Bereich (landet auf Homepage nach reload).
**Fix:** Navigate zu GMX Homepage → "E-Mail" click → 3s warten → DOM scrapen. Bei "needs_click" → Email-Element finden und klicken → Email-Page scrapen.

### Account Creation Redirect
**Problem:** "Create Account" klicken aber URL wechselt nicht zu `/signup/verify`.
**Fix:** FAIL-HARD — kein `/signup/verify` in URL = `account_creation_redirect_mismatch`. Account wurde NICHT erstellt. Chrome neu starten, Session recover, erneut versuchen.

### GMX FreeMail: Nur EIN Alias
**Problem:** GMX FreeMail erlaubt nur einen Alias gleichzeitig.
**Fix:** Vor neuer Alias-Erstellung existierenden Alias löschen (Phase 2).

---

## 📡 API ENDPOINTS (ÜBERSICHT)

| Methode | Endpoint | Beschreibung |
|---|---|---|
| POST | `/browser/start` | Chrome mit Profile 901 starten |
| POST | `/browser/stop` | Chrome beenden (SIGTERM) |
| GET | `/browser/status` | Browser-Status + CDP-Port prüfen |
| POST | `/rotation/full` | Komplette Rotation: GMX Alias + Fireworks E2E |
| POST | `/gmx/session/validate` | GMX Session validieren |
| POST | `/gmx/alias/create` | GMX Alias erstellen |
| POST | `/gmx/alias/delete` | GMX Alias löschen |
| POST | `/cookies/extract` | Cookies aus aktuellem Chrome extrahieren |
| POST | `/cookies/inject` | Cookies in Chrome injizieren |
| POST | `/cookies/recover` | Session aus Master-Backup wiederherstellen |
| GET | `/pool/stats` | Pool-Statistiken |
| GET | `/pool/key` | Nächsten verfügbaren Key abrufen |

---

## 🔍 DEBUGGING

```bash
# Chrome startet nicht?
ps aux | grep -i "[c]hrome.*user-data-dir"
lsof -i :9222

# CDP erreichbar?
curl -s http://127.0.0.1:9222/json/version | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['webSocketDebuggerUrl'])"

# GMX Session tot?
# → Session Recovery Protokoll ausführen (siehe oben)

# Cookie Banner bleibt?
# → Mit CDP evaluate() rect prüfen: document.querySelector('.cky-btn-accept').getBoundingClientRect()
```

---

## 📚 REFERENZEN

| Thema | Datei |
|---|---|
| Verbannte Methoden | `banned.md` |
| CDP Client API | `agent_toolbox/core/cdp_client.py:85` |
| GMX Service (Session, Alias) | `agent_toolbox/core/gmx_service.py` |
| Fireworks E2E Flow | `agent_toolbox/core/fireworks_service.py:875` |
| Rotation Orchestrator | `agent_toolbox/api/routes/rotation.py:55` |
| Pool Manager | `agent_toolbox/core/pool_manager.py` |
| Chrome Lifecycle | `agent_toolbox/core/browser_manager.py` |

*Letzte Aktualisierung: 2026-05-09*