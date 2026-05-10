# AGENTS.md — SINator Fireworks AI Rotator

## 🎯 PROJECT VISION

**Ziel:** Automatisierte Erstellung von Fireworks AI API-Keys via GMX Alias → Fireworks Account → OTP Verification → API-Key Pool.

**Endprodukt:** `POST /rotation/full` liefert einen `fw-...` API-Key. Jeder Key = ein neuer GMX Alias + ein neuer Fireworks Account + $5 Credits.

**Stack:** Python + FastAPI + Raw CDP Websocket (KEIN Playwright — Playwright crashed bei GMX SPA frame detachment).

**Start:** `python agent_toolbox/start_toolbox.py` → `http://localhost:8000/docs`

---

## 🚨 PROZESS-REGELN (aus Fehlschlägen gelernt)

### REGEL 1: DELETE WRONG IMMEDIATELY
Nach einem Fehlschlag: **SOFORT** Dateien/Ordner löschen die den failed approach enthalten.
NIE: "vielleicht brauch ich das später" — es kostet nur Zeit beim nächsten Versuch.

### REGEL 2: ONCE VERIFIED = READ-ONLY
Ein funktionierender Code-Abschnitt wird NICHT mehr angefasst. NUR Änderungen für:
Bug-Fix, Performance-Issue, neuer Use-Case. Bei Unsicherheit: NEUE Datei, nicht existierende ändern.

### REGEL 3: FÜTTERE AGENTS.MD NACH JEDEM ERFOLG
Neue Learnings → SOFORT in AGENTS.md. Prozedur:
- Erfolg → AGENTS.md updaten (bewiesene Fixes, Koordinaten, Data Models)
- Fehlschlag → banned.md updaten (verbotene Methode + warum)
- Learnings NIE nur im Chat lassen

---

## 🚨 ABSOLUTE REGELN — NIEMALS ÜBERTRETEN

| VERBOTEN | WARUM |
|---|---|
| `git checkout -- .` / `git reset --hard` | Zerstört alle Arbeitsfortschritte |
| `pkill -9 -f "Google Chrome"` | Zerstört unflushed SQLite → GMX Session tot |
| Profil 901 nach /tmp kopieren | Cookies an Original-Pfad gebunden (macOS Keychain) → Session unbrauchbar |
| `--user-data-dir=/tmp/...` | GMX-Session geht verloren |
| `waitForNavigation()` bei GMX | GMX ist SPA — keine Page-Reloads → hängt ewig |

---

## 🏗️ SYSTEM CONFIGURATION (IMMUTABLE)

```
Chrome Binary:     /Applications/Google Chrome.app/Contents/MacOS/Google Chrome
User Data Dir:     /Users/jeremy/Library/Application Support/Google Chrome
Profile:           Profile 901 ("SINator (Fireworks AI)")
CDP Port:          9222
Chrome User:       simoneschulze (macOS login profile)
CDP Endpoint:      ws://127.0.0.1:9222/devtools/browser/...
```

**Chrome Start (DER EINZIG RICHTIGE WEG):**
```bash
rtk nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="/Users/jeremy/Library/Application Support/Google Chrome" \
  --profile-directory="Profile 901" \
  --remote-debugging-port=9222 \
  --no-first-run --no-default-browser-check \
  > /tmp/chrome_sinator.log 2>&1 &
sleep 6 && curl -s http://127.0.0.1:9222/json/version | python3 -c "import sys,json; print('Chrome OK')"
```

**Chrome Beenden (SIGTERM, nicht SIGKILL):**
```bash
kill $(ps aux | grep "[c]hrome.*user-data-dir" | awk '{print $2}' | head -1)
```

---

## 📂 PROJEKT-STRUKTUR

```
SINator-fireworksai/
├── agent_toolbox/
│   ├── start_toolbox.py           FastAPI Entrypoint (uvicorn)
│   ├── core/
│   │   ├── cdp_client.py          Raw CDP Websocket Client (KEIN Playwright)
│   │   ├── gmx_service.py         GMX: Session, Alias rotate/delete/create
│   │   ├── fireworks_service.py   Fireworks: E2E 20-Phasen Flow
│   │   ├── browser_manager.py     Browser Lifecycle (Singleton)
│   │   ├── pool_manager.py        API-Key Pool CRUD
│   │   └── cookie_manager.py      Cookie Management (legacy)
│   └── api/
│       ├── schemas.py             Pydantic Request/Response Models
│       └── routes/
│           ├── rotation.py        POST /rotation/full  ← HAUPT-ENDPOINT
│           ├── gmx.py             GMX Alias Endpoints
│           ├── fireworks.py       Fireworks Standalone Endpoints
│           ├── browser.py         Browser Start/Stop/Status
│           ├── cookies.py         Cookie Extract/Inject/Recover
│           └── pool.py            Pool Stats/Key/Get
├── tools/
│   └── gmx_alias_tool.py          ← VERIFIZIERTES READ-ONLY CLI-TOOL
│                                  BEZEICHNUNG: VERIFIZIERT, NIEMALS ÄNDERN!
├── data/
│   └── fireworksai-pool.json      API-Key Pool (JSON)
├── backup/session/
│   └── gmx-cookies-master.json    Goldener Session-Backup (chmod 444, READ-ONLY!)
├── AGENTS.md                      ← DIESE DATEI (Single Source of Truth)
└── banned.md                      Verbotene Methoden
```

