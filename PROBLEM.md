# PROBLEM: OTP Email Extraction from GMX

## Status
- **GMX Login** — ✅ Fixed (prompt=none → prompt=login JS history.replaceState)
- **GMX Alias Delete/Create** — ✅ Working
- **Fireworks Signup** — ✅ Works (account created, verify page shown)
- **OTP / Verify-Email lesen** — ❌ Broken

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
