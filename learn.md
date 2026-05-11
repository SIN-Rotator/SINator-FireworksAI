# LEARN.md — Learnings aus Fehlschlägen und Erfolgen

> **Jedes Learning SOFORT hier dokumentieren! NIE nur im Chat lassen!**

---

## 🔥 KRITISCHE LEARNINGS (2026-05-11)

### 1. CUA Driver kann ALLES — CDP ist Notlösung

**Erkenntnis:** CUA Driver nutzt native macOS AX API und ist NICHT detectierbar.
CDP wird von GMX als Bot erkannt (HTTP 413/302/403).

**Erfolg:** API Key Erstellung komplett mit CUA + CDP für React Inputs.
- CUA click auf Buttons, Links, Checkboxes, MenuItems, PopUpButtons ✅
- CUA type_text auf normale Inputs ✅
- CUA set_value für PopUpButton Menus ✅
- CDP nativeInputValueSetter für React Inputs ✅

**Fehlschlag:** 3 Tage mit CDP JavaScript für einfache Klicks verschwendet.

### 2. Pre-Flight Check vor jedem Klick

**Erkenntnis:** Ohne Scan weiß man nicht ob Element existiert.
Nach Klick ohne Scan weiß man nicht ob es funktioniert hat.

**Regel:** SCAN → KLICK → SCAN → Ergebnis verifizieren

**Fehlschlag:** Mehrere Male "Missing ... Name!" Fehler wegen vergessenem Scan.

### 3. GMX Extension für Email — nicht lightmailer

**Erkenntnis:** lightmailer-bs.gmx.net URLs werfen HTTP 500.
GMX MailCheck Extension ist der einzig erlaubte Weg.

**Extension:**
- ID: camnampocfohlcgbajligmemmabnljcm
- Email IDs: 18 Ziffern (z.B. 1778454231729833464)

### 4. PopUpButton braucht set_value

**Erkenntnis:** CUA click auf PopUpButton gibt Warnung:
```
⚠️ This is a popup/select button. Use set_value.
```

**Lösung:** Nach Warnung `set_value` verwenden, nicht nochmal click.

### 5. React Inputs = nativeInputValueSetter

**Erkenntnis:** CUA `type_text` funktioniert NICHT für React controlled inputs.
DOM-Wert wird gesetzt aber React-State bleibt LEER.

**Lösung:**
```javascript
const nativeSetter = Object.getOwnPropertyDescriptor(
    HTMLInputElement.prototype, 'value').set;
nativeSetter.call(input, 'text');
input.dispatchEvent(new Event('input', {bubbles: true, composed: true}));
```

### 6. AX element_index = secondary ID

**Erkenntnis:** AX-Tree Format `[tree_line] - [element_index]`
Nur die SECONDARY ID (nach `] - [`) ist die richtige!

**Falsch:** `[140]` extrahieren
**Richtig:** `parts[1].split(']')[0]` für `[123]`

### 7. Original-Profil nutzen, nicht kopieren

**Erkenntnis:** macOS Keychain-Verschlüsselung bindet Cookies an Original-Pfad.
Profil kopieren = Session verloren.

**Chrome Start:**
```bash
--user-data-dir="/Users/jeremy/Library/Application Support/Google Chrome" \
--profile-directory="Profile 901"
```

---

## 📅 DETAILLIERTE CHRONOLOGIE

### 2026-05-08: Flow #0 Discovery
GMX Login Flow hat sich geändert — Shadow DOM von ACCOUNT-AVATAR.
CDP click_at() funktioniert NICHT für Custom Elements.

**Lösung:** JS .click() + .dispatchEvent() auf Custom Element

### 2026-05-09: Flow #1 Verified
GMX Alias Rotation funktioniert in 29s.
elron-runner-701@gmx.de erstellt.

### 2026-05-10: Flow #1 Breakdown
Agent versuchte "DOM exploration" → Flow #1 komplett gebrochen.
11 Dateien reverted auf commit cf146a6.

**Learn:** ONCE VERIFIED = READ-ONLY

### 2026-05-10: GMX OTP URL Discovery
GMX nutzt ZWEI URL-Formate:
- SPA hash URL: www.gmx.net/mail/#.pc_page... → PUBLIC content!
- Direct URL: navigator.gmx.net/mail?sid=... → LOGGED-IN inbox

### 2026-05-10: GMX Extension Discovery
GMX MailCheck Extension öffnet Email-Panel.
Nicht lightmailer URLs nutzen (HTTP 500).

### 2026-05-11: API Key Creation Success
Erster API Key generiert: fw_4SyZoeCFsyn5L4hpT63LGV
blaze-scorpion-746@gmx.de → Credits: $6.00

---

## ✅ WAS FUNKTIONIERT (2026-05-11)

- CUA click auf alle interaktiven Elemente
- CUA MenuItems nach PopUpButton click
- CUA PopUpButton mit set_value
- CDP nativeInputValueSetter für React inputs
- GMX Extension für Email-Zugriff
- Fireworks API Key Erstellung
- Chrome Start mit Original-Profil 901

## ❌ WAS NICHT FUNKTIONIERT

- CUA type_text auf React controlled inputs
- lightmailer-bs.gmx.net URLs → HTTP 500
- CDP evaluate im extension context (nur Page-Kontext!)
- Profil kopieren/nach /tmp verschieben
- pkill -9 für Chrome

---

*Letzte Aktualisierung: 2026-05-11*