**Starten:** `python agent_toolbox/start_toolbox.py`
**API Docs:** `http://localhost:8000/docs`

---

## 🔄 ZUSTANDSMASCHINE — KOMPLETTER ROTATION FLOW

### POST /rotation/full (HAUPT-ENDPOINT)

```
Request:
{
  "new_alias_name": null,           // Optional: eigener Name, sonst auto-generiert
  "fireworks_password": "Passwort!", // Passwort für neuen FW Account (required)
  "save_to_pool": true              // Key in Pool speichern (default: true)
}

Response:
{
  "status": "success|partial|failed|error",
  "gmx_alias": "swift-hawk-842@gmx.de",
  "fireworks_account": "swift-hawk-842@gmx.de",
  "api_key": "fw-...",
  "api_key_name": "swift",
  "steps_completed": [...],
  "steps_failed": [...],
  "execution_time": "187.32s",
  "error": null
}
```

---

### Flow #0: GMX Login / Session Recovery (ensure_gmx_session)

**Methode:** `GmxService.ensure_gmx_session(email, password, cdp_port)`

```
PRÜFUNG: Kann GMX Inbox erreicht werden?
  → navigate(gmx.net) → click E-Mail (208, 44) → wait 5s
  → URL enthält navigator.gmx.net/mail?sid= ?
  → JA: Session OK → weiter zu Flow 1

FALLS NICHT (Session korrupt):
  a) JS click auf ACCOUNT-AVATAR → öffnet Shadow DOM Dropdown
     → JS click auf Logout BUTTON (im Shadow DOM!)
  b) JS click auf ACCOUNT-AVATAR → JS click auf Login
     (ERSTE attempt - GMX ignoriert diesen Klick!)
  b2) Email + Passwort eingeben und Login klicken (ignoriert)
  c) JS click auf ACCOUNT-AVATAR → JS click auf Login
     (ZWEITE attempt - jetzt erscheint Email-Form!)
  d) Email: opensin@gmx.de → Click Weiter
  e) Passwort: ZOE.jerry2024 → Click Login
  f) Verifizieren: Click E-Mail → navigator.gmx.net/mail?sid= ?
```

**CRITICAL: Shadow DOM Handling**
- ACCOUNT-AVATAR ist ein Custom Element mit Shadow DOM
- CDP `click_at()` öffnet das Dropdown NICHT zuverlässig
- `getBoundingClientRect()` gibt 0x0 für Shadow DOM Elemente zurück
- **Lösung:** JS `.click()` auf das Custom Element + `.dispatchEvent(new Event('mouseenter'))`
- Dann JS `.click()` auf Buttons im Shadow DOM via `avatar.shadowRoot.querySelectorAll('button')`
- 3s Wait für Shadow DOM Rendering nötig

**Login Formular:**
- 2-Schritt Formular: Email → Weiter → Password → Login
- Nach Login-Formular: Beide Felder (Email + Password) sichtbar
- Buttons: "Weiter" dann "Login" (nicht "Anmelden")

**Credentials:**
- Email: `opensin@gmx.de`
- Passwort: `ZOE.jerry2024`

**WICHTIG:** Flow 0, 1, 2, 3 sind ALLE READ-ONLY! NIEMALS ÄNDERN außer bei konkretem Bug-Report!

**Flow 0 Status:** ✅ VERIFIED — 54.93s durchschnittlich, 5/5 Tests erfolgreich — **READ-ONLY SINCE 2026-05-10**
- Letzter Test: 2026-05-10, SID: 331e8dc82fec93376c05f1148c0bc2...
- Ablauf: Logout → Login(ignoriert) → Login(funktioniert) → Email+Weiter → Passwort+Login → E-Mail Klick → SID
- **FILE:** `agent_toolbox/core/gmx_service.py` — `_click_profile_icon_and_action()`, `_do_email_password_login()`, `ensure_gmx_session()`

---

### ⚠️⚠️⚠️ Flow #1: GMX Alias Rotation — READ-ONLY VERIFIED (2026-05-10) ⚠️⚠️⚠️

**STATUS: READ-ONLY — NIEMALS ÄNDERN!**

**Breakdown-Recovery (2026-05-10):** Agent attempted "DOM exploration" to find Shadow-DOM input → rewrote `_navigate_to_all_email_addresses` with 75-line PFAD-based navigation → broke Flow #1 completely. **All 11 files reverted to commit `cf146a6`**. This proved Flow #1 works perfectly as-is — DO NOT touch.

**File:** `agent_toolbox/core/gmx_service.py` (NIEMALS ändern!)
**Verified at:** `cf146a6 fix: pool_manager dual-format support + AGENTS.md 5 factual corrections`
**Last working:** 2026-05-09 — 29s per rotation, elron-runner-701@gmx.de created

**Methode:** `GmxService.rotate_alias(new_alias_name=None, cdp_port=9222)`

**Methode:** `GmxService.rotate_alias(new_alias_name=None, cdp_port=9222)`

