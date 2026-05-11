# ANTI-LEARN.md — Was NICHT funktioniert

> **Diese Methoden NIEMALS verwenden! Sie führen zu Fehlern!**

---

## ❌ CUA type_text auf React Inputs

```bash
# FALSCH — CUA type_text funktioniert NICHT für React!
echo '{"pid": 123, "window_id": 456, "element_index": 94}' | cua-driver call type_text '{"text": "mein-email@gmx.de"}'
# Result: "Missing ... Name!" Fehler!
```

**Warum:** React controlled inputs nutzen `useState`. CUA keyboard events setzen DOM-Wert aber React-State bleibt LEER.

**Lösung:** CDP nativeInputValueSetter verwenden.

---

## ❌ lightmailer-bs.gmx.net URLs

```bash
# FALSCH — HTTP 500 errors!
curl https://lightmailer-bs.gmx.net/mailbody/123456789/false
# → "Diese Seite funktioniert nicht HTTP ERROR 500"
```

**Warum:** GMX hat diese URLs deaktiviert oder sie sind überlastet.

**Lösung:** GMX MailCheck Extension nutzen:
```
chrome-extension://camnampocfohlcgbajligmemmabnljcm/pages/mail-panel.html
```

---

## ❌ CDP evaluate im Extension Context

```python
# FALSCH — läuft im falschen Kontext!
await cdp.evaluate(sid, "document.querySelector('button').click()")
# → ReferenceError: document is not defined
```

**Warum:** CDP evaluate läuft im Extension-Kontext, nicht im Page-Kontext.

**Lösung:** CUA click für Buttons/Links verwenden. CDP nur für React Inputs.

---

## ❌ Profil kopieren nach /tmp

```bash
# FALSCH — Session geht verloren!
cp -R "/Users/jeremy/Library/Application Support/Google/Chrome/Profile 901" /tmp/my-profile
chrome --user-data-dir=/tmp/my-profile --remote-debugging-port=9222
```

**Warum:** macOS Keychain-Verschlüsselung bindet Cookies an Original-Pfad.

**Lösung:** Original-Profil 901 direkt nutzen:
```bash
--user-data-dir="/Users/jeremy/Library/Application Support/Google/Chrome"
--profile-directory="Profile 901"
```

---

## ❌ pkill -9 für Chrome

```bash
# FALSCH — zerstört unflushed SQLite!
pkill -9 -f "Google Chrome"
# → GMX Session tot!
```

**Warum:** SIGKILL beendet Chrome ohne SQLite-Flush. GMX Session-Cookies gehen verloren.

**Lösung:** SIGTERM verwenden:
```bash
kill $(ps aux | grep "[c]hrome.*user-data-dir" | awk '{print $2}' | head -1)
```

---

## ❌ Nach Klick nicht scannen

```bash
# FALSCH — Klick ohne Scan nachher!
echo '...' | cua-driver call click
echo 'nächste aktion'  # FEHLER!
```

**Warum:** Nach jedem Klick kann sich die UI ändern (Modal, Fehler, Element verschiebt).

**Lösung:** Immer SCAN → KLICK → SCAN → Ergebnis verifizieren.

---

## ❌ PopUpButton nochmal clicken nach Warnung

```bash
# FALSCH — nochmal click nach Warnung!
echo '...' | cua-driver call click
# → "This is a popup/select button. Use set_value."
echo '...' | cua-driver call click  # FEHLER!
```

**Warum:** CUA warnt dass es ein PopUpButton ist. Nochmal click klickt das falsche Element (Image/StaticText).

**Lösung:** Nach Warnung set_value verwenden:
```bash
echo '{"pid": 123, "window_id": 456, "element_index": 74, "value": "Option"}' | cua-driver call set_value
```

---

## ❌ Tree_line als element_index nutzen

```python
# FALSCH — extrahiert tree_line statt element_index!
regex = r'\[(\d+)\]'
match = re.search(regex, line)  # Gibt 140, nicht 123!
```

**Warum:** AX-Tree Format ist `[tree_line] - [element_index]`
Man muss die SECONDARY ID (nach `] - [`) nehmen.

**Lösung:**
```python
parts = stripped.split('] - [')
sec_id = parts[1].split(']')[0]  # Gibt 123
```

---

## ❌ waitForNavigation() bei GMX

```javascript
# FALSCH — GMX ist SPA, keine Page-Navigation!
await page.click('#login-button');
await page.waitForNavigation(); // Hängt ewig!
```

**Warum:** GMX auth.gmx.net ist eine Single-Page-Application. URL ändert sich nicht.

**Lösung:** Auf DOM-Elemente warten statt auf Navigation.

---

## ❌ READ-ONLY Code ändern

```python
# FALSCH — Flow #1, #2, #3 sind VERIFIED!
# gmx_service.py, fireworks_service.py, gmx_alias_tool.py
# NICHT ÄNDERN außer konkreter Bug-Report!
```

**Warum:** 2026-05-10: Agent änderte `_navigate_to_all_email_addresses`
→ Flow #1 komplett gebrochen
→ 11 Dateien reverted auf commit cf146a6

**Lösung:** Neuer Ansatz = Neue Datei (debug/), nicht existierende ändern.

---

## ❌ Symlink für user-data-dir

```bash
# FALSCH — bricht Cookie-Entschlüsselung!
ln -s "/Users/jeremy/Library/Application Support/Google/Chrome" /tmp/chrome-profile
chrome --user-data-dir=/tmp/chrome-profile --remote-debugging-port=9222
```

**Warum:** macOS Keychain-Verschlüsselung bindet Cookies an realen Pfad, nicht Symlink.

---

## ❌ puppeteer.launch() statt spawn()

```javascript
# FALSCH — setzt --enable-automation Flag!
const browser = await puppeteer.launch({ headless: false });
# → GMX Bot-Detection erkennt Automation sofort!
```

**Lösung:** Chrome direkt starten ohne puppeteer für GMX.

---

*Letzte Aktualisierung: 2026-05-11*