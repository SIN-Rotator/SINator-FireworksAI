# SUCCESSFUL.md — Was funktioniert (Verifiziert 2026-05-11)

> **Diese Methoden sind VERIFIED und funktionieren. NICHT ändern!**

---

## ✅ CUA CLICK

CUA Driver kann ALLE interaktiven Elemente klicken:

```bash
# Button klicken
echo '{"pid": 35880, "window_id": 11395, "element_index": 96}' | cua-driver call click

# Link klicken
echo '{"pid": 35880, "window_id": 11395, "element_index": 35}' | cua-driver call click

# Checkbox klicken
echo '{"pid": 35880, "window_id": 11395, "element_index": 134}' | cua-driver call click
```

**Funktioniert für:**
- Buttons
- Links
- Checkboxes
- MenuItems
- PopUpButtons (nach set_value)

---

## ✅ CUA SET_VALUE für PopUpButtons

Nach PopUpButton click kommt Warnung "Use set_value":

```bash
# Klick auf PopUpButton
echo '{"pid": 35880, "window_id": 11395, "element_index": 74}' | cua-driver call click

# Menu erscheint → MenuItem scannen → set_value für PopUpButton
echo '{"pid": 35880, "window_id": 11395, "element_index": 74, "value": "Create API Key"}' | cua-driver call set_value
```

---

## ✅ CUA GET_WINDOW_STATE für Scanning

Vollständiges AX-Tree scannen vor und nach jedem Klick:

```bash
echo '{"pid": 35880, "window_id": 11395}' | cua-driver call get_window_state | python3 -c "
import sys, json
d = json.load(sys.stdin)
lines = d['tree_markdown'].split('\n')
for i, line in enumerate(lines):
    if 'Button' in line or 'Link' in line:
        print(f'[{i}] {line}')
"
```

---

## ✅ CDP nativeInputValueSetter für React Inputs

CUA type_text funktioniert NICHT für React. CDP ist die Lösung:

```python
await cdp.send_to_session(sid, "Runtime.evaluate", {
    "expression": """
        (function() {
            const input = document.querySelector('input[name*="name"], input[placeholder*="name"]');
            if (!input) return 'input not found';
            
            const nativeSetter = Object.getOwnPropertyDescriptor(
                HTMLInputElement.prototype, 'value').set;
            nativeSetter.call(input, 'blaze-scorpion-746');
            input.dispatchEvent(new Event('input', {bubbles: true, composed: true}));
            
            return 'set: ' + input.value;
        })()
    """,
    "returnByValue": True
})
```

**Funktioniert für:**
- Email-Inputs auf Fireworks Signup
- Password-Inputs
- API Key Name-Input

---

## ✅ GMX Extension für Email

GMX MailCheck Extension ist der einzig erlaubte Weg für Email-Zugriff:

```
Extension ID: camnampocfohlcgbajligmemmabnljcm
Popup: chrome-extension://camnampocfohlcgbajligmemmabnljcm/pages/mail-panel.html
Email IDs: 18 Ziffern
```

---

## ✅ Chrome Start mit Original-Profil 901

```bash
# Chrome BEENDEN
kill $(ps aux | grep "[c]hrome.*user-data-dir" | awk '{print $2}' | head -1)

# Chrome STARTEN
nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="/Users/jeremy/Library/Application Support/Google Chrome" \
  --profile-directory="Profile 901" \
  --remote-debugging-port=9222 \
  --no-first-run --no-default-browser-check \
  > /tmp/chrome_sinator.log 2>&1 &

sleep 6 && curl -s http://127.0.0.1:9222/json/version
```

---

## ✅ API Key Erstellung (Fireworks)

Komplett funktionierender Flow:

1. **Settings → API Keys** (CUA Navigation)
2. **"Create API Key" PopUpButton** → Menu → "API Key" (CUA)
3. **Name eingeben** → CDP nativeInputValueSetter
4. **"Generate Key"** → CUA click
5. **Key aus AX-Tree extrahieren** → `"fw_4SyZoeCFsyn5L4hpT63LGV"`

---

## ✅ Fireworks Registration Flow

1. Navigate zu `/signup`
2. Cookie Banner dismissen (CUA)
3. Email eingeben (CDP nativeInputValueSetter)
4. "Next" klicken (CUA)
5. Password eingeben (CDP nativeInputValueSetter)
6. "Create Account" klicken (CUA) → `/signup/verify`
7. GMX Extension → OTP Email finden
8. OTP URL klicken → Account verifiziert

---

## ✅ GMX Session Recovery (Flow 0)

1. GMX Homepage → "E-Mail" click
2. Prüfe URL enthält `navigator.gmx.net/mail?sid=`
3. Falls tot: Shadow DOM Logout → Login → Email → Password

---

## ✅ GMX Alias Rotation (Flow 1)

1. Navigate zu Settings → "E-Mail-Adressen"
2. Delete-Icon klicken → OK bestätigen
3. Input[name*="localPart"] füllen (CDP)
4. "Hinzufügen" Button klicken (CUA)
5. Erfolg: Alias erscheint in .table_body-row

---

## ✅ Pool Manager

Plain List Format funktioniert mit mehreren Keys:

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

- `get_available_key()` → erster unverwendeter Key ✅
- `mark_used()` → setzt used=True + used_at ✅

---

## ✅ AX element_index korrekt extrahieren

```python
parts = stripped.split('] - [')
sec_id = parts[1].split(']')[0]  # NICHT parts[0]!
```

---

## ✅ Pre-Flight Check Protokoll

```
1. get_window_state scannen
2. Element mit element_index UND Text identifizieren
3. Element existiert IM aktuellen Tree? → KLICKEN
4. Erneut scannen → Ergebnis verifizieren
5. Bei Fehler: Dialog schließen → von vorne beginnen
```

---

*Letzte Aktualisierung: 2026-05-11*