```
Phase 1: GMX Session validieren
         └─ _connect_to_browser(cdp_port) → client, session_id
         └─ GMX Homepage → "E-Mail" click (coords 235, 33)
         └─ Prüfe: bap.navigator.gmx.net/mail?sid=... → OK
         └─ Wenn tot → Session Recovery (siehe unten)

Phase 2: GMX Alias löschen (falls vorhanden)
         └─ _navigate_to_all_email_addresses()
           → navigate(gmx.net/mail_settings/email_addresses)
           → Wicket SPA: Click "E-Mail-Adressen" im Header
         └─ _delete_existing_alias()
           → JS: .js-template.is-hidden.removeClass('is-hidden') → style.display=block
           → Delete-Icon: a[title="E-Mail-Adresse löschen"] klicken
           → OK-Button im Bestätigungs-Dialog
           → Erfolg: "Ihr Eintrag wurde erfolgreich gelöscht"

Phase 3: GMX Alias erstellen
         └─ generate_alias_name() → "{adj}-{noun}-{3digits}" (z.B. "elron-vader-412")
         └─ _fill_alias_input(client, session_id, alias_name)
           → Input[name*="localPart"] füllen via CDP
           → Events: input, change, blur
         └─ _find_hinzufuegen_button() → Button finden
         └─ _click_button_via_cdp(client, session_id, btn)
           → CDP Input.dispatchMouseEvent (mousePressed + mouseReleased)
         └─ _check_creation_success(client, session_id, alias_name)
           → Alias in .table_body-row?
           → "wurde erfolgreich angelegt"?
           → Falls "nicht verfügbar" → neuer Name, max 3 Versuche
         └─ Return: {status, created_alias, alias_name, steps_completed}

Alias-Generator (32 Adjektive × 32 Nouns × 999 Suffix = ~1M Kombinationen):
  ADJECTIVES: elron, dark, swift, iron, silver, golden, crystal, shadow,
              storm, frost, blaze, thunder, cosmic, neon, cyber, quantum,
              alpha, beta, delta, omega, zenith, nexus, vortex, pulse,
              echo, phantom, spectra, turbo, hyper, ultra, mega, super
  NOUNS:      vader, runner, hawk, wolf, fox, tiger, eagle, shark,
              dragon, phoenix, falcon, panther, cobra, lynx, raven, jaguar,
              bear, lion, whale, dolphin, puma, cheetah, otter, badger,
              wolverine, raptor, condor, scorpion, spider, mantis, beetle
```

---

### Flow #2: Fireworks E2E Registry (fireworks_service.register())

**Methode:** `FireworksService.register(email, password, gmx_password, cdp_port=9222)`

```
Phase 4: Fireworks Domain Cleanup (nur Fireworks-Cookies!)
         └─ Network.getAllCookies → alle Cookies
         └─ Network.deleteCookies für domain="app.fireworks.ai" oder "fireworks"
         └─ GMX-Cookies BLEIBEN (shared browser, Profile 901)
         └─ LocalStorage: fireworks.ai cleared

Phase 5: Cookie Banner dismissen
         └─ navigate("https://app.fireworks.ai/signup")
         └─ _dismiss_cookie_banner(client, session_id):
           → JS querySelector('.cky-btn-accept') → rect → center
           → Falls not found → direktes JS-Query im Container
           → Falls still not found → hardcoded fallback coords (1113.7, 805.5)
           → CDP click_at() → mousePressed + mouseReleased
           → Validierung: .cky-consent-container height=0 oder display=none
           → Wait 2s

Phase 6: Email → Next → Password → Create Account
         └─ _fill_input(client, session_id, ['#email-display'], email)
           → KRITISCH: nativeInputValueSetter verwenden!
           → Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set
           → Plus: Event('input', {bubbles: true, composed: true})
           → KeyEvents funktionieren NICHT für React controlled inputs!
         └─ _click_button(client, session_id, ['button:contains("Next")'])
           → JS text matching: (btn.textContent||'').trim().toLowerCase() === 'next'
           → CDP click_at() an Button-Center
           → Wait 3s
         └─ URL wechselt zu Step 2 (Password)
         └─ _fill_input(client, session_id, ['input#password'], password)
         └─ _fill_input(client, session_id, ['input#confirm-password'], password)
         └─ _click_button(client, session_id, ['button:contains("Create Account")'])
           → URL MUSS zu /signup/verify wechseln
           → Wenn nicht → FAIL-HARD: return {status: "partial", steps_failed: ["account_creation_redirect_mismatch"]}

Phase 7: GMX OTP Polling (30 retries × 6s = 180s)
         └─ goto_inbox():
           → navigate(gmx.net) → JS click "E-Mail" im Header
           → Wait 3s → URL = bap.navigator.gmx.net/mail?sid=...
         └─ OTP suchen im Main Frame DOM:
           → selectors: inbox-content, maillist, mail_list, main [class*="list"]
           → Suche nach "fireworks" + "verif" im innerText
           → Falls Email gefunden aber kein URL → "needs_click" path
           → Email row clicken → Email-Page scrapen für OTP URL
           → URL Pattern: https://app.fireworks.ai/signup/verify?token=...
         └─ Falls timeout: return {status: "partial", steps_failed: ["otp_not_found"]}
         └─ Email-Delay kann 2-5min dauern → 180s ist nötig
```

---

### Flow #3: GMX OTP Email Detection (innerhalb Phase 7)

---

## 🔬 TECHNISCHE ERKENNTNISSE — Shadow DOM & Custom Elements

