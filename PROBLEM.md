# PROBLEM: OTP Email Extraction from GMX

## Status
- **GMX Login** — ✅ Fixed (prompt=none → prompt=login JS history.replaceState)
- **GMX Alias Delete/Create** — ✅ Working
- **Fireworks Signup** — ✅ Works (account created, verify page shown)
- **OTP / Verify-Email lesen** — ✅ Fixed (siehe Root Cause unten)

## ✅ ROOT CAUSE (gefunden & gefixt)
In `agent_toolbox/core/gmx_service.py` waren vier Methoden durch fehlerhafte
Einrückung (Spalte 0 statt 4 Spaces) **aus der Klasse `GmxService` herausgefallen**
und damit zu reinen Modul-Funktionen geworden:

- `generate_alias_name()`
- `initialize_architecture()`   → Multi-Tab-Setup (work_tab + inbox_tab)
- `navigate_inbox()`            → dedizierter Inbox-Tab
- `read_otp_axtree_and_frames()` → eigentlicher OTP-Reader

Dadurch schlugen alle Aufrufe wie `self.generate_alias_name()`,
`gmx.initialize_architecture(browser)`, `gmx.navigate_inbox()` und
`gmx.read_otp_axtree_and_frames(...)` mit `AttributeError` fehl. Das erklärt
**beide** Symptome: das OTP-Lesen UND "Tab bleibt nicht im Posteingang" (Problem 2),
da die komplette Multi-Tab-Architektur unerreichbar war.

**Fix:** Zeilen 61–135 wieder um 4 Spaces in die Klasse eingerückt. Die Methoden
gehören jetzt wieder zu `GmxService` (per AST verifiziert, Datei kompiliert).

## ✅ ROBUSTHEIT (zusätzliche Härtung der OTP-Logik)
Zusätzlich zum Strukturfix wurden die in den Hypothesen genannten Schwachstellen adressiert:

- **`read_otp_via_playwright`** scannt jetzt **alle Frames** der Page statt nur den Hauptframe.
  Damit wird die Mail auch gefunden, wenn sie in einem OOPIF/iframe liegt
  (Hypothese #1/#2: `bap.navigator.gmx.net`). Der Klick erfolgt im jeweils
  matchenden Frame (`matched_frame.evaluate`), Text- ODER ID-basiert.
- **`read_otp_axtree_and_frames`** erkennt jetzt zuerst die eindeutige Fireworks
  **Confirm-URL** und akzeptiert einen 6-stelligen Code nur noch aus Text-Chunks mit
  Verifizierungs-Kontext (`code`/`verify`/`confirm`/...). Das vermeidet die
  False-Positives des alten `[A-Z0-9]{6}`-Patterns (Hypothese #4), bevorzugt rein
  numerische Codes (`\d{6}`).

## Symptom
Nach Fireworks-Signup wird `read_otp_via_playwright()` auf `navigator.gmx.net/mail` aufgerufen.
Die Email **kommt bei GMX an** (sie ist im Posteingang sichtbar), aber `read_otp_via_playwright`
findet kein `<list-mail-item>` mit `"fireworks"` im Text.

## Code
- `agent_toolbox/core/gmx_service.py` → `read_otp_via_playwright()` (Zeile ~990)
- Funktionsweise: Shadow-DOM-Traversal via `querySelectorAll('*')` → Tag-Check `list-mail-item` → `innerText.includes('fireworks')`

## Hypothesen
1. Die GMX-Email liegt auf `bap.navigator.gmx.net/mail?sid=...` statt `navigator.gmx.net/mail`
   → OOPIF oder SPA-Struktur anders
2. Shadow-DOM hat andere Struktur (Tag heisst anders, Mail in iframe statt main frame)
3. Die Mail ist im Posteingang sichtbar mit CUA/CDP aber nicht per JS Shadow-DOM-Traversal
4. `innerText` des Items enthält nicht "fireworks" sondern zB "Fireworks AI" oder URL-only
5. MailCheck Extension (`chrome-extension://camnampocfohlcgbajligmemmabnljcm/`) könnte nötig sein

## Problem 2: Code bleibt nicht im logged-in Tab
Nach erfolgreichem GMX-Login (Tab auf `bap.navigator.gmx.net/mail?sid=...`) wird derselbe Tab
für Alias-Operationen auf die Settings-Seite navigiert (`3c.gmx.net/mail/client/settings/...`).
Später muss OTP-Reading in diesen Tab zurücknavigieren, was Session-Probleme verursachen kann.

**Gewünscht:** Ein eigener Tab für GMX bleibt IMMER im Posteingang (nie navigiert).
Alle anderen Ops (Alias, FW-Signup) nutzen separate Tabs. Der OTP-Tab hat dann immer
die frische Session ohne erneute Navigation.

## Alte Arbeitsansätze
- `tools/test_otp_mailcheck.py` — MailCheck Extension + OOPIF-Attach via CDP (funktionierte früher)
- `read_otp()` (CDP-basiert, Zeile ~830) — AXTree + OOPIF-Polling (funktionierte, legacy)

## Nächste Debug-Schritte
- Bei nächstem Testlauf `page.content()` dumpen unmittelbar nach Signup
- GMX-Inbox per CDP/AXTree scannen statt Playwright shadow DOM
- `read_otp()` (CDP-legacy) als Fallback einbauen
- Auf MailCheck Extension umstellen (siehe `test_otp_mailcheck.py`)
- EIGENEN Tab für OTP: `browser.new_page()` BEVOR der GMX-Tab weg navigiert wird
- Keine Navigation des OTP-Tabs — bleibt fix auf `navigator.gmx.net/mail`
