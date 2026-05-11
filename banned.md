# 🚫 BANNED — Verbotene Methoden & Patterns

> **NIEMALS** diese Methoden verwenden. Sie führen zu Chrome-Start-Fehlern, CDP-Verbindungsproblemen oder Session-Verlust.

---

## ❌ BANNED: AX tree_line als element_index nutzen (2026-05-11)

**Problem:** AX-Tree output format:
```
[140] - [123] AXCheckBox "Flexible capacity for production"
  ^^^   ^^^^
  |     +---> element_index = 123 (RICHTIG!)
  +---> tree_line = 140 (FALSCH!)
```
Klickt man `element_index: 140` wird das WONG element geklickt (AXStaticText ""), nicht die Checkbox!

**Banned:** Regex `\[(\d+)\]` extrahiert tree_line statt element_index!
**Fix:** Immer `parts[1].split(']')[0]` für secondary ID nutzen (siehe AGENTS.md Regel 1).

---

## ❌ BANNED: Chrome mit Default user-data-dir starten

```bash
# FALSCH — Chrome verweigert CDP mit diesem Pfad!
chrome --user-data-dir="/Users/jeremy/Library/Application Support/Google/Chrome" --remote-debugging-port=9222
```

**Fehlermeldung:**
```
DevTools remote debugging requires a non-default data directory.
```

**Warum gebannt:** Chrome blockiert `--remote-debugging-port` wenn `--user-data-dir` auf den **Standard-Pfad** zeigt (`~/Library/Application Support/Google/Chrome`). Das ist eine Sicherheitsbeschränkung.

---

## ❌ BANNED: Nur Profil-Subfolder kopieren (ohne Local State)

```bash
# FALSCH — Chrome erstellt ein NEUES Profil statt Profile 901 zu verwenden!
cp -R "/Users/jeremy/Library/Application Support/Google/Chrome/Profile 901" /tmp/my-profile
chrome --user-data-dir=/tmp/my-profile --remote-debugging-port=9222
```

**Symptom:** Chrome startet zwar mit CDP, aber erstellt ein **neues leeres Profil** (Default). Alle Sessions, Cookies, Login-Daten sind weg.

**Warum gebannt:** Chrome braucht die `Local State` Datei im Root von `user-data-dir` um zu wissen welche Profile existieren. Ohne `Local State` → Chrome denkt es ist ein neues Profil → erstellt Default.

---

## ❌ BANNED: Cookie-Injection in fremdes Profil

```javascript
// FALSCH — Cookies sind profilgebunden verschlüsselt!
const cdp = await page.createCDPSession();
await cdp.send('Network.setCookies', { cookies: savedCookies });
```

**Symptom:** `page.setCookie()` oder CDP `Network.setCookies` in ein **frisches** Profil funktioniert nicht. GMX-Cookies sind an den **originalen Profil-Pfad** gebunden (macOS Keychain-Verschlüsselung).

**Warum gebannt:** Chrome verschlüsselt Cookies mit einem Schlüssel der vom `user-data-dir` Pfad abhängt. Cookies aus Profil A können nicht in Profil B injiziert werden.

---

## ❌ BANNED: puppeteer.launch() statt spawn()

```javascript
// FALSCH — puppeteer.launch() setzt --enable-automation!
const browser = await puppeteer.launch({ headless: false });
```

**Symptom:** GMX's Bot-Detection (DataDome/Akamai) erkennt `--enable-automation` Flag sofort → CAPTCHA nach Email-Eingabe → Automation blockiert.

**Warum gebannt:** `puppeteer.launch()` fügt automatisch Flags hinzu die Anti-Bot-Systeme erkennen. `child_process.spawn()` umgeht das.

---

## ❌ BANNED: waitForNavigation() bei auth.gmx.net

```javascript
// FALSCH — auth.gmx.net nutzt JS-Transitions, keine Page-Navigation!
await page.click('#login-button');
await page.waitForNavigation(); // Hängt ewig!
```

**Symptom:** `waitForNavigation()` timeout weil auth.gmx.net **keine** neue Seite lädt — der Login erfolgt via JavaScript (SPA-Transition).

**Warum gebannt:** GMX's auth.gmx.net ist eine Single-Page-Application. Nach Button-Klick ändert sich die URL nicht, nur der DOM-Inhalt.

---

## ❌ BANNED: Symlink für user-data-dir

```bash
# FALSCH — Symlink bricht Cookie-Entschlüsselung!
ln -s "/Users/jeremy/Library/Application Support/Google/Chrome/Profile 901" /tmp/chrome-profile
chrome --user-data-dir=/tmp/chrome-profile --remote-debugging-port=9222
```

**Symptom:** Chrome startet, aber Cookies sind unlesbar (verschlüsselt mit original Pfad).

**Warum gebannt:** macOS Keychain-Verschlüsselung bindet Cookies an den **realen** Pfad. Symlinks werden nicht aufgelöst für den Decryption-Key.

---

## ❌ BANNED: READ-ONLY Code ändern (Flow #1, #2, #3)