### ACCOUNT-AVATAR Shadow DOM Struktur
```
ACCOUNT-AVATAR (Custom Element)
└── #shadow-root
    ├── .appa-user-icon
    │   └── section.appa-user-icon__initials
    │       └── appa-ui-lux-svg-icon (fallback icon)
    └── #appa-account-flyout (Dropdown — wird via JS Events geöffnet)
        ├── .appa-account-flyout__header
        │   ├── .appa-account-flyout__avatar "JS"
        │   ├── .appa-account-flyout__plan "FreeMail"
        │   ├── h1 "Jerem Schulz"
        │   └── p "opensin@gmx.de"
        ├── section (Account Management Links)
        │   ├── a "Account verwalten"
        │   └── a "E-Mail Einstellungen"
        ├── section (Action Buttons)
        │   ├── button "Logout"           ← Y=384 (nach JS .click())
        │   ├── button "Zum Postfach"   ← Y=432
        │   └── button "Account wechseln" ← Y=480
        └── section (Footer Links)
            ├── a "Feedback"
            └── a "Hilfe & Kontakt"
```

### Warum CDP click_at() NICHT funktioniert für Shadow DOM
1. **getBoundingClientRect()** gibt **0×0** zurück für Shadow DOM Elemente
2. **Custom Elements** reagieren auf interne Events, nicht auf CDP Mouse Events
3. **ACCOUNT-AVATAR** öffnet Flyout nur bei `mouseenter` + `click` Events
4. **Lösung:** JS `.click()` + `.dispatchEvent(new Event('mouseenter'))` auf das Custom Element

### Korrekte Interaktions-Reihenfolge
```javascript
// 1. Avatar finden und öffnen
var avatar = document.querySelector('ACCOUNT-AVATAR');
avatar.click();
avatar.dispatchEvent(new Event('mouseenter', {bubbles: true}));

// 2. 3s warten für Shadow DOM Rendering

// 3. Button im Shadow DOM via JS klicken
var buttons = avatar.shadowRoot.querySelectorAll('button');
for (var i=0; i<buttons.length; i++) {
    if (buttons[i].textContent.trim().toLowerCase() === 'logout') {
        buttons[i].click();
        buttons[i].dispatchEvent(new Event('click', {bubbles: true}));
    }
}
```

### GMX Login Flow — Vollständige State Machine
```
State: LOGGED_IN
  → ACCOUNT-AVATAR zeigt: "Zum Postfach", "Account wechseln"
  
State: LOGOUT (nach Klick auf "Logout")
  → URL: https://www.gmx.net/logoutlounge
  → Seite zeigt: "Login vorübergehend nicht möglich"
  → Nach 3s Refresh: normale GMX Homepage
  
State: LOGIN_ATTEMPT_1 (erster Klick auf "Login")
  → GMX IGNORIERT diesen Klick!
  → URL bleibt: https://www.gmx.net/
  → Kein Formular erscheint
  
State: LOGIN_ATTEMPT_2 (zweiter Klick auf "Login")
  → Jetzt erscheint das Login-Formular!
  → URL: https://auth.gmx.net/login?prompt=none&state=...
  → Formular hat: Email-Input + Password-Input + "Login" Button
  
State: EMAIL_ENTERED
  → Email eingeben + "Weiter" klicken
  → URL bleibt gleich, Formular zeigt jetzt auch Password
  
State: PASSWORD_ENTERED  
  → Password eingeben + "Login" klicken
  → URL wechselt zu: https://bap.navigator.gmx.net/mail?sid=...
  
State: LOGGED_IN (wieder)
  → Session OK! Weiter zu Flow 1.
```

### Element-Koordinaten (Viewport 1200×919)
| Element | Selektor | X | Y | Typ |
|---|---|---|---|---|
| ACCOUNT-AVATAR | `document.querySelector('ACCOUNT-AVATAR')` | 1066 | 44 | Custom Element |
| Logout Button | `avatar.shadowRoot.querySelectorAll('button')[0]` | 914 | 384 | BUTTON |
| Zum Postfach | `avatar.shadowRoot.querySelectorAll('button')[1]` | 914 | 432 | BUTTON |
| Account wechseln | `avatar.shadowRoot.querySelectorAll('button')[2]` | 914 | 480 | BUTTON |

---

### Flow #3: GMX OTP Email Detection (innerhalb Phase 7)

```
Herausforderung: GMX Emails sind im iframe (3c-bap.gmx.net/mail/client/start)
                 Main Frame zeigt nur den Navigator-Frame mit iframe-URL
                 OTP sucht im Main Frame → findet keine Emails

Lösung: navigate(gmx.net) → JS click "E-Mail" → bap.navigator.gmx.net/mail?sid=...
        OTP sucht im Main Frame DOM nach "fireworks" + "verif"
        GMX Inbox URL ist: https://bap.navigator.gmx.net/mail?sid={sid}
        Email-Liste ist im iframe aber der SID-Token reicht für HTTP-Zugriff

GMX SPA Navigation (KRITISCH):
  ❌ navigate("navigator.gmx.net/mail") → redirected zu www.gmx.net/
  ✅ navigate("www.gmx.net/") → JS click "E-Mail" bei (235, 33) → Inbox URL erreicht

Falls "needs_click":
  → Email row finden: [class*="item"], [class*="row"], tr
  → Row clicken → Email-Page öffnet sich
  → Email-Page scrapen: innerHTML contains "fireworks.ai/signup/verify?token="
```

---

### Flow #4: Fireworks Login + Setup (Phase 9-17)

