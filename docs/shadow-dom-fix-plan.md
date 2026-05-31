# Shadow DOM Fix — Plan

**Version:** V15.6  
**Datum:** 2026-05-31  
**Status:** PLANNED — awaiting implementation  
**Bug:** OTP-Extraktion fehlschlägt — GMX verwendet Shadow DOM WebComponents (`sc-webmailer-mail-list-h`) für die Email-Liste. Der Rotator scannt `document.body` mit normalen DOM-Selectors und findet 0 Emails.

---

## Root Cause (bestätigt via CDP)

- `body.innerText` = 0 Zeichen im webmailer-frame
- Alle Emails liegen in Shadow DOM: `<sc-webmailer-mail-list-h class="sc-webmailer-mail-list-h hydrated">`
- `document.querySelectorAll('*')` durchdringt Shadow DOM NICHT
- Der Code sucht nach `<list-mail-item>` (alter Tag-Name) — existiert nicht mehr in aktuellem GMX
- Playwright `page.frames` findet den Frame, aber Shadow DOM bleibt unsichtbar

---

## Betroffene Dateien

| Datei | Zeile(n) | Problem |
|-------|----------|---------|
| `agent_toolbox/core/gmx_service.py` | 107-121 | `read_otp_axtree_and_frames()` — traversiert childNodes aber `body.innerText = 0` liefert keinen Inhalt aus Shadow DOM |
| `agent_toolbox/core/gmx_service.py` | 990-1008 | `findItems()` — Entry-Point `document.body.querySelectorAll('*')` ignoriert Shadow DOM komplett |
| `agent_toolbox/core/gmx_service.py` | 1117 | Sucht nach `list-mail-item` (alter Tag) — aktueller Tag ist `sc-webmailer-mail-list-h` |
| `agent_toolbox/core/gmx_service.py` | 1139-1147 | `click_js` — gleiches Problem: alter Tag-Name, Shadow DOM nicht penetriert |
| `tools/rotate.py` | 127-137 | OTP-Fallback auf `work_tab` statt in den mail-iframe |

---

## Fix-Plan (3 Tasks)

### Task 1: `findItems()` — Shadow-DOM-fähig machen (CDP-Pfad)
- Entry-Point ändern: Statt `document.body.querySelectorAll('*')` direkt auf `document.body` walken
- Rekursion in `shadowRoot` für ALLE Elemente, nicht nur `list-mail-item`
- Tag-Suche verallgemeinern: Suche nach ANY Element mit `shadowRoot` + Text-Inhalt
- Alternativ: CSS-Selector auf `sc-webmailer-mail-list-h` direkt, dann `.shadowRoot` öffnen

### Task 2: `read_otp_axtree_and_frames()` — body.innerText ersetzen
- Statt `document.body.innerText` (liefert 0) → Shadow-DOM-Traversierung mit Text-Extraktion
- Rekursive Funktion die durch `shadowRoot` geht und alle Text-Node Chunks sammelt
- Dann bestehende Logik (URL-Match + 6-stelliger Code) darauf anwenden

### Task 3: Playwright `scan_js` + `click_js` — Shadow DOM penetrieren
- Entry-Point: `document.querySelector('sc-webmailer-mail-list-h')?.shadowRoot ?? document.body`
- Wenn `shadowRoot` existiert: Scan darin statt im leeren `document.body`
- Click-Email: Direkt im gefundenen Frame via `shadowRoot.querySelector(...)` clicken

---

## Implementation Order

1. **Task 2 zuerst** — höchste Priorität, betrifft `read_otp_axtree_and_frames()` (die primäre OTP-Methode)
2. **Task 1 danach** — CDP-Fallback (`read_otp`) parallel anpassen
3. **Task 3 zuletzt** — Playwright-Pfad als Backup

---

## Test-Strategie

1. GMX Login aufrufen → Alias rotieren → Fireworks Signup → OTP-Poll starten
2. Im Browser: Fireworks Verify-Email MANUELL in GMX Posteingang sichtbar machen
3. Prüfen ob `read_otp_axtree_and_frames()` die Email im Shadow DOM findet
4. Bei Erfolg: Full Rotation durchlaufen lassen (Signup → Verify → Login → API Key → Pool)

---

## Risiko

- **Niedrig:** Änderung ist auf DOM-Traversierung beschränkt, keine Architektur-Änderung
- **GMX-Änderungen:** Wenn GMX den WebComponent-Tag ändert, muss der Selector angepasst werden
