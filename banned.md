# 🚫 BANNED — Verbotene Methoden & Patterns

> **NIEMALS** diese Methoden verwenden. Sie wurden ALLE getestet und sind fehlgeschlagen.

---

## 🚫 BANNED: Playwright-native Anti-Patterns (2026-05-31) — V15.4

| ❌ Verboten | Grund |
|------------|-------|
| Playwright `check()` auf React-Checkbox | "Clicking did not change state" — React-CB ignoriert JS-Click. Use native `el.click()` auf `<button role="checkbox">` (Radix UI) |
| `input[type="checkbox"]` mit `aria-label` für Use-Cases | Fireworks Use-Cases: `aria-label` Matching funktioniert NICHT — Checkboxen werden nicht gesetzt. Use `label:has-text("{use_case}")` + click() |
| `label:has-text("Terms")` für Terms-Checkbox | Matcht den "Terms of Service" Link, nicht die Checkbox. Use `button[role="checkbox"]` + native `el.click()` |
| Nur ein einfacher Button-Scan für Continue/Submit | React re-rendered Buttons → einfacher Scan trifft falschen Button. Use 3-Stufen-Strategie: 1) `has-text()` + `is_disabled()`, 2) `type="submit"`, 3) case-insensitive scan |
| Playwright `fill()` auf React-Inputs ohne `click()` vorher | React-State nicht aktualisiert. Use `click()` + `fill()` oder `type(delay=50)` |
| `page.locator('input[type="email"]')` auf Fireworks | Input hat KEIN type-Attribut. Use `input[name="email"]` |
| `page.locator('input[type="password"]')` als einziger Selector | Es gibt 2 Password-Inputs (Password + Confirm). Use `input[name="password"]` |
| `text=CREATE` als Button-Selector | Matcht Cookie-Banner "Create profiles for personalised advertising" |
| `text=E-Mail` als Page-Link | Matcht News-Artikel (Text im Content, nicht Nav-Link) |
| `text=Next` als Submit-Button | Matcht Cookie-Banner "Next" — use `button[type="submit"]` + text-check |
| `page.goto()` auf 3c.gmx.net direkt | Triggert IAC Anti-Automation. Use shadow DOM navigation via Playwright |
| `browser.new_page()` für jeden Schritt | Tab-Explosion → Chrome überlastet. Reuse pages, close non-essential tabs |
| `create_api_key()` ohne Session Reuse | Neue Page = keine Cookies → API Key Seite redirected zu `/login`. Use `login_fireworks()` Session übergeben (page+playwright+browser) |
| `return {{...}}` statt `return {...}` | Python interpretiert `{{...}}` als Set mit Dict → `TypeError: cannot use 'dict' as set element` |
| `parentElement` für Shadow DOM Traversal | Bricht an Shadow-Boundary. Use `el.getRootNode().host` |
| `_click_text()` Helper aus V5/V7 | Unreliable text-matching. Use Playwright-native locators |
| `cua-driver` für Navigation | Tab-Titel ist leer bei programmatischen Tabs. Use Playwright für Navigation |
| `find_cua_window(title_keywords=["FreeMail"])` | Chrome-Titel ist LEER für neue Tabs. Use `get_page_target()` mit URL-Matching |

---

## 🚫 BANNED: Tauri v2 Patterns (2026-05-25)

| ❌ Verboten | Grund |
|------------|-------|
| `__TAURI_INTERNALS__` in `BACKEND_URL` Check | Existiert im Production Build nicht → `BACKEND_URL` wird leer → alle Fetches failen |
| Next.js API Routes im Tauri Static Export | `frontendDist: "../out"` = statischer Export, `/api/*` Routen existieren nicht |
| Tauri Event `listen()` für Chat-Streaming | ACL `plugin:event|listen not allowed` — Permission existiert aber JS API braucht anderen Scope |
| `fetch()` von Tauri WebView zu `localhost:8888` | Tauri v2 blockiert externe Fetches per Default — braucht Rust Command statt Frontend-Fetch |
| `kimi-k2p5` als Chat-Modell | Reasoning-Modell — denkt 20-30s, Antwort kommt in `reasoning_content` statt `content` |
| `gpt-oss-120b` mit `max_tokens=50` | Zu kurz — Reasoning wird abgeschnitten bevor die Antwort kommt |
| Frontend `fetch` zu `localhost:8000` ohne Auth | `/api/v1/config` war nicht in `public_prefixes` → 401 → GMX Passwort wurde nicht geladen |