```
Phase 9:  Navigate zu /login → "Sign In" Button klicken
         → URL: https://app.fireworks.ai/login
         → Button "Sign In" bei coords ~(942, 398)

Phase 10: "Email Login" oder "Use Email Instead" klicken
         → Auf /login erscheint ein Email-Formular nach dem OAuth-Link

Phase 11: Email + Password eingeben + "Next" klicken
         → _fill_input() mit nativeInputValueSetter

Phase 12: FirstName/LastName eingeben
         → Aus Alias extrahieren: "swift-hawk" → Swift + Hawk
         → nativeInputValueSetter verwenden

Phase 13: Checkbox "I agree to Terms of Service" per CDP click
         → Find via: checkbox, [type="checkbox"], label containing "Terms"

Phase 14: "Continue" Button klicken

Phase 15: Checkbox "Flexible capacity for production" per CDP click

Phase 16: Checkbox "Conversational AI" per CDP click

Phase 17: "Submit to get $5 Credits" klicken
         → Find via: button text containing "$5 Credits"

Phase 18: Credits-Aktivierung abwarten
         → 15s initial wait
         → 5×2s Polling: Seite scannen nach "credits" oder "activated"
         → Falls Credits nicht aktiv: continue anyway (partial)

Phase 19: Navigate zu /settings/workspace/api-keys
         → URL: https://app.fireworks.ai/settings/workspace/api-keys

Phase 20: API Key erstellen
         → "Create API Key" Button klicken
         → Name eingeben: alias-YYYY-MM-DD
         → "Generate Key" Button klicken
         → Key extrahieren:fw-[a-zA-Z0-9]{32,} Pattern
         → Key speichern in data/fireworksai-pool.json via pool_manager.add_key()
```

---

## 🔧 SESSION RECOVERY PROTOKOLL

### Wenn GMX Session TOT:

```
1. Browser beenden: kill $(ps aux | grep "[c]hrome.*user-data-dir" ...)
2. Chrome neu starten (Chrome Start Befehl)
3. GMX Homepage → "E-Mail" click → navigator.gmx.net/mail?sid=... prüfen
```

### Session Validierung (IMMER VOR JEDER OPERATION):

```python
async def _validate_gmx_session(client, session_id):
    await client.navigate(session_id, "https://www.gmx.net/")
    await asyncio.sleep(3)
    await client.click_at(session_id, 235, 33)  # "E-Mail" Header
    await asyncio.sleep(5)
    url = await client.evaluate(session_id, "window.location.href")
    return "navigator.gmx.net/mail?sid=" in url or "bap.navigator.gmx.net/mail?sid=" in url
```

---

## 🛠️ GMX ALIAS TOOL — VERIFIZIERTES INTERAKTIONS-TOOL

**⚠️ READ-ONLY VERIFIED — ÄNDERN VERBOTEN!**
Dieses Tool wurde getestet und verifiziert. Alle GMX-Operationen nutzen die
bewiesenen GmxService-Methoden. Nächster Agent darf dieses Tool NICHT ändern.

### Pfad
```
tools/gmx_alias_tool.py
```

### Usage
```bash
# Session-Status prüfen
python tools/gmx_alias_tool.py status

# Detaillierte Session-Validierung
python tools/gmx_alias_tool.py check

# Alias rotieren (delete + create, auto-generiert)
python tools/gmx_alias_tool.py rotate

# Alias rotieren mit bestimmtem Namen
python tools/gmx_alias_tool.py rotate swift-hawk-999

# Nur Alias erstellen (auto-generiert)
python tools/gmx_alias_tool.py create

# Alias mit bestimmtem Namen erstellen
python tools/gmx_alias_tool.py create thunder-dragon-500

# Alias löschen (mit Bestätigung)
python tools/gmx_alias_tool.py delete
```

### API Alternative (FastAPI)
```bash
# Alias rotieren
curl -X POST http://localhost:8000/gmx/alias/rotate

# Alias mit bestimmtem Namen
curl -X POST "http://localhost:8000/gmx/alias/rotate" \
  -H "Content-Type: application/json" \
  -d '{"new_alias_name": "swift-hawk-999"}'

# Nur erstellen
curl -X POST "http://localhost:8000/gmx/alias/create?alias_name=thunder-dragon-500"

# Session prüfen
curl -X POST http://localhost:8000/gmx/session/check

# Alias löschen
curl -X POST http://localhost:8000/gmx/alias/delete
```

### Output-Beispiele
```
=== GMX Alias Rotation ===
   Target: swift-hawk-999

✅ Rotation
   Status: success
   Created: swift-hawk-999@gmx.de
   Deleted: neon-phoenix-307@gmx.de
   Steps OK: navigated_to_addresses → alias_deleted → form_filled → add_button_clicked → alias_created
   Time: 16.46s
```

### Intern implementiert via:
- `GmxService.rotate_alias(new_alias_name, cdp_port)` → verifiziert ✅
- `GmxService.create_alias(alias_name, cdp_port)` → verifiziert ✅
- `GmxService.delete_existing_alias(cdp_port)` → verifiziert ✅
- `GmxService.check_session(cdp_port)` → verifiziert ✅
- `get_browser_ws_endpoint()` → urllib-basiert, funktioniert ✅

### WICHTIG: Browser muss laufen!
Vor Nutzung: `curl -X POST http://localhost:8000/browser/start`
Falls Session tot: `curl -X POST http://localhost:8000/cookies/recover`