```python
# FALSCH — READ-ONLY Code anfassen!
# Flow #1 (gmx_service.py), Flow #2 (fireworks_service.py), Flow #3 (OTP extraction)
# sind VERIFIED und funktionieren. NIE ändern außer es gibt einen konkreten Bug-Report.

# Breaked am 2026-05-10: Agent versuchte "DOM exploration" für Shadow-DOM input
# → rewrite _navigate_to_all_email_addresses mit 75-line PFAD-Navigation
# → Flow #1 komplett gebrochen
# → 11 files reverted auf commit cf146a6 (alles verloren!)
```

**Symptom:** Nach Änderung funktioniert die Navigation nicht mehr. GMX-Session geht verloren, Alias-Rotation schlägt fehl, "Input nicht gefunden" Fehler.

**Warum gebannt:** Flow #1, #2, #3 wurden mühsam getestet und verifiziert. Jede Änderung — selbst "kleine Verbesserungen" — kann den funktionierenden Flow brechen. Der Agent verlor am 2026-05-10 6 Tage Arbeit durch einen Rewrite-Versuch.

**Regel:** ONCE VERIFIED = READ-ONLY. Nur ändern wenn: (a) konkreter Bug-Report, (b) GMX die UI ändert, (c) neue Use-Case erfordert es.

---

## ✅ KORREKTE METHODE (siehe AGENTS.md für Details)

```bash
# 1. GESAMTES user-data-dir kopieren (inkl. Local State!)
TEMP_DIR="/tmp/sinator-chrome-$(date +%s)"
mkdir -p "$TEMP_DIR"
cp "/Users/jeremy/Library/Application Support/Google/Chrome/Local State" "$TEMP_DIR/"
cp -R "/Users/jeremy/Library/Application Support/Google/Chrome/Profile 901" "$TEMP_DIR/"

# 2. Chrome mit kopiertem Profil + profile-directory Flag starten
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="$TEMP_DIR" \
  --profile-directory="Profile 901" \
  --remote-debugging-port=9222 \
  --no-first-run \
  --no-default-browser-check 2>&1 &

# 3. Auf CDP warten
sleep 8
curl -s http://127.0.0.1:9222/json/version
```

```javascript
// Node.js: puppeteer.connect() zum laufenden Chrome
const puppeteer = require('puppeteer');
const wsUrl = await getWebSocketUrl(9222);
const browser = await puppeteer.connect({ browserWSEndpoint: wsUrl });
const pages = await browser.pages();
const page = pages[0]; // Bereits eingeloggt in GMX!
```

---

## ❌ BANNED: CDP JavaScript für Button/Link/Checkbox Klicks

```python
# FALSCH — CDP evaluate für normale Klicks!
await cdp.evaluate(sid, "document.querySelector('button').click()")
```

**Warum gebannt:** CUA driver kann ALLE interaktiven Elemente klicken. CDP evaluate:
- Läuft im falschen Kontext (Extension statt Page)
- Macht uns abhängig von DOM-Struktur-Änderungen
- Ist langsamer als CUA für einfache Klicks

**Regel:** CUA für Buttons, Links, Checkboxes, MenuItems, PopUpButtons.
CDP NUR für: React Inputs, Tab Management, Cookie Inspection.

---

## ❌ BANNED: CUA type_text auf React Inputs

```bash
# FALSCH — CUA type_text funktioniert NICHT für React!
echo '{"pid": 123, "window_id": 456, "element_index": 94}' | cua-driver call type_text '{"text": "mein-email@gmx.de"}'
# Result: "Missing ... Name!" Fehler!
```

**Warum gebannt:** React controlled inputs nutzen `useState` und ignorieren CUA keyboard events. Der DOM-Wert wird gesetzt aber React-State bleibt LEER.

**Fix:** CDP nativeInputValueSetter verwenden (siehe AGENTS.md Regel 3).

---

## ❌ BANNED: lightmailer-bs.gmx.net URLs

```bash
# FALSCH — HTTP 500 errors!
curl https://lightmailer-bs.gmx.net/mailbody/123456789/false
# → "Diese Seite funktioniert nicht HTTP ERROR 500"
```

**Warum gebannt:** lightmailer URLs werfen 500er errors. GMX Extension ist der einzig erlaubte Weg für Email-Zugriff.

**Fix:** GMX MailCheck Extension öffnen → Email klicken (siehe AGENTS.md Regel 4).

---

## ❌ BANNED: Nach Klick NICHT scannen

```bash
# FALSCH — Klick ohne Scan nachher!
echo '...' | cua-driver call click
echo 'nächste aktion'  # FEHLER! Kein Scan dazwischen!
```

**Warum gebannt:** Nach jedem Klick kann sich die UI ändern (Modal öffnet, Fehler erscheint, Element verschiebt). Ohne Scan weiß man nicht ob der Klick funktioniert hat.

**Fix:** Immer SCAN → KLICK → SCAN → Ergebnis verifizieren.

---

## ❌ BANNED: PopUpButton nicht mit set_value behandeln

```bash
# FALSCH — Nach Popup-Warnung wieder click verwenden!
echo '...' | cua-driver call click
# → "This is a popup/select button. Use set_value."
# NOCHMAL click = FEHLER!
```

**Warum gebannt:** CUA warnt dass es ein PopUpButton ist. Bei erneutem click wird das falsche Element (Image/StaticText) geklickt.

**Fix:** Nach "This is a popup/select button" → set_value verwenden:
```bash
echo '{"pid": 123, "window_id": 456, "element_index": 74, "value": "Create API Key"}' | cua-driver call set_value
```