**✅ Korrektur:** Rust `chat_send` Command (kein Event nötig), `BACKEND_URL` immer `"http://localhost:8000"`, `/api/v1/config` in `public_prefixes`, `gpt-oss-120b` mit `max_tokens=2048`

---

## 🛑 BANNED: Health Check Side-Effects (2026-05-23)

| ❌ Verboten | Grund |
|------------|-------|
| `GET /pool/health` ruft `mark_used()` auf | Destruktiver Side-Effect! 7 Keys zerstört am 2026-05-23 |
| Dashboard `loadDashboard()` ruft `/pool/health` | Überschreibt stats-Anzeige mit health-Daten |
| `PoolManager` ohne `reload()` | Singleton hat stale State, sieht keine externen Änderungen |
| `_purge_gmx_cookies()` löscht Master-Backup | Überschreibt `backup/session/gmx-cookies-master.json` |
| `update_credits()` hat NULL Callers | Credits werden nie gezogen — alle Keys zeigen `credits_remaining=6.0` |

**✅ Korrektur:** Health-Endpoint ist read-only. PoolManager ruft `reload()` vor jeder public Methode.

---

## 🛑 BANNED: E2E Flow (2026-05-22)

| ❌ Verboten | Grund |
|------------|-------|
| GMX Rotation OHNE vorherigen Logout-Check | Redirect zu Account-Home statt Signup-Form |
| CUA `"Name"` statt `"First"` + `"Last"` | Matcht Company Name zuerst → falsches Feld |
| Hardcodierte CUA-Indizes (129, 137, etc.) | React re-rendered → Indizes ändern sich |
| `_re` Import NUR global | Wird in inner function scope nicht gefunden |
| Playwright `check()` auf React-Checkbox | "Clicking did not change state" |
| JS `.click()` auf React-Button | React controlled components ignorieren dispatchEvent |
| `input[type="email"]` auf Fireworks | Input hat KEIN type-Attribut → `input[name="email"]` |
| `/settings/workspace/api-keys` | 404 → `/settings/users/api-keys` |
| `text=CREATE` als Button-Selector | Matcht Cookie-Banner |
| Direkte Navigation zu 3c.gmx.net | Triggert IAC restart |
| `pkill -9 -f "Google Chrome"` | Killt User-Chrome → Profil-Lock → Session tot |

---

## 🛑 BANNED: OTP/Email-Lesung (2026-05-12)

**GMX Email-Körper (OOPIF) via Playwright-Frames (V15.4):** `page.frames` sucht native nach `mailbody-ui.de`. CDP `attach_to_iframe()` ist Fallback via Playwright-Browser-WS.

| ❌ Verboten | Grund |
|------------|-------|
| HTTP `mailbody/tmai{id}/true;jsessionid=...` | GMX REST API gibt 403 |
| CDP `DOM.performSearch` + `describeNode` auf Webmailer | Hängt auf 3c.gmx.net |
| Shadow DOM Traversal für Email-Zugriff | Wicket blockiert alle JS-Events |
| `read_otp()` OHNE Extension-Methode | HTTP-API ist tot |

**✅ Erlaubt:** Playwright `page.frames` nach OOPIF suchen → Verify-URL extrahieren. CDP `attach_to_iframe()` via Playwright-Browser-WS als Fallback.

---

## 🚫 BANNED: Chrome Session Management (2026-05-11 — HISTORISCH)

> V15.4 nutzt `chromium.launch()` — diese Bans gelten nur falls jemand noch `connect_over_cdp()` versucht.

Diese Ansätze wurden ALLE ausprobiert. JEDER einzelne ist gescheitert:

---

## 🚫 BANNED: CDP-Only Anti-Patterns (HISTORISCH — 2026-05-21)

> **Diese Bans sind aus V5/V7. Aktueller Code (V15.4) nutzt Playwright-native — CDP wird nur noch als OOPIF-Fallback via Playwright-Browser-WS verwendet.**

