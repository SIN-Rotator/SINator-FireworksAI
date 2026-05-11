# FIX.md — Fixes für bekannte Probleme

> **Probleme die auftreten können und ihre Lösungen.**

---

## 🔧 "Missing API Key Name!" Fehler

**Problem:** TextField zeigt "Missing API Key Name!" nach Eingabe.

**Ursache:** CUA type_text funktioniert NICHT für React controlled inputs.

**Fix:** CDP nativeInputValueSetter verwenden:

```python
await cdp.send_to_session(sid, "Runtime.evaluate", {
    "expression": """
        (function() {
            const input = document.querySelector('input[name*="name"]');
            const nativeSetter = Object.getOwnPropertyDescriptor(
                HTMLInputElement.prototype, 'value').set;
            nativeSetter.call(input, 'blaze-scorpion-746');
            input.dispatchEvent(new Event('input', {bubbles: true, composed: true}));
            return 'set';
        })()
    """,
    "returnByValue": True
})
```

---

## 🔧 PopUpButton Menu erscheint nicht

**Problem:** Nach Click auf PopUpButton passiert nichts.

**Fix:** 
1. Nochmal click → Warnung "This is a popup/select button"
2. `set_value` verwenden:

```bash
echo '{"pid": 123, "window_id": 456, "element_index": 74, "value": "Option"}' | cua-driver call set_value
```

---

## 🔧 GMX Session TOT

**Problem:** GMX zeigt nicht eingeloggt nach Chrome-Neustart.

**Fix:**
1. Chrome beenden: `kill $(ps aux | grep "[c]hrome.*user-data-dir" | awk '{print $2}' | head -1)`
2. Chrome neu starten mit Original-Profil 901
3. Session validieren: GMX Homepage → "E-Mail" click → URL prüfen

---

## 🔧 lightmailer-bs.gmx.net HTTP 500

**Problem:** Email-URL gibt HTTP 500 Error.

**Fix:** GMX Extension nutzen statt lightmailer URLs:
```
chrome-extension://camnampocfohlcgbajligmemmabnljcm/pages/mail-panel.html
```

---

## 🔧 CDP evaluate "document is not defined"

**Problem:** CDP evaluate läuft im Extension Context.

**Fix:** 
1. CUA click für Buttons/Links verwenden
2. CDP NUR für React Inputs nutzen
3. Target attachen an korrekte Page:

```python
targets = await cdp.get_targets()
api_key_target = [t for t in targets if 'settings/users/api-keys' in t.get('url', '')][0]
sid = await cdp.attach_to_target(api_key_target['targetId'])
```

---

## 🔧 "This is a popup/select button" Warning

**Problem:** CUA warnt dass es ein PopUpButton ist.

**Fix:** `set_value` verwenden statt nochmal click:
```bash
echo '{"pid": 123, "window_id": 456, "element_index": 74, "value": "Option"}' | cua-driver call set_value
```

---

## 🔧 AX element_index falsch (klickt falsches Element)

**Problem:** Click landet auf falschem Element.

**Ursache:** tree_line statt element_index extrahiert.

**Fix:** Secondary ID verwenden:
```python
parts = stripped.split('] - [')
sec_id = parts[1].split(']')[0]  # element_index
```

---

## 🔧 GMX Email-Rows nicht klickbar

**Problem:** GMX zeigt "Barrierefreies Postfach" mit nicht-klickbaren Email-Rows.

**Ursache:** Chrome mit `--force-renderer-accessibility` gestartet.

**Fix:** Chrome OHNE accessibility flag starten:
```bash
nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="/Users/jeremy/Library/Application Support/Google Chrome" \
  --profile-directory="Profile 901" \
  --remote-debugging-port=9222 \
  --no-first-run --no-default-browser-check \
  > /tmp/chrome_sinator.log 2>&1 &
```

---

## 🔧 "Missing ... Name!" nach Input

**Problem:** Form zeigt Fehler trotz Input.

**Fix:**
1. Dialog schließen (Close button)
2. Erneut versuchen mit CDP nativeInputValueSetter
3. Nach Input scannen um "Missing" Fehler zu prüfen

---

## 🔧 Flow #1, #2, #3 broken

**Problem:** Code funktioniert nicht mehr nach Änderung.

**Ursache:** READ-ONLY Code wurde angefasst.

**Fix:**
1. `git checkout -- .` um alles reverted
2. Debug-Skript in debug/ erstellen statt existierenden Code ändern
3. Problem analysieren ohne Code zu ändern

---

## 🔧 Chrome Profil-Probleme

**Problem:** Chrome startet mit falschem Profil oder leerer Session.

**Fix:** Original-Profil 901 direkt nutzen:
```bash
--user-data-dir="/Users/jeremy/Library/Application Support/Google/Chrome"
--profile-directory="Profile 901"
```

**VERBOTEN:**
- Profil kopieren nach /tmp
- Symlinks
- --user-data-dir=/tmp/...

---

## 🔧 GMX SPA Navigation Problem

**Problem:** `navigate("navigator.gmx.net/mail")` redirected zu www.gmx.net/

**Fix:** Erst zu gmx.net navigieren, dann "E-Mail" clicken:
```python
await cdp.navigate(sid, "https://www.gmx.net/")
await asyncio.sleep(3)
await cdp.click_at(sid, 235, 33)  # "E-Mail" Header
await asyncio.sleep(5)
url = await cdp.evaluate(sid, "window.location.href")
# URL sollte navigator.gmx.net/mail?sid=... sein
```

---

## 🔧 Cookie-Injection funktioniert nicht

**Problem:** Injizierte Cookies werden nicht akzeptiert.

**Ursache:** Cookies sind an Profil-Pfad gebunden (macOS Keychain).

**Fix:** Cookie-Injection vermeiden. Chrome mit funktionierendem Profil starten.

---

*Letzte Aktualisierung: 2026-05-11*