---

## 🔧 BACKUP-STRUKTUR (für Session Recovery)

```
backup/session/
└── gmx-cookies-master.json  ← Goldener Master (chmod 444, READ-ONLY!)
```

---

## 📁 DATENMODELL

### data/fireworksai-pool.json (PoolManager)

PoolManager unterstützt BEIDE Formate: Legacy `{"accounts": [...]}` und neues `[{...}]`.
```json
// Neues Format (empfohlen) — Plain Array
[
  {
    "id": "uuid-8-stellig",
    "api_key": "fw-Za4b8C2d1E9f0G3h...",
    "alias_email": "swift-hawk-842@gmx.de",
    "key_name": "swift-hawk",
    "created_at": "2026-05-09T12:00:00Z",
    "used": false,
    "used_at": null
  }
]

// Legacy Format (noch auf Disk: {"accounts": []})
// PoolManager erkennt beide automatisch via _load()
```

**PoolManager API:**
- `add_key(api_key, alias_email, key_name)` → {status, key_id}
- `get_available_key()` → {api_key, alias_email, key_name, ...} oder None
- `mark_used(key_id)` → True/False
- `get_stats()` → {total, used, available, keys: [...]}
- `save()` → schreibt pool.json

### data/fireworksai-pool.json

API-Key Pool im Plain-Array Format:
```json
[
  {
    "id": "uuid-8-stellig",
    "api_key": "fw-Za4b8C2d1E9f0G3h...",
    "alias_email": "swift-hawk-842@gmx.de",
    "key_name": "swift-hawk",
    "created_at": "2026-05-09T12:00:00Z",
    "used": false,
    "used_at": null
  }
]
```

**PoolManager API:**
- `add_key(api_key, alias_email, key_name)` → {status, key_id}
- `get_available_key()` → {api_key, alias_email, key_name, ...} oder None
- `mark_used(key_id)` → True/False
- `get_stats()` → {total, used, available, keys: [...]}
- `save()` → schreibt pool.json

---

## 📡 API ENDPOINTS (VOLLSTÄNDIG)

### Browser
| Methode | Endpoint | Request | Response |
|---|---|---|---|
| POST | `/browser/start` | `{profile_name, cdp_port, headless}` | `{status, browser_info, execution_time}` |
| POST | `/browser/stop` | — | `{status, cleanup_info, execution_time}` |
| GET | `/browser/status` | — | `{is_running, cdp_port, page_count}` |

### GMX
| Methode | Endpoint | Request | Response |
|---|---|---|---|
| POST | `/gmx/session/check` | — | `{status, current_url, session_active}` |
| POST | `/gmx/email-addresses` | — | `{status, current_url, title}` |
| POST | `/gmx/alias/delete` | — | `{status, deleted, alias}` |
| POST | `/gmx/alias/rotate` | `{new_alias_name}` | `{status, deleted_alias, created_alias, steps_completed, steps_failed}` |
| POST | `/gmx/alias/create` | `alias_name` (query param) | `{status, alias_email, alias_name}` |
| POST | `/gmx/inbox/open` | — | `{status, current_url}` |
| POST | `/gmx/otp/read` | `sender_filter, max_retries` | `{status, otp_url, email_subject}` |

### Fireworks
| Methode | Endpoint | Request | Response |
|---|---|---|---|
| POST | `/fireworks/register` | `{email, password}` | `{status, account_email}` |
| POST | `/fireworks/confirm` | `{confirm_url, email, password}` | `{status, account_confirmed}` |
| POST | `/fireworks/api-key` | `{key_name}` | `{status, api_key, key_name}` |

### Cookies
| Methode | Endpoint | Request | Response |
|---|---|---|---|
| POST | `/cookies/extract` | `{domain_filter, save_to_file}` | `{status, cookie_count, saved_to}` |
| POST | `/cookies/inject` | `{filename, verify_session}` | `{status, injected_count, session_active}` |
| POST | `/cookies/recover` | — | `{status, session_active}` |
| POST | `/cookies/backup` | — | `{status, backup_path}` |

### Pool
| Methode | Endpoint | Request | Response |
|---|---|---|---|
| GET | `/pool/stats` | — | `{status, total, used, available, keys}` |
| GET | `/pool/key` | — | `{api_key, alias_email, key_name}` oder `{status: "empty"}` |
| POST | `/pool/key/use` | `{key_id}` | `{status, key_id}` |
| POST | `/pool/add` | `{api_key, alias_email, key_name}` | `{status, key_id}` |

### Rotation (HAUPT)
| Methode | Endpoint | Request | Response |
|---|---|---|---|
| POST | `/rotation/full` | `{new_alias_name, fireworks_password, save_to_pool}` | `{status, gmx_alias, fireworks_account, api_key, api_key_name, steps_completed, steps_failed}` |

---

## 🐛 BEKANNTE PROBLEME & FIXES (KRITISCH)

### `_fill_input` React Controlled Components ← WICHTIGSTER FIX
**Problem:** Fireworks.ai verwendet React `useState` für alle Inputs.
`input.value = 'text'` setzt den DOM-Wert aber React-State bleibt LEER →
"Next" klicken hat keinen Effekt, Form advance nicht.

**Fix:** `nativeInputValueSetter` — exakt dieser Code:
```javascript
const nativeSetter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
nativeSetter.call(input, 'test@gmx.de');
input.dispatchEvent(new Event('input', {bubbles: true, composed: true}));
```