| ❌ Verboten (historisch) | Grund |
|--------------------------|-------|
| CDP `Runtime.evaluate` auf GMX accessible pages | Gibt `{}` zurück wenn Accessibility-Mode aktiv |
| CDP `Page.navigate` zu GMX URLs | Triggert Bot-Detection (Akamai/DataDome) |
| CDP `Input.dispatchKeyEvent` | GMX React-Inputs ignorieren |
| JS `.click()` auf Delete-Icon | Wicket ignoriert |
| JS `dispatchEvent(MouseEvent)` auf Delete-Icon | Wicket prüft `isTrusted` |
| `form.submit()` für Hinzufügen | Triggert `iac/restart` |
| CDP `Input.dispatchMouseEvent` für Navigation | GMX ignoriert CDP für Nav |
| `bap.navigator.gmx.net/mail_settings` | Nur Shell, kein Content |
| CUA für Navigation | SID geht verloren |
| JS `nativeSetter` ohne `dispatchEvent('input')` | React-State nicht aktualisiert |
| `Target.getTargets` für Iframe-Suche | GMX-Iframes nicht als CDP-Targets |
| Hartcodierte Koordinaten `(350,340)` | Klickt ins Leere |

**Stattdessen IMMER:**
- DOM-Zugriff: `client.evaluate()` + JavaScript
- Delete-Icon + Hinzufügen: CDP `Input.dispatchMouseEvent`
- Navigation: JS `dispatchEvent(MouseEvent)` mit bubbles
- Input: `nativeInputValueSetter` + Event('input')
- OK-Button: CUA `click`

---

## ❌ BANNED: AX tree_line als element_index nutzen (2026-05-11)

**Problem:** AX-Tree output format:
```
[140] - [123] AXCheckBox "Flexible capacity for production"
  ^^^   ^^^^
  |     +---> element_index = 123 (RICHTIG!)
  +---> tree_line = 140 (FALSCH!)
```
Klickt man `element_index: 140` wird das WONG element geklickt (AXStaticText ""), nicht die Checkbox!

**Banned:** Regex `\[(\d+)\]` extrahiert tree_line statt element_index!
**Fix:** Immer `parts[1].split(']')[0]` für secondary ID nutzen (siehe AGENTS.md Regel 1).

---

## ❌ BANNED: Chrome mit Default user-data-dir starten

```bash
# FALSCH — Chrome verweigert CDP mit diesem Pfad!
chrome --user-data-dir="/Users/jeremy/Library/Application Support/Google/Chrome" --remote-debugging-port=9222
```

**Fehlermeldung:**
```
DevTools remote debugging requires a non-default data directory.
```

**Warum gebannt:** Chrome blockiert `--remote-debugging-port` wenn `--user-data-dir` auf den **Standard-Pfad** zeigt (`~/Library/Application Support/Google/Chrome`). Das ist eine Sicherheitsbeschränkung.

---

## ❌ BANNED: Nur Profil-Subfolder kopieren (ohne Local State)

```bash
# FALSCH — Chrome erstellt ein NEUES Profil statt Profile 901 zu verwenden!
cp -R "/Users/jeremy/Library/Application Support/Google/Chrome/Profile 901" /tmp/my-profile
chrome --user-data-dir=/tmp/my-profile --remote-debugging-port=9222
```

**Symptom:** Chrome startet zwar mit CDP, aber erstellt ein **neues leeres Profil** (Default). Alle Sessions, Cookies, Login-Daten sind weg.

**Warum gebannt:** Chrome braucht die `Local State` Datei im Root von `user-data-dir` um zu wissen welche Profile existieren. Ohne `Local State` → Chrome denkt es ist ein neues Profil → erstellt Default.

---

## ❌ BANNED: Cookie-Injection in fremdes Profil

```javascript
// FALSCH — Cookies sind profilgebunden verschlüsselt!
const cdp = await page.createCDPSession();
await cdp.send('Network.setCookies', { cookies: savedCookies });
```

**Symptom:** `page.setCookie()` oder CDP `Network.setCookies` in ein **frisches** Profil funktioniert nicht. GMX-Cookies sind an den **originalen Profil-Pfad** gebunden (macOS Keychain-Verschlüsselung).

