# SINRULES.md — Single Source of Truth Regeln

> **ALLE Agenten MÜSSEN diese Regeln 100% befolgen. Keine Ausnahmen.**

---

## 🚨 OBERSTE REGEL: PRE-FLIGHT CHECK

**NIEMALS eine Aktion ausführen ohne vorher alles zu scannen!**

```
SCAN → AKTION → SCAN → Ergebnis verifizieren
```

### Pflicht-Scan vor JEDEM Klick:
1. `cua-driver call get_window_state` — vollständiges AX-Tree scannen
2. Element mit element_index UND Text identifizieren
3. Element existiert IM aktuellen Tree?
4. DANN klicken

### Pflicht-Scan nach JEDEM Klick:
1. Erneut `get_window_state` aufrufen
2. Ergebnis verifizieren: Hat sich was geändert?
3. Fehler? → Dialog schließen → von vorne

---

## 🚨 REGEL 2: CUA DRIVER IST IMMER ERSTE WAHL

**CUA kann ALLES anklicken. Du musst nur fähig genug sein!**

```
✅ CUA click     → Buttons, Links, Checkboxes, MenuItems, PopUpButtons
✅ CUA type_text → Normale Inputs (NICHT React controlled!)
✅ CUA set_value → PopUpButton Menus
✅ CUA get_window_state → AX-Tree scannen
```

**CDP NUR ALS NOTLÖSUNG wenn CUA 100% korrekt erfasst ist im VORFELD:**

```
✅ CDP NUR für:
  - React controlled inputs (CUA type_text funktioniert NICHT!)
  - Target management (neue Tabs)
  - GMX Extension Email-Zugriff
```

---

## 🚨 REGEL 3: REACT INPUTS = CDP nativeInputValueSetter

CUA `type_text` funktioniert NICHT für React controlled inputs!

**KORREKT:**
```python
const nativeSetter = Object.getOwnPropertyDescriptor(
    HTMLInputElement.prototype, 'value').set;
nativeSetter.call(input, 'mein-text');
input.dispatchEvent(new Event('input', {bubbles: true, composed: true}));
```

---

## 🚨 REGEL 4: GMX EXTENSION FÜR EMAIL

**EINZIG erlaubter Weg für Email-Zugriff:**

```
Extension ID: camnampocfohlcgbajligmemmabnljcm
Popup: chrome-extension://camnampocfohlcgbajligmemmabnljcm/pages/mail-panel.html
```

**VERBOTEN:**
```
❌ lightmailer-bs.gmx.net URLs → HTTP 500
❌ webmailer.gmx.net direkt navigieren
```

---

## 🚨 REGEL 5: CHROME START MIT ORIGINAL-PROFIL

**NIEMALS Profil kopieren oder nach /tmp verschieben!**

```bash
nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="/Users/jeremy/Library/Application Support/Google Chrome" \
  --profile-directory="Profile 901" \
  --remote-debugging-port=9222 \
  --no-first-run --no-default-browser-check \
  > /tmp/chrome_sinator.log 2>&1 &
```

**VERBOTEN:**
```
❌ --user-data-dir=/tmp/... (Session geht verloren)
❌ Profil kopieren (Keychain-Verschlüsselung)
❌ Symlinks (bricht Cookie-Entschlüsselung)
❌ pkill -9 (SIGTERM nur!)
```

---

## 🚨 REGEL 6: PopUpButton = set_value

Nach `click` auf PopUpButton kommt Warnung:
```
⚠️ This is a popup/select button. Use set_value.
```

**DANN:** `set_value` verwenden, nicht nochmal click!

```bash
echo '{"pid": 123, "window_id": 456, "element_index": 74, "value": "Create API Key"}' | cua-driver call set_value
```

---

## 🚨 REGEL 7: AX element_index = secondary ID

**AX-Tree Format:**
```
[140] - [123] AXCheckBox "Flexible capacity"
   ^^^   ^^^^
   |     +---> element_index = 123 (RICHTIG!)
   +---> tree_line = 140 (FALSCH!)
```

**Extrahieren:**
```python
parts = stripped.split('] - [')
sec_id = parts[1].split(']')[0]  # NICHT parts[0]!
```

---

## 🚨 REGEL 8: ONCE VERIFIED = READ-ONLY

Flow #0, #1, #2, #3 sind VERIFIED. NIE ändern außer:
- Konkreter Bug-Report
- GMX ändert die UI
- Neuer Use-Case erfordert es

**Neuer Ansatz = Neue Datei (debug/), nicht existierende ändern!**

---

## 🚨 REGEL 9: Nach jedem Commit zu GitHub

Lokale Commits sind MÜLL — andere Agenten setzen alles zurück!

```bash
rtk git add -A
rtk git commit -m "beschreibung"
rtk git push
```

---

## 🚨 REGEL 10: Documentation = Code

Jede Datei 100% lesen bevor weitermachen!
Jedes Learning SOFORT dokumentieren!
Keine Learnings nur im Chat lassen!

---

*Letzte Aktualisierung: 2026-05-11*