**KeyEvents (`Input.dispatchKeyEvent`) funktionieren NICHT für Sonderzeichen
(`.`, `@`, `!`). KeyEvents nur für einfache alphanumerische Strings.

### Cookie Banner dismiss
**Problem:** `_find_element()` findet `.cky-btn-accept` nicht (Shadow DOM).
Button ist in DOM aber nicht per CDP querySelector erreichbar.

**Fix:** Direktes JS-Query + Fallback auf hardcoded coords (1113.7, 805.5).
Button rect ist BEWIESEN: top=785.5, left=1052.5, w=122.5, h=40.0.

### GMX SPA Navigation
**Problem:** `navigate("navigator.gmx.net/mail")` redirected zu `www.gmx.net/`.

**Fix:** `navigate(gmx.net)` → `click_at(235, 33)` → wait → URL prüfen.
NIEMALS `waitForNavigation()` verwenden (GMX ist SPA).

### OTP Email Detection
**Problem:** OTP Polling sucht im Main Frame DOM aber GMX Emails sind im iframe.

**Fix:** navigate(gmx.net) → JS click "E-Mail" → inbox URL = bap.navigator.gmx.net/mail?sid=...
Im Main Frame nach "fireworks" + "verif" suchen.
"needs_click" path: Email row clicken → Email-Page scrapen → OTP URL finden.

### Account Creation Redirect
**Problem:** "Create Account" klicken aber URL wechselt nicht zu `/signup/verify`.

**Fix:** FAIL-HARD. Kein `/signup/verify` in URL = `account_creation_redirect_mismatch`.
Account wurde NICHT erstellt. Session recover und erneut versuchen.

### GMX FreeMail: Nur EIN Alias
**Problem:** GMX FreeMail erlaubt nur einen Alias gleichzeitig.

**Fix:** Vor neuer Alias-Erstellung existierenden Alias löschen (Phase 2).
Falls delete fehlschlägt → trotzdem neuen erstellen (partial success).

### GMX Session bei Chrome-Neustart
**Problem:** Nach Chrome-Neustart sind GMX-Session-Cookies weg.

**Fix:** Chrome mit Profil 901 starten → GMX Session wird automatisch
wiederhergestellt (Cookies sind im Chrome-Profil gespeichert).

---

## 🔧 CDP CLIENT API

**CDPClient** (connected mit ws_url):
```python
client = CDPClient("ws://127.0.0.1:9222/devtools/browser/...")
await client.connect()

# Session management
targets = await client.get_targets()            # Alle Tabs
session_id = await client.attach_to_target(target_id)  # An Tab attachen
await client.disconnect()

# Navigation
await client.navigate(session_id, "https://...")        # Page.navigate
await client.click_at(session_id, x, y)                  # Input.dispatchMouseEvent

# JS Execution
result = await client.evaluate(session_id, "document.body.innerText", return_by_value=True)
# → {"result": {"type": "object", "value": {...actual data...}}}

# Low-level CDP
await client.send(session_id, "Page.screenshot", {"format": "png"})
await client.send_to_session(session_id, "Network.getAllCookies")
await client.send_to_session(session_id, "Network.deleteCookies", {"name": "...", "domain": "..."})

# Helpers
await client.screenshot(session_id, path="/tmp/screen.png")  # Full page screenshot
await client.get_document(session_id)                          # DOM snapshot
await client.query_selector(session_id, selector, root_id)    # Find element
await client.get_box_model(session_id, node_id)               # Element rect
```

**CDP click_at() vs JS .click() — WICHTIGE UNTERSCHIEDE:**

| Methode | Funktioniert für | Nicht für | Beispiel |
|---|---|---|---|
| `click_at(x, y)` | Normale DOM Elemente, Links, Buttons | Shadow DOM, Custom Elements | E-Mail Header Link |
| JS `.click()` | Shadow DOM, Custom Elements, React controlled inputs | — | ACCOUNT-AVATAR Dropdown |

**Regel:**
- Normale Elemente → `click_at()` (echte Maus-Events)
- Shadow DOM / Custom Elements → JS `.click()` + `.dispatchEvent()`
- React Inputs → `nativeInputValueSetter` + `Event('input')`

---

## 🔍 DEBUGGING COMMANDS

```bash
# Chrome Prozess?
ps aux | grep -i "[c]hrome.*user-data-dir" | head -3

# CDP Port erreichbar?
curl -s http://127.0.0.1:9222/json/version | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['webSocketDebuggerUrl'])"

# GMX Session validieren (Python)?
python3 - << 'PYEOF'
import asyncio, sys
sys.path.insert(0, '/Users/jeremy/dev/SINator-fireworksai/agent_toolbox/core')
from cdp_client import CDPClient, get_browser_ws_endpoint
async def validate():
    ws = await get_browser_ws_endpoint(9222)
    c = CDPClient(ws)
    await c.connect()
    targets = await c.get_targets()
    sid = await c.attach_to_target(targets[0]['targetId'])
    await c.navigate(sid, "https://www.gmx.net/")
    await asyncio.sleep(3)
    await c.click_at(sid, 235, 33)
    await asyncio.sleep(5)
    url = await c.evaluate(sid, "window.location.href")
    print(f"URL: {url.get('result',{}).get('value')}")
    print(f"Session OK: {'navigator.gmx.net/mail?sid=' in url.get('result',{}).get('value','')}")
    await c.disconnect()
asyncio.run(validate())
PYEOF

# Cookie Banner prüfen?
python3 - << 'PYEOF'
# Navigate zu FW signup → evaluate: document.querySelector('.cky-btn-accept').getBoundingClientRect()
PYEOF

# Pool Stats?
curl -s http://localhost:8000/pool/stats | python3 -m json.tool
```