**Warum gebannt:** Chrome verschlüsselt Cookies mit einem Schlüssel der vom `user-data-dir` Pfad abhängt. Cookies aus Profil A können nicht in Profil B injiziert werden.

---

## ❌ BANNED: puppeteer.launch() statt spawn()

```javascript
// FALSCH — puppeteer.launch() setzt --enable-automation!
const browser = await puppeteer.launch({ headless: false });
```

**Symptom:** GMX's Bot-Detection (DataDome/Akamai) erkennt `--enable-automation` Flag sofort → CAPTCHA nach Email-Eingabe → Automation blockiert.

**Warum gebannt:** `puppeteer.launch()` fügt automatisch Flags hinzu die Anti-Bot-Systeme erkennen. `child_process.spawn()` umgeht das.

---

## ❌ BANNED: waitForNavigation() bei auth.gmx.net

```javascript
// FALSCH — auth.gmx.net nutzt JS-Transitions, keine Page-Navigation!
await page.click('#login-button');
await page.waitForNavigation(); // Hängt ewig!
```

**Symptom:** `waitForNavigation()` timeout weil auth.gmx.net **keine** neue Seite lädt — der Login erfolgt via JavaScript (SPA-Transition).

**Warum gebannt:** GMX's auth.gmx.net ist eine Single-Page-Application. Nach Button-Klick ändert sich die URL nicht, nur der DOM-Inhalt.

---

## ❌ BANNED: Symlink für user-data-dir

```bash
# FALSCH — Symlink bricht Cookie-Entschlüsselung!
ln -s "/Users/jeremy/Library/Application Support/Google/Chrome/Profile 901" /tmp/chrome-profile
chrome --user-data-dir=/tmp/chrome-profile --remote-debugging-port=9222
```

**Symptom:** Chrome startet, aber Cookies sind unlesbar (verschlüsselt mit original Pfad).

**Warum gebannt:** macOS Keychain-Verschlüsselung bindet Cookies an den **realen** Pfad. Symlinks werden nicht aufgelöst für den Decryption-Key.

---

## ❌ BANNED: READ-ONLY Code ändern (Flow #1, #2, #3)

```python
# FALSCH — READ-ONLY Code anfassen!
# Flow #1 (gmx_service.py), Flow #2 (fireworks_service.py), Flow #3 (OTP extraction)
# sind VERIFIED und funktionieren. NIE ändern außer es gibt einen konkreten Bug-Report.

# Breaked am 2026-05-10: Agent versuchte "DOM exploration" für Shadow-DOM input
# → rewrite _navigate_to_all_email_addresses mit 75-line PFAD-Navigation
# → Flow #1 komplett gebrochen
# → 11 files reverted auf commit cf146a6 (alles verloren!)
```

**Symptom:** Nach Änderung funktioniert die Navigation nicht mehr. GMX-Session geht verloren, Alias-Rotation schlägt fehl, "Input nicht gefunden" Fehler.

**Warum gebannt:** Flow #1, #2, #3 wurden mühsam getestet und verifiziert. Jede Änderung — selbst "kleine Verbesserungen" — kann den funktionierenden Flow brechen. Der Agent verlor am 2026-05-10 6 Tage Arbeit durch einen Rewrite-Versuch.

**Regel:** ONCE VERIFIED = READ-ONLY. Nur ändern wenn: (a) konkreter Bug-Report, (b) GMX die UI ändert, (c) neue Use-Case erfordert es.

---

## ✅ KORREKTE METHODE (siehe AGENTS.md für Details)

**V15.4 nutzt `chromium.launch()` — KEIN Running Chrome nötig.** Kein `connect_over_cdp()`, kein Profile 901, kein `--remote-debugging-port`. Playwright startet frischen Chromium mit `--remote-debugging-port` auf einem freien Port (9230-9240) für CDP-Fallback.

```python
# Richtig (V15.4):
p = await async_playwright().start()
browser = await p.chromium.launch(headless=False)
page = await browser.new_page()
```

**NIEMALS:** `connect_over_cdp()` — hängt mit Chrome 148 (Protocol-Mismatch).

---

