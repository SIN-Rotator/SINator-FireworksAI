# 🚫 BANNED — Verbotene Methoden & Patterns

> **NIEMALS** diese Methoden verwenden. Sie führen zu Chrome-Start-Fehlern, CDP-Verbindungsproblemen oder Session-Verlust.

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
