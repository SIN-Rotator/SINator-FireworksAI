# 📋 AGENTS.md — SINator Fireworks AI Rotator

## Projekt-Übersicht
**Zweck:** Automatisierte Erstellung von GMX E-Mail-Aliasen → Fireworks AI Account-Registrierung → API-Key-Pool-Rotation.

**Architektur:** Chrome Subprocess + CDP + puppeteer.connect() mit Profil-Kopie für Session-Persistenz.

---

## 🚨 CRITICAL: Chrome Start Methode

### WARUM NICHT Standard user-data-dir?
Chrome verweigert `--remote-debugging-port` mit Default-Pfad:
```
DevTools remote debugging requires a non-default data directory.
```

### WARUM NICHT nur Profil-Subfolder kopieren?
Ohne `Local State` Datei erstellt Chrome ein NEUES leeres Profil → alle Sessions weg.

### ✅ KORREKTE METHODE:
```bash
# 1. GESAMTES user-data-dir vorbereiten:
TEMP_DIR="/tmp/sinator-chrome-$(date +%s)"
mkdir -p "$TEMP_DIR"
cp "/Users/jeremy/Library/Application Support/Google/Chrome/Local State" "$TEMP_DIR/"
cp -R "/Users/jeremy/Library/Application Support/Google/Chrome/Profile 73" "$TEMP_DIR/"

# 2. Chrome mit kopiertem Profil starten:
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="$TEMP_DIR" \
  --profile-directory="Profile 73" \
  --remote-debugging-port=9222 \
  --no-first-run \
  --no-default-browser-check 2>&1 &

# 3. CDP prüfen:
sleep 8
curl -s http://127.0.0.1:9222/json/version
```

### puppeteer.connect() Pattern:
```javascript
const puppeteer = require('puppeteer');

function getWebSocketUrl(port) {
  return new Promise((resolve, reject) => {
    const req = http.get(`http://127.0.0.1:${port}/json/version`, res => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(body).webSocketDebuggerUrl); }
        catch (e) { reject(new Error(`Invalid JSON: ${body}`)); }
      });
    });
    req.on('error', reject);
    req.setTimeout(5000, () => { req.destroy(); reject(new Error('CDP timeout')); });
  });
}

async function waitForCdp(port, maxRetries = 15) {
  for (let i = 0; i < maxRetries; i++) {
    try { return await getWebSocketUrl(port); }
    catch { await new Promise(r => setTimeout(r, 1000)); }
  }
  throw new Error(`CDP nicht erreichbar nach ${maxRetries}s auf Port ${port}`);
}

// Usage:
const wsUrl = await waitForCdp(9222);
const browser = await puppeteer.connect({ browserWSEndpoint: wsUrl });
const page = (await browser.pages())[0];
// page ist bereits in GMX eingeloggt (Session aus kopiertem Profil)!
```

---

## 📁 Projekt-Struktur

```
SINator-fireworksai/
├── AGENTS.md              ← Diese Datei (Architektur-Doku)
├── banned.md              ← Verbotene Methoden & Patterns
├── .env                   ← Konfiguration (GMX-Credentials, Delays, CDP-Port)
├── package.json           ← Dependencies (puppeteer-extra, stealth-plugin)
├── src/
│   ├── browser.js         ← Chrome-Start mit Stealth-Flags, CDP-Setup
│   ├── gmxHandler.js      ← GMX-Login, Alias-Erstellung/Löschung
│   ├── fireworksHandler.js← Fireworks AI Registrierung, API-Key-Erstellung
│   ├── index.js           ← Orchestrator (once/loop Modus)
│   ├── logger.js          ← Winston Logging (Console + File)
│   ├── nameGenerator.js   ← Alias-Namen-Generator (32×32 Kombinationen)
│   └── pool.js            ← API-Key-Pool-Speicher (./data/fireworksai-pool.json)
└── data/
    ├── gmx-cookies.json   ← Gespeicherte GMX-Cookies (23 Entries)
    └── fireworksai-pool.json ← Generierte API-Keys
```

---

## 🔑 Wichtige Pfade & Credentials

| Item | Wert |
|------|------|
| Chrome Binary | `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` |
| Source Profil | `/Users/jeremy/Library/Application Support/Google/Chrome/Profile 73` |
| Local State | `/Users/jeremy/Library/Application Support/Google/Chrome/Local State` |
| CDP Port | `9222` |
| GMX Email | `zukunftsorientierte.energie@gmail.com` |
| GMX Password | `ZOE.jerry2024` |
| GMX Alias Page | `https://navigator.gmx.net/mail_settings/email_addresses` |
| GMX Inbox | `https://navigator.gmx.net/mail` |
| Fireworks AI | `https://app.fireworks.ai` |

---

## ⚠️ Bekannte Probleme & Workarounds

### GMX Login CAPTCHA
**Problem:** GMX zeigt nach Email-Eingabe im Login-Flow einen CAPTCHA.
**Workaround:** Profil-Kopie → Session ist bereits aktiv → kein Login nötig.

### auth.gmx.net JavaScript-Transitions
**Problem:** `waitForNavigation()` funktioniert nicht (SPA, keine Page-Reloads).
**Workaround:** Auf DOM-Elemente warten statt auf Navigation.

### GMX FreeMail: Nur EIN Alias
**Problem:** GMX FreeMail erlaubt nur einen Alias gleichzeitig.
**Workaround:** Vor neuer Alias-Erstellung existierenden Alias löschen.

### Cookie-Verschlüsselung (macOS Keychain)
**Problem:** Cookies sind an `user-data-dir` Pfad gebunden.
**Workaround:** Profil kopieren (inkl. Local State) → Chrome nutzt kopierte Cookies.

---

## 🚀 Flow: Alias-Erstellung

1. **Profil kopieren** → Local State + Profile 73 nach /tmp
2. **Chrome starten** → `--user-data-dir=/tmp/... --profile-directory="Profile 73" --remote-debugging-port=9222`
3. **CDP verbinden** → `puppeteer.connect({ browserWSEndpoint: wsUrl })`
4. **GMX öffnen** → `navigator.gmx.net/mail_settings/email_addresses` (bereits eingeloggt!)
5. **Existierenden Alias löschen** (falls vorhanden)
6. **Neuen Alias erstellen** → `{adjektiv}-{substantiv}@gmx.de`
7. **Fireworks AI registrieren** → mit neuem Alias
8. **API-Key speichern** → `./data/fireworksai-pool.json`
9. **Chrome beenden** → Temp-Profile aufräumen

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

# Falls ja: Beenden
pkill -f "Google Chrome"

# Dann neu starten mit kopiertem Profil
```

### CDP-Port nicht erreichbar?
```bash
# Port prüfen:
lsof -i :9222

# Falls belegt: Anderen Port verwenden
# In .env: CDP_PORT=9223
```

### GMX Session abgelaufen?
1. Chrome mit kopiertem Profil starten (siehe oben)
2. Manuell bei GMX einloggen: `https://navigator.gmx.net/mail`
3. Cookies extrahieren via `page.cookies()`
4. Cookies speichern für zukünftige Runs

---

## 📚 Referenzen

- **banned.md** — Liste verbotener Methoden
- **src/browser.js** — Chrome-Start mit Stealth-Flags
- **src/gmxHandler.js** — GMX-Login & Alias-Management
- **src/fireworksHandler.js** — Fireworks AI Registrierung