## ❌ BANNED: CDP JavaScript für Button/Link/Checkbox Klicks

```python
# FALSCH — CDP evaluate für normale Klicks!
await cdp.evaluate(sid, "document.querySelector('button').click()")
```

**Warum gebannt:** CUA driver kann ALLE interaktiven Elemente klicken. CDP evaluate:
- Läuft im falschen Kontext (Extension statt Page)
- Macht uns abhängig von DOM-Struktur-Änderungen
- Ist langsamer als CUA für einfache Klicks

**Regel:** CUA für Buttons, Links, Checkboxes, MenuItems, PopUpButtons.
CDP NUR für: React Inputs, Tab Management, Cookie Inspection.

---

## ❌ BANNED: CUA type_text auf React Inputs

```bash
# FALSCH — CUA type_text funktioniert NICHT für React!
echo '{"pid": 123, "window_id": 456, "element_index": 94}' | cua-driver call type_text '{"text": "mein-email@gmx.de"}'
# Result: "Missing ... Name!" Fehler!
```

**Warum gebannt:** React controlled inputs nutzen `useState` und ignorieren CUA keyboard events. Der DOM-Wert wird gesetzt aber React-State bleibt LEER.

**Fix:** CDP nativeInputValueSetter verwenden (siehe AGENTS.md Regel 3).

---

## ❌ BANNED: lightmailer-bs.gmx.net URLs

```bash
# FALSCH — HTTP 500 errors!
curl https://lightmailer-bs.gmx.net/mailbody/123456789/false
# → "Diese Seite funktioniert nicht HTTP ERROR 500"
```

**Warum gebannt:** lightmailer URLs werfen 500er errors. GMX Extension ist der einzig erlaubte Weg für Email-Zugriff.

**Fix:** GMX MailCheck Extension öffnen → Email klicken (siehe AGENTS.md Regel 4).

---

## ❌ BANNED: Nach Klick NICHT scannen

```bash
# FALSCH — Klick ohne Scan nachher!
echo '...' | cua-driver call click
echo 'nächste aktion'  # FEHLER! Kein Scan dazwischen!
```

**Warum gebannt:** Nach jedem Klick kann sich die UI ändern (Modal öffnet, Fehler erscheint, Element verschiebt). Ohne Scan weiß man nicht ob der Klick funktioniert hat.

**Fix:** Immer SCAN → KLICK → SCAN → Ergebnis verifizieren.

---

## ❌ BANNED: PopUpButton nicht mit set_value behandeln

```bash
# FALSCH — Nach Popup-Warnung wieder click verwenden!
echo '...' | cua-driver call click
# → "This is a popup/select button. Use set_value."
# NOCHMAL click = FEHLER!
```

**Warum gebannt:** CUA warnt dass es ein PopUpButton ist. Bei erneutem click wird das falsche Element (Image/StaticText) geklickt.

**Fix:** Nach "This is a popup/select button" → set_value verwenden:
```bash
echo '{"pid": 123, "window_id": 456, "element_index": 74, "value": "Create API Key"}' | cua-driver call set_value
```

---

## ❌ BANNED: CDP Runtime.evaluate auf GMX Accessible Pages (2026-05-11)

```python
# FALSCH — client.evaluate() gibt LEERES {} zurück auf accessible GMX!
result = await client.evaluate(sid, "document.querySelector('...')")
# → {"result": {"type": "function", "value": {}}}  ← LEER!
```

**Symptom:** Runtime.evaluate-Ergebnisse sind `{}` auf allen GMX-Seiten wenn Chrome im Accessibility-Mode läuft. ALLE JS-basierten DOM-Queries schlagen fehl.

**Warum gebannt:** Wenn cua-driver Daemon läuft, erkennt Chrome "Assistive Technology" und aktiviert den Accessibility-Mode. In diesem Modus funktioniert `Runtime.evaluate` NICHT für GMX-Seiten (vermutlich wegen iframe/cross-origin restrictions in der accessible rendering pipeline).

**Fix:** DOM.performSearch + DOM.getBoxModel verwenden STATT Runtime.evaluate:
```python
# ✅ RICHTIG — DOM domain funktioniert auch auf accessible pages!
await client.send_to_session(sid, "DOM.performSearch", {
    "query": "@gmx.de",
    "includeUserAgentShadowDOM": True
})
# → findet text nodes in iframes!
```

