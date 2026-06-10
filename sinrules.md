# SINRULES.md — Single Source of Truth Regeln

> **ALLE Agenten MÜSSEN diese Regeln 100% befolgen. Keine Ausnahmen.**
> Letzte Aktualisierung: 2026-06-02 (V19.14 — Soft-Ownership Multi-Agent Key Distribution)

---

## 🛑 REGEL 0: VERIFIED FLOW — COMPLETE (2026-06-02)

**Pool:** 261 Keys (~5 available, ~250 suspended)
**Cycle Time:** ~180s average
**E2E Single Command:** `python tools/rotate.py`
**Config:** GMX/Fireworks Credentials aus `data/config.json` (nicht mehr hardcodiert!)
**Proxies:** 10 Instanzen (:8888-:8897) hinter Pool-Router :9998, single URL `sinatorpool-router.delqhi.com`
**API Key (alle Macs):** `<DEIN_API_KEY>`

### WAS IMMER VERWENDET WERDEN MUSS

| ✅ ERLAUBT | Für was |
|-----------|---------|
| **Playwright shadow DOM** | GMX Navigation: `ACCOUNT-AVATAR-NAVIGATOR` → "E-Mail Einstellungen" → iframe |
| **CUA `click`** | React-Checkbox, Dialog-OK, PopUpButton (NICHT mehr für GMX Navigation!) |
| **CUA `type_text`** | Names (First/Last), beliebige Textfelder (OS-Level, React-kompatibel) |
| **CUA `get_window_state`** | AX-Tree scannen (vor/nach JEDEM Klick!) |
| **Playwright `fill()`** | Form-Inputs (email, password, alias name) auf New-Tab allEmailAddresses |
| **Playwright `click(force=True)`** | Delete-Icon, Create-Button, PopUpButton, Generate auf New-Tab |
| **Playwright new-tab** | allEmailAddresses iframe-URL als Top-Level öffnen — umgeht Viewport/Trusted-Event-Issues |
| **CDP Target** | mailbody-ui.de OOPIF für Email-Inhalt |
| **Playwright `page.frames` Scan** | OTP-Mail in ALLEN Frames suchen (auch OOPIF `bap.navigator.gmx.net`) — `read_otp_via_playwright` |
| **CDP Cookie** | `Network.deleteCookies` + `clearBrowserCookies` NUR für Fireworks Domain |
| **Config Manager** | `get_config()` für GMX Email/Passwort + Fireworks Passwort |

### WAS NIEMALS VERWENDET WERDEN DARF

| ❌ VERBOTEN | Grund |
|------------|-------|
| CDP `DOM.performSearch` + `getBoxModel` | Node-IDs stale (0) in 3c.gmx.net Cross-Origin-Iframe |
| CDP `Page.navigate` zu `/mail?...` oder `/mail_settings?...` | Triggert IAC Anti-Automation — Session wird erkannt |
| Playwright `check()` auf React-CB | "Did not change state" — React ignoriert |
| JS `.click()` auf React-Button | React ignoriert dispatchEvent |
| evaluate `.click()` auf off-screen iframe | isTrusted=false → Wicket ignoriert |
| `input[type="email"]` auf Fireworks | Input hat KEIN type-Attribut! → `input[name="email"]` |
| `text=CREATE` als Selector | Matcht Cookie-Banner |
| `/settings/workspace/api-keys` URL | 404; correct: `/settings/users/api-keys` |
| Hardcodierte CUA element_index | React re-renders → alle Indizes ändern sich |
| CUA `"Name"` statt `"First"+"Last"` | Matcht "Company Name" zuerst → falsches Feld |
| `_re` import NUR global | Wird in inner function scope nicht gefunden |
| `Network.clearBrowserCookies` global | Killt GMX-Session — nur für Fireworks Domain |
| `pkill -9 -f "Google Chrome"` | Killt User-Chrome → Session tot |
| Hardcodierte GMX/FW Credentials im Code | Config Manager nutzen (`get_config()`) |
| `__TAURI_INTERNALS__` Check in Frontend | Existiert nicht im Production Build |
| Next.js API Routes in Static Export | Tauri export ist statisch — keine Server-Routes |
| `fetch()` zu localhost:8888 aus Tauri WebView | WebView blockiert → Rust Command nutzen |
| `kimi-k2p5` als Chat-Modell | `reasoning_content` statt `content` → leer |
| Frontend-Fetch ohne Auth-Token | 401 Unauthorized |
| OTP-Scan NUR auf Hauptframe | Mail liegt oft in OOPIF/iframe → `page.frames` durchlaufen |
| GmxService-Methoden auf Modul-Ebene (Spalte 0) | Fallen aus der Klasse → `AttributeError`; immer 4-Space-Indent |