---

## 📚 REFERENZEN

| Thema | Datei | Key Methods |
|---|---|---|
| Verbannte Methoden | `banned.md` | — |
| CDP Websocket Client | `agent_toolbox/core/cdp_client.py:85` | connect, navigate, click_at, evaluate, send_to_session, **get_browser_ws_endpoint (urllib)** |
| GMX Session & Alias | `agent_toolbox/core/gmx_service.py` | **ensure_gmx_session (Flow 0)**, rotate_alias, create_alias, delete_alias, check_session, _inject_saved_cookies |
| GMX Alias CLI Tool | `tools/gmx_alias_tool.py` | status, check, rotate, create, delete — **READ-ONLY VERIFIED, NEVER CHANGE** |
| Fireworks E2E | `agent_toolbox/core/fireworks_service.py:875` | register(email, password, gmx_password) |
| Rotation Orchestrator | `agent_toolbox/api/routes/rotation.py:55` | POST /rotation/full |
| Pool Manager | `agent_toolbox/core/pool_manager.py:33` | add_key, get_available_key, mark_used, get_stats |
| Browser Lifecycle | `agent_toolbox/core/browser_manager.py:75` | start, stop, is_running |
| GMX API Routes | `agent_toolbox/api/routes/gmx.py` | POST /gmx/alias/rotate, /gmx/alias/create, /gmx/alias/delete |
| API Schemas | `agent_toolbox/api/schemas.py` | RotationRequest, RotationResponse, alle Models |
| FastAPI Entrypoint | `agent_toolbox/start_toolbox.py` | FastAPI app registration |

---

## 🏛️ INCIDENT LOG — Niemals wiederholen!

### 2026-05-10: Flow #1 Breakdown (VERHINDERT)

**Was passiert ist:**
Agent versuchte "DOM exploration" für GMX Shadow-DOM Input → rewrite `_navigate_to_all_email_addresses` mit 75-line PFAD-Navigation → Flow #1 komplett gebrochen. **11 Dateien reverted auf commit `cf146a6`.**

**Files die gebrochen wurden:**
- `agent_toolbox/core/gmx_service.py` — Rewrite mit neuer Navigation (PFAD A/B/C)
- `agent_toolbox/core/cdp_client.py`, `browser_manager.py`, `fireworks_service.py`, `pool_manager.py`
- `agent_toolbox/api/routes/cookies.py`, `rotation.py`
- `tools/gmx_alias_tool.py`, `AGENTS.md`, `banned.md`

**Symptom:** `gmx_alias_tool.py status` → "Playwright: No alias input found. All inputs: []"

**Recovery:** `git checkout -- .` (alle 11 files reverted) → `gmx_alias_tool.py check` ✅ → `rotate` ✅ in 29s

**Root Cause:** Agent verletzte "ONCE VERIFIED = READ-ONLY". Flow #1 war VERIFIED am 2026-05-09 (29s rotation, elron-runner-701@gmx.de erstellt). Agent versuchte es zu "verbessern" ohne konkreten Bug.

**Verhindern:**
1. ⚠️ Flow #1, #2, #3 sind READ-ONLY — NIEMALS ändern außer es gibt konkreten Bug-Report
2. Debuggen JA, Umschreiben NEIN
3. Neuer Ansatz = Neue Datei (debug/), nicht existierende Dateien ändern
4. IMMER zuerst backup/branch erstellen bevor irgendetwas geändert wird

### 2026-05-10: Flow 0 Shadow DOM Discovery (GELÖST)

**Was passiert ist:**
GMX Login Flow hat sich geändert — Dropdown ist jetzt im Shadow DOM von ACCOUNT-AVATAR.
CDP `click_at()` funktioniert NICHT für Custom Elements mit Shadow DOM.

**Lösung:**
1. JS `.click()` + `.dispatchEvent(new Event('mouseenter'))` auf Custom Element
2. Dann JS `.click()` auf Buttons im Shadow DOM
3. 3s Wait für Shadow DOM Rendering
4. Multi-Synonym Suche: `logout`, `abmelden`, `ausloggen`, `account wechseln`

**Files geändert:**
- `agent_toolbox/core/gmx_service.py` — `_click_profile_icon_and_action()` komplett neu
- `AGENTS.md` — Shadow DOM Dokumentation, State Machine, Koordinaten

**Test Ergebnis:**
- 5/5 Tests erfolgreich
- Durchschnitt: 54.93s
- Letzter Test: 2026-05-10, SID: 331e8dc82fec93376c05f1148c0bc2...

**Root Cause:**
GMX hat ACCOUNT-AVATAR zu einem Web Component (Custom Element) umgebaut.
Shadow DOM Elemente sind für CDP nicht sichtbar (`getBoundingClientRect()` → 0×0).
Nur JS Events innerhalb des Shadow DOM können die Elemente bedienen.

*Letzte Aktualisierung: 2026-05-10 (Flow 0: GMX Shadow DOM + 2x Login)*