**Alternativ:** `Input.dispatchMouseEvent` funktioniert ebenfalls (andere Domain als Runtime).

---

## ❌ BANNED: CDP Page.navigate für GMX (2026-05-11)

```python
# FALSCH — Page.navigate ist ein HTTP Request der als Bot erkannt wird!
await client.send_to_session(sid, "Page.navigate", {"url": "https://navigator.gmx.net/..."})
# → GMX antwortet mit 413/302/403 (Bot Detection)!
```

**Symptom:** Session ist sofort tot, redirects zu Login-Page oder Cookie-Fehler-Seite.

**Warum gebannt:** GMX's CDN/Load-Balancer (Akamai/DataDome) erkennt CDP-generierte HTTP-Requests und blockiert sie.

**Fix:** CUA für ALLE Navigation nutzen (AXPress auf Links/Buttons).
CDP nur für: DOM.performSearch, Input.dispatchMouseEvent, Cookie-Management.

---

## 🛑 BANNED: Fireworks Anti-Patterns (2026-05-21)

| ❌ Verboten | Grund |
|------------|-------|
| Playwright `check()` auf React-Checkbox | "Clicking did not change state" — React-CB ignoriert JS-Click |
| JS `.click()` auf React-Button | React controlled components ignorieren dispatchEvent |
| `page.locator('input[type="email"]')` auf Fireworks | Input hat KEIN type-Attribut; use `input[name="email"]` |
| `/settings/workspace/api-keys` URL | 404 Not Found; correct is `/settings/users/api-keys` |
| `text=CREATE` als Button-Selector | Matcht Cookie-Banner "Create profiles for personalised advertising" |
| `text=E-Mail` als Page-Link | Matcht News-Artikel (Text im Content, nicht Nav-Link) |

---

## 🛑 BANNED: GMX Iframe Direct Navigation (2026-05-22 — UPDATED V8)

| ❌ Verboten | Grund |
|------------|-------|
| CDP `Page.navigate` zu `/mail` oder `/mail_settings` | Triggert IAC Anti-Automation → Einstellungen AXButton nicht sichtbar |
| CDP `Page.navigate` zu `/email_addresses?sid=...` | Redirects immer zu `/mail_settings/mail` — GMX SPA blockiert direkte URL |
| `new_page().goto(iframe_url)` zu 3c.gmx.net im alten Approach | Früher erlaubt, JETZT New-Tab mit voller iframe-URL als Top-Level |
| Playwright `fill()`/`click()` auf off-screen 3c-bap iframe | Element outside viewport — trusted events benötigen sichtbaren Viewport |
| JS `evaluate("el => el.click()")` auf off-screen iframe | isTrusted=false → Wicket/Apache Wicket ignoriert |

**✅ V8 Korrektur — New-Tab Approach:**
```python
# 1. Playwright goto inbox (kein CDP!)
await pg.goto(f"https://bap.navigator.gmx.net/mail?sid={sid}")

# 2. CUA click Einstellungen (nur auf /mail sichtbar!)
cua_click(find_element("Einstellungen", "AXButton"))

# 3. JS click hidden nav-menu
await pg.evaluate("document.querySelector('#nav-menu button...').click()")

# 4. Extract iframe URL → open in new tab as top-level document
iframe_url = await _get_iframe_url()  # 6×3s retry
new_pg = await browser.new_page()
await new_pg.goto(iframe_url)
# Now fill() + click() work normally (element IS on-screen)
```

## 🛑 BANNED: macos-use Agent (2026-05-21)

| ❌ Verboten | Grund |
|------------|-------|
| `agent.invoke()` mit LLM | Tool-Validierung broken (loc:Input should be a valid list) |
| Agent Tool calls | Pydantic `list[int]` validation fails on LLM JSON output |
| Chromium launch via Agent | Chrome bereits offen; App-Tool crashed |

**✅ Erlaubt:** CUA direkt für OS-Level-Klicks (kein LLM-Agent nötig)

*Last Updated: 2026-05-31 (V15.4 — ONE Browser, Playwright frames statt CDP OOPIF)*