### MANDATORY PATTERNS

```python
# _re import in JEDER Funktion mit CUA scanning
import re as _re  # NIEMALS nur global!

# CUA Names: "First"+"Last" suchen, NICHT "Name"
_find_element("First", "AXTextField")  # richtig
# _find_element("Name", "AXTextField")  # FALSCH!

# CUA dynamic element scanning
def _find_element(text, el_type="AXButton"):
    for line in _cua_scan().split('\n'):
        s = line.strip()
        if text in s and el_type in s:
            m = _re.search(r'\]?\s*-\s*\[(\d+)\]', s)
            if m: return int(m.group(1))
    return None

# Config Manager statt Hardcoding
from agent_toolbox.core.config_manager import get_config
cfg = get_config()  # cfg.gmx_email, cfg.gmx_password, cfg.fireworks_password
```

### BEI FEHLER: SESSION CHECKEN

```bash
# GMX Session check
python tools/gmx_alias_tool.py status

# IAC tabs killen
python -c "from playwright.async_api import async_playwright; ... close iac pages"
```

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

**OTP lesen (V15.5):** `read_otp_via_playwright` scannt ALLE `page.frames`, nicht nur
den Hauptframe (Mail liegt teils im OOPIF `bap.navigator.gmx.net`). `read_otp_axtree_and_frames`
bevorzugt die Fireworks Confirm-URL und akzeptiert einen 6-stelligen Code nur mit
Verifizierungs-Kontext (kein blindes `[A-Z0-9]{6}`).

---

## 🚨 REGEL 5: CHROME START MIT ORIGINAL-PROFIL

**NIEMALS Profil kopieren oder nach /tmp verschieben!**

```bash
nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="/Users/simoneschulze/Library/Application Support/Google Chrome" \
  --profile-directory="Profile 73" \
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
❌ --force-renderer-accessibility (GMX zeigt "Barrierefreies Postfach" — Email-Rows nicht klickbar!)
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

## 🚨 REGEL 11: Bekanntes Problem — Account Suspension

Fireworks suspendiert Accounts bei Spending Limit ($6 Credits aufgebraucht):
```
Account XXX is suspended, possibly due to reaching the monthly
spending limit or failure to pay past invoices.
```
**Workaround:** Key via `POST /pool/report` als suspended markieren → neuen Key holen.
Account ist tot, kein Recovery möglich.

---

## 🚨 REGEL 12: Tauri v2 — Rust Commands statt Frontend-Fetch

**Tauri WebView blockiert `fetch()` zu localhost:8888!**

```
❌ Frontend fetch zu localhost aus Tauri WebView → TypeError: Load failed
✅ Rust Command invoke("chat_send", {message})               → Rust macht den HTTP-Call
```

**Auch verboten:**
- `listen()` für Streaming → ACL denied trotz Permissions
- Next.js API Routes → nicht im Static Export enthalten
- `__TAURI_INTERNALS__` Check → leer im Production Build

**Chat-Modell:** `accounts/fireworks/models/gpt-oss-120b` ($0.15/M, billigstes Serverless)
**Nicht verwenden:** `kimi-k2p5` (reasoning_content statt content → leer bei zu wenig max_tokens)

---

*Letzte Aktualisierung: 2026-06-02 (V19.14)*
