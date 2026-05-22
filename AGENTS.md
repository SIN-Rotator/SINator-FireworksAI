# AGENTS.md — SINator Fireworks AI Rotator V8 (2026-05-22)

## ✅ COMPLETE E2E FLOW — VERIFIED 2026-05-22

**Full automated flow in ONE command:**
```bash
python tools/rotate.py
# → GMX Login (built-in, Step 0) → Alias Rotation (~63s) → Fireworks Signup
# → OTP → Verify → Login → Onboarding → Playwright Fallback → API Key → Pool
```

**Latest API Key:** `fw_6rWU4KGUPts6zVnaRreu6R` (pulse-jaguar-899@gmx.de)
**Pool:** 30 Keys (30 total, 29 available)
**Cycle Time:** ~209s average (Strecke: 204-224s)

### E2E Steps (proven working, ~204s total)
0. **GMX Login (built-in)**: `rotate.py` Step 0 — Playwright-Login `opensin@gmx.de`, speichert frische Cookies
1. **GMX Session**: IAC-Tabs cleanup → `www.gmx.net` → "E-Mail" click → 15s SID-Polling
2. **GMX Rotation**: Playwright iframe delete + create (~28s)
3. **Fireworks Logout**: CDP `Network.deleteCookies` + `clearBrowserCookies` (nur Fireworks-Domain!)
4. **Signup**: `/signup` → `input[name="email"]` → 2x password → Create Account
5. **OTP Poll**: GMX MailCheck extension → CDP OOPIF mailbody-ui.de → extract URL
6. **Verify**: `Target.createTarget(verify_url)` → account confirmed
7. **Login**: `/login` → "Email Login" → `input[name="email"]` + password → Next
8. **Onboarding**: CUA "First" + "Last" (NOT "Name"!) → Terms checkbox → Continue
9. **Playwright-Onboarding-Fallback**: Falls CUA Submit keinen Redirect triggert → Playwright füllt Formular + Submit
10. **Use-Cases**: CUA dynamic scan text-based → checkboxes → Submit
11. **API Key**: `/settings/users/api-keys` → Create API Key PopUpButton → menuitem → Generate (mit `disabled`-Wait + DOM-Polling)
12. **Pool**: Auto-save to `data/fireworksai-pool.json`

### Architecture: Playwright + CUA Hybrid

| Layer | Tool | Purpose |
|-------|------|---------|
| Navigation (CUA) | CUA | Inbox → Einstellungen AXButton |
| Navigation (JS) | CDP evaluate | Hidden nav-menu click → `produkte_ha` page with allEmailAddresses iframe |
| Alias operations | Playwright new-tab | Open iframe URL in fresh tab → `fill()`, `click()` on top-level document |
| React checkboxes | CUA | `AXPress` — Playwright `check()` ignoriert React |
| Names input | CUA | `type_text` — real macOS keystrokes React can't ignore |
| API Key dialog | Playwright | PopUpButton force-click → menuitem → fill → Generate |
| OTP email | CDP | MailCheck Extension → click email → mailbody-ui.de OOPIF → extract URL |
| Cookie management | CDP | `Network.deleteCookies` + `clearBrowserCookies` für Fireworks |

### 🔧 V8 GMX NAVIGATION FIX (2026-05-22)

**Problem:** GMX geändert — Direkte Navigation zu `/mail_settings/email_addresses?sid=...` redirected immer zu `/mail_settings/mail`. CDP `Page.navigate` triggert IAC Anti-Automation → "Einstellungen" AXButton nicht im AX-Tree. allEmailAddresses iframe off-screen (`rect=(-2400, -1742)`) → Playwright kann nicht interagieren (Trusted-Events + Viewport).

**Lösung — 4-Schritt Flow:**

```python
# STEP 1: Playwright navigate to inbox (NOT CDP — avoids IAC)
# CDP `Page.navigate` detected as bot → IAC restart
# Playwright connect_over_cdp + goto("/mail?sid=...") works

# STEP 2: CUA click "Einstellungen" AXButton from inbox
# ONLY visible on full inbox page (/mail?sid=...), NOT on /mail_settings/mail
cua_click(find_element("Einstellungen", "AXButton"))  # element [148]
await asyncio.sleep(5)  # → URL changes to /mail_settings?sid=...

# STEP 3: JS evaluate click hidden nav-menu button
# GMX hides settings sidebar via CSS (offsetParent === null)
# CUA can't see it, but JS click loads the allEmailAddresses iframe
await client.evaluate(session_id, """
    const nav = document.querySelector('#nav-menu');
    if (nav) {
        for (const el of nav.querySelectorAll('button, a')) {
            if (el.innerText?.includes('Mail-Adressen') || 
                el.innerText?.includes('Wunsch-Mail')) {
                el.click(); break;
            }
        }
    }
""")
# → URL changes to /produkte_ha?sid=... with embedded iframe

# STEP 4: Open allEmailAddresses iframe URL in new Playwright tab
# The 3c-bap.gmx.net iframe is off-screen AND in cross-origin context
# JS dispatchEvent clicks fail (isTrusted === false for Wicket framework)
# Solution: extract iframe URL → goto() in new tab → top-level document
iframe_url = "https://3c-bap.gmx.net/mail/client/settings/allEmailAddresses;jsessionid=..."
new_page = await browser.new_page()
await new_page.goto(iframe_url)
# Now Playwright fill() + click() work normally (element IS on-screen)
```

**Code-Änderungen in `gmx_service.py`:**
- `_navigate_to_all_email_addresses`: CDP `Page.navigate` entfernt → Playwright goto inbox + CUA Einstellungen + JS nav-click + Polling bis iframe geladen
- `_get_iframe_url`: Neue Helper-Methode mit 6×3s Retry-Loop
- `_delete_alias_via_playwright`: Iframe-Operation → New-Tab-Operation (öffnet iframe URL, hover/click/OK ohne off-screen issues)
- `_create_alias_via_playwright`: Gleiche New-Tab-Strategie, `fill()` statt evaluate nativeInputValueSetter
- `rotate_alias` inline delete: Nutzt `_get_iframe_url` + new-tab statt iframe-content

**Anti-Pattern (NIEMALS):**
```python
# FALSCH — CDP navigate triggert IAC, Einstellungen nicht im AX tree:
await client.send_to_session(sid, "Page.navigate", {"url": ".../email_addresses?sid=..."})

# FALSCH — Off-screen iframe → evaluate click().failed (isTrusted=false):
await frame.locator('button').evaluate("el => el.click()")
```

**Korrektes Pattern:**
```python
# RICHTIG — Playwright navigate (kein IAC):
for btn in await pg.locator('button').all():
    if 'Zum Postfach' in (await btn.text_content() or ''): await btn.click()

# RICHTIG — New tab → top-level document → normal Playwright click:
new_pg = await browser.new_page()
await new_pg.goto(iframe_url)
await new_pg.locator('button:has-text("Hinzufügen")').first.click()
```

### 🔑 CRITICAL PATTERNS (MANDATORY)

```python
# 1. `_re` import in JEDER function die CUA scanning nutzt
import re as _re  # NIEMALS nur global! In jeder Funktion!

# 2. CUA Names: "First"+"Last" suchen, NICHT "Name"
el = _find_element("First", "AXTextField")  # richtig
# el = _find_element("Name", "AXTextField")  # FALSCH! matcht "Company Name"

# 3. CUA Scan + Click + Scan (REPEAT THIS EXACTLY)
def _cua_scan():
    r = subprocess.run(["cua-driver", "call", "get_window_state"],
        capture_output=True, text=True, timeout=15,
        input=json.dumps({"pid": pid, "window_id": wid}))
    return json.loads(r.stdout).get('tree_markdown', '')

def _find_element(text, el_type="AXButton"):
    for line in _cua_scan().split('\n'):
        s = line.strip()
        if text in s and el_type in s:
            m = _re.search(r'\]?\s*-\s*\[(\d+)\]', s)
            if m: return int(m.group(1))
    return None

# 4. Playwright form interaction
page.locator('input[name="email"]').first.fill(email)  # KEIN type-Attribut!
page.locator('input[name="password"]').first.fill(password)
# Button matching via text content:
for btn in await page.locator('button[type="submit"]').all():
    if 'Next' in (await btn.text_content() or ''):
        await btn.click(force=True); break

# 5. GMX Alias Delete (Playwright iframe)
frame = [f for f in page.frames if 'allEmailAddresses' in f.url][0]
frame.locator(f'text={alias_email}').first.hover()
frame.locator('[title*="löschen"]').first.click(force=True)
# → CUA click OK in confirmation dialog

# 6. GMX Alias Create (Playwright iframe)
inp = frame.locator('input[type="text"]').first
await inp.fill("name-123")
btn = frame.locator('button:has-text("Hinzufügen")').first
await btn.click(force=True)
# verify: inp.input_value() == '' = success

# 7. API Key (Playwright) — V6 mit disabled-Wait + DOM-Polling
await page.goto("https://app.fireworks.ai/settings/users/api-keys")
for btn in await page.locator('button').all():
    if 'Create API Key' == (await btn.text_content() or '').strip():
        await btn.click(force=True); break
await page.locator('[role="menuitem"]:has-text("API Key")').first.click(force=True)
for inp in await page.locator('input').all():
    if 'name' in (await inp.get_attribute('name') or '').lower():
        await inp.fill(key_name); break
await asyncio.sleep(1)  # Wait für React Re-Render
# Wait for disabled → enabled transition
for _ in range(15):
    for btn in await page.locator('button').all():
        txt = (await btn.text_content() or '').strip()
        if 'Generate' == txt and not await btn.is_disabled():
            await btn.click(force=True); break
    else: await asyncio.sleep(0.5); continue
    break
# Poll für API Key im DOM (max 10s)
api_key = None
for _ in range(10):
    body = await page.evaluate("document.body.innerText")
    m = _re.search(r'fw_[a-zA-Z0-9]{20,}', body)
    if m: api_key = m.group(0); break
    await asyncio.sleep(1)
if not api_key:
    raise RuntimeError("API Key not generated")
```

**API Key Error Handling:**
```python
# "Missing API Key Name!" Modal erkennen + schließen
body = await page.evaluate("document.body.innerText")
if 'Missing' in body and 'Name' in body:
    for btn in await page.locator('button').all():
        if 'Close' in (await btn.text_content() or ''):
            await btn.click(force=True); break
    await asyncio.sleep(1)
    # Retry: fill + Generate
```

### 🏗️ Project Structure
```
SINator-fireworksai/
├── agent_toolbox/
│   ├── start_toolbox.py                  FastAPI Entrypoint
│   ├── core/
│   │   ├── cdp_client.py                Raw CDP Websocket Client
│   │   ├── gmx_service.py               GMX: Session, Alias (Playwright+CUA+CDP), OTP
│   │   ├── fireworks_service.py          V6: Playwright+CUA + Playwright-Onboarding-Fallback
│   │   ├── browser_manager.py           Browser Lifecycle
│   │   ├── pool_manager.py              API-Key Pool CRUD
│   │   └── cookie_manager.py            Cookie Management (legacy)
│   └── api/
│       ├── schemas.py                   Pydantic Models
│       └── routes/
│           ├── rotation.py              POST /rotation/full (V5 Playwright+CUA)
│           ├── gmx.py                   GMX Alias Endpoints
│           ├── fireworks.py             Fireworks Endpoints
│           ├── browser.py               Browser Start/Stop/Status
│           ├── cookies.py               Cookie Extract/Inject/Recover
│           └── pool.py                  Pool Stats/Key/Get
├── tools/
│   ├── rotate.py                        Single-command E2E (GMX → FW → API Key)
│   └── gmx_alias_tool.py                CLI tool (rotates alias standalone)
├── data/
│   └── fireworksai-pool.json            API-Key Pool (gitignored — secrets!)
├── AGENTS.md                            ← DIESE DATEI
├── banned.md                            Verbotene Methoden
├── sinrules.md                          Absolute Regeln
├── plan.md                              BUILDING PLAN
├── README.md                            Projekt-README
└── plans/
    ├── knowledge-base.md                Lessons Learned
    └── 2026-05-21-fix-alias-creation.md Fix Plan
```

### 🔧 Chrome Configuration (IMMUTABLE)
```bash
# Chrome STARTEN (OHNE --force-renderer-accessibility!)
nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="/Users/jeremy/Library/Application Support/Google Chrome" \
  --profile-directory="Profile 901" \
  --remote-debugging-port=9222 \
  --no-first-run --no-default-browser-check \
  > /tmp/chrome_sinator.log 2>&1 &
sleep 6 && curl -s http://127.0.0.1:9222/json/version

# Chrome BEENDEN (SIGTERM, not SIGKILL!)
kill $(ps aux | grep "[c]hrome.*user-data-dir" | awk '{print $2}' | head -1)
```

**⚠️ NIEMALS `--force-renderer-accessibility` verwenden!**
- MIT Flag: GMX zeigt "Barrierefreies Postfach" (Email-Rows NICHT klickbar!)
- OHNE Flag: GMX funktioniert normal + CUA-Driver AX-Tree funktioniert trotzdem

**⚠️ NIEMALS `pkill -9 -f "Google Chrome"`!** Killt User-Chrome → Session tot.

### 🚫 BANNED METHODS (alle getestet, alle failed)
| ❌ Verboten | Grund |
|------------|-------|
| CDP `DOM.performSearch` + `getBoxModel` | Node-IDs stale (0) in 3c.gmx.net Cross-Origin-Iframes |
| Playwright `check()` auf React-Checkbox | "Clicking did not change state" |
| JS `.click()` auf React-Button | dispatchEvent ignoriert |
| `input[type="email"]` auf Fireworks | Input hat KEIN `type`-Attribut! → `input[name="email"]` |
| `/settings/workspace/api-keys` | 404 → `/settings/users/api-keys` |
| `text=CREATE` als Button-Selector | Matcht Cookie-Banner |
| Direkte Navigation zu `3c.gmx.net` | Triggert IAC Anti-Automation, Session tot |
| Hardcodierte CUA element_index | React re-renders → alle Indizes ändern sich |
| CUA `"Name"` statt `"First"` + `"Last"` | Matcht "Company Name" zuerst → falsches Feld |
| `_re` import NUR global | Wird in inner function scope nicht gefunden |
| `Network.clearBrowserCookies` global | Killt GMX-Session — nur für Fireworks Domain |
| `page.goto()` zu iframe-URL | Triggert IAC restart, Session expired |
| CUA Submit-Klick bei Onboarding | Triggert keinen Redirect → Playwright-Fallback nötig |
| `ERR_BLOCKED_BY_RESPONSE` ignorieren | GMX Rate-Limiting → Cookies löschen + Chrome restart |

---

## ⬇️ ARCHIVED: V3/V4 CDP Documentation (2026-05-10 to 2026-05-21)

**The following sections document the OLD CDP-based approach that was replaced by the V5 Playwright+CUA hybrid. They are kept for historical reference only. DO NOT use these methods for new development.**

### V4 Playwright Flow — Verified 2026-05-21

**Verification:** `neon-hawk-042@gmx.de` successfully created + verified.
**Approach:** CUA for navigation, Playwright for form interaction, CDP DOM not used for form.

### Alias Delete Flow (Playwright + CUA)

```python
# 1. Find allEmailAddresses iframe in mail_settings page
frame = [f for f in page.frames if 'allEmailAddresses' in f.url][0]

# 2. Mouseover alias email → delete icon appears  
frame.locator(f'text={alias_email}').first.hover()
await asyncio.sleep(1)

# 3. Click delete icon (force=True — icon only visible after hover)
frame.locator('[title*="löschen"]').first.click(force=True)
await asyncio.sleep(2)

# 4. CUA click OK in confirmation dialog
cua-driver call click '{"pid": PID, "window_id": WID, "element_index": OK_INDEX}'
await asyncio.sleep(3)

# 5. Verify: alias_email not in frame.content()
```

### Alias Create Flow (Playwright — iframe URL direkt)

```python
# 1. Open allEmailAddresses iframe URL in new tab (bessere Wicket-Interaktion)
new_page = await browser.new_page()
await new_page.goto(iframe_url)  # z.B. https://3c-bap.gmx.net/.../allEmailAddresses;jsessionid=...

# 2. Fill input + click Hinzufügen
inp = new_page.locator('input[type="text"]').first
await inp.fill("name-123")
btn = new_page.locator('button:has-text("Hinzufügen")').first
await btn.click(force=True)
await asyncio.sleep(5)

# 3. Verify: input cleared = success
if not await inp.input_value():
    print("✅ Created!")
```

### Session Refresh (wenn nötig)

```python
# Click "E-Mail" link → redirects to inbox with fresh SID
gmx_page.get_by_role("link", name="E-Mail", exact=True).first.click()
# Oder via CUA:
cua-driver call click '{"pid": P, "wid": W, "element_index": 29}'
```
**Verification:** `python tools/gmx_alias_tool.py rotate` → ✅ success in ~15s

### ⚡ (ARCHIVED) MANDATORY PREFLIGHT — WURDE ENTFERNT

**Note:** `preflight.py` was deleted in the V5 cleanup (2026-05-22). These instructions are historical only.

```bash
# This tool no longer exists — use manual verification instead:
python tools/gmx_alias_tool.py rotate
```

### ⚡ WAS FUNKTIONIERT (Ground Truth)

```
=== GMX Alias Rotation ===
   Target: AUTO-GENERATED
✅ Rotation
   Status: success
   Created: shadow-tiger-983@gmx.de
   Deleted: echo-tiger-831@gmx.de
   Steps OK: navigated_to_addresses → alias_deleted → input_found
              → form_filled → add_button_clicked → alias_created
   Time: 11.35s
```

### 🔒 GESCHÜTZTE METHODEN — TOD BEI ÄNDERUNG

| Methode | Datei | Warum geschützt |
|---------|-------|----------------|
| `_navigate_to_all_email_addresses` | `gmx_service.py:441` | v3 CDP/JS-Navigation. CUA-Version ist TOT. |
| `_resolve_gmx_oopif` | `gmx_service.py:619` | Navigiert zu `navigator.gmx.net/navigator/jump/to/mail_settings`. Nicht `bap.navigator.gmx.net`! |
| `_find_hinzufuegen_button_coords` | `gmx_service.py:1283` | Button aus FORM des ERSTEN `localPart`-Inputs. NICHT Fun-Domain! |
| `_click_button_via_cdp` | `gmx_service.py:1323` | CDP `Input.dispatchMouseEvent`. `form.submit()` triggert IAC! |
| `_cdp_click` | `gmx_service.py:835` | CDP `Input.dispatchMouseEvent` (mouseMoved+pressed+released). JS dispatchEvent IGNORED! |
| `_cua_click_ok_button` | `gmx_service.py:900` | Regex: `-\s*\[(\d+)\]\s*AXButton\s*"OK"`. CUA Markdown-Format! |
| `_fill_alias_input_via_cdp` | `gmx_service.py:1394` | `nativeInputValueSetter`. `dispatchKeyEvent` IGNORED! |
| `_verify_alias_in_iframe` | `gmx_service.py:1353` | JS `innerText.indexOf()`. `dom_search` HÄNGT! |
| `_find_alias_input_via_cdp` | `gmx_service.py:1196` | Selectors: `name*='localPart'`, `placeholder*='ihr-name'`. Nicht `alias`! |
| `_find_delete_icon_coords` | `gmx_service.py:848` | JS evaluate. `dom_search` HÄNGT! |
| `_find_alias_coords_in_iframe` | `gmx_service.py:721` | JS evaluate. `dom_search` HÄNGT! |

### ☠️ VERBOTENE ANSÄTZE (ausprobiert, ALLE fehlgeschlagen)

| Ansatz | Warum gescheitert |
|--------|------------------|
| CDP `DOM.performSearch` + `getSearchResults` | Hängt auf `3c.gmx.net` (kein Response) |
| CDP `DOM.getBoxModel` nach `performSearch` | Stale NodeIds, parentId=None |
| JS `.click()` auf Delete-Icon | Wicket ignoriert `.click()` |
| JS `dispatchEvent(MouseEvent)` auf Delete-Icon | Wicket prüft `isTrusted` (immer false) |
| `form.submit()` für Hinzufügen-Button | Triggert `iac/restart` Anti-Automation |
| CDP `Input.dispatchKeyEvent` für Input-Füllung | GMX React-Inputs ignorieren KeyEvents |
| CDP `Input.dispatchMouseEvent` für Navigation | GMX ignoriert CDP-Level Maus-Events für Nav |
| `bap.navigator.gmx.net/mail_settings` Navigation | Zeigt nur Shell, Content in Cross-Origin-Iframes |
| CUA für Navigation | Produziert URLs ohne `sid=`, Session geht verloren |

### 🧪 VOR JEDER ÄNDERUNG: VERIFICATION

```bash
# Nur dieser eine Befehl — NIEMALS mit && oder anderen Commands verketten!
python tools/gmx_alias_tool.py rotate
```

Bei Fehler: `git checkout v3-working -- agent_toolbox/core/gmx_service.py`

### ⚡ OTP/EMAIL — GMX MAILCHECK EXTENSION (PERMANENT, 2026-05-12)

Extension ID: `camnampocfohlcgbajligmemmabnljcm`
Methode: `_read_otp_via_extension()` in gmx_service.py

Extension-Popup öffnen → Firefox-Email per sender_filter finden → klicken → GMX Mail öffnet Email → iframe navigieren → OTP-URL extrahieren.

**☠️ BANNED für OTP:** HTTP mailbody API (403), CDP DOM API (hängt), Shadow DOM Traversal

---

## ⚠️ GMX ALIAS BUG-FIX (2026-05-11 v2) — DIRECT NAVIGATION STATT OOPIF

**Ursprüngliches Problem (Bug-Report):**
> Alias-Formular liegt in Cross-Origin-Iframe. CDP DOM.getBoxModel crasht,
> Input.dispatchMouseEvent mit hartcodierten Koordinaten (350, 340) klickt ins Leere.

**Erste Diagnose (v1 — FALSCH):**
> `3c.gmx.net` ist ein OOPIF. Wir müssen `Target.getTargets` nutzen, das
> iframe-Target finden, eine separate child_session attachen, und dort
> DOM-Operationen ausführen.

**Echte Ursache (User-Diagnose 2026-05-11):**
1. `3c.gmx.net` (Iframe 4) ist der **Mail-Client (Inbox)**, NICHT die Alias-Settings!
   Dieser Iframe ist offscreen bei `rect=(-2400, -1742)`.
2. Der aktive Alias-Settings-Iframe ist `navigator.gmx.net/navigator/jump/to/mail_settings`
   (Iframe 7) mit `rect=(0, 80)` und `class app-stack__children--active`.
3. **KEINER der Content-Iframes erscheint als CDP iframe-Target** — Chrome isoliert
   sie NICHT als OOPIF. `Target.getTargets` liefert nur den Top-Level-Page-Target.
4. **Direkte Navigation zu der Iframe-URL funktioniert:**
   `https://bap.navigator.gmx.net/mail_settings?sid=...` zeigt die Settings-Seite
   als vollständiges Dokument (kein Iframe nötig).

**Fix v2 — DIRECT NAVIGATION:**
`_resolve_gmx_oopif` wurde komplett umgebaut:
- Statt `Target.getTargets` + iframe-attach → **direkte Navigation** zu
  `bap.navigator.gmx.net/mail_settings?sid={session_id}`
- Der "Iframe-Inhalt" ist jetzt der **Top-Frame** — keine OOPIF-Transformation nötig
- `OopifContext` wird weiterhin für API-Kompatibilität genutzt, aber:
  - `child_session_id = parent_session_id` (gleiche Session)
  - `offset_x = offset_y = 0` (kein Transform)
- `dom_search`, `node_content_box` etc. laufen direkt auf dem Top-Frame

**Anti-Pattern — NIEMALS:**
```python
# FALSCH — Chrome isoliert GMX-Iframes NICHT als CDP-Targets:
iframe = await client.find_iframe_target("3c.gmx.net")  # → None!

# FALSCH — falscher Iframe (3c.gmx.net = Mail-Client, NICHT Alias-Settings):
url_substring="3c.gmx.net"  # → Inbox, nicht Settings!

# FALSCH — hartcodierte Klick-Koords:
return {"x": 350, "y": 340}
```

**Korrektes Pattern:**
```python
# Direct Navigation — navigiere zur Settings-URL und arbeite auf Top-Frame
oopif = await self._resolve_gmx_oopif(client, top_session)
if not oopif: return None  # Nicht eingeloggt
# oopif.child_session_id == oopif.parent_session_id (gleiche Session!)
# oopif.offset_x == oopif.offset_y == 0 (kein Transform)
node_ids = await client.dom_search(oopif.child_session_id, "@gmx.de")
# Koordinaten sind direkt Top-Viewport-Koords (kein to_top nötig)
```

**Diagnose-Tool (aktualisiert für v2, DELETED in V5 cleanup):**
**Note:** `tools/diagnose_oopif.py` was deleted in the V5 cleanup (2026-05-22).

**Verifikations-Status:** v2-Fix gepusht auf `main`. User muss testen mit:
```bash
git pull origin main
python tools/diagnose_oopif.py
python tools/gmx_alias_tool.py status
python tools/gmx_alias_tool.py rotate
```

---

## 🎯 ALIAS DELETE FLOW (Stand 2026-05-11 v2, Direct Navigation)

**HYBRID: CDP DOM auf Top-Frame + Input.dispatchMouseEvent + CUA**

Nach der direkten Navigation zu `bap.navigator.gmx.net/mail_settings?sid=...`
ist der Alias-Content im **Top-Frame** (nicht mehr in einem Iframe).
`child_session_id == parent_session_id`, `offset_x/y = 0`.

```
1. _resolve_gmx_oopif → navigiert zu mail_settings, returnt OopifContext
   (child_session = parent_session, offset = 0)
2. dom_search(session, "@gmx.de") → Text-Node-Treffer direkt im Top-Frame
3. node_content_box(session, nid) → Koords sind bereits Top-Viewport
4. Input.dispatchMouseEvent mouseMoved → HOVER → Delete-Icon rendert
5. dom_search("löschen") → Delete-Icon Koords
6. Input.dispatchMouseEvent pressed+released → Klick auf Delete-Icon
7. CUA get_window_state → "OK"-Button im macOS-Dialog → CUA click "OK"
8. _verify_alias_in_iframe(alias_email, present=False) → Server-Verifikation
```

**Implementation:** `agent_toolbox/core/gmx_service.py` Methoden
`_resolve_gmx_oopif`, `_find_alias_coords_in_iframe`, `_cdp_hover`,
`_find_delete_icon_coords`, `_cdp_click`, `_cua_click_ok_button`,
`_verify_alias_in_iframe`, `delete_existing_alias`.

## 🎯 ALIAS CREATE FLOW (Stand 2026-05-11 v2, Direct Navigation)

**HYBRID: CDP DOM auf Top-Frame + Input.dispatchKeyEvent + CUA-Fallback**

```
1. _resolve_gmx_oopif → navigiert zu mail_settings, returnt OopifContext
2. _find_alias_input_via_cdp → CSS-Selektoren (input[name*='alias'], type='email')
   Koords sind direkt Top-Viewport (kein Transform). Falls kein CDP-Match:
   CUA-AXTextField-Click als Fallback.
3. CDP Input.dispatchMouseEvent → click auf Input
4. CDP Input.dispatchKeyEvent type="char" → Zeichen tippen
5. _find_hinzufuegen_button_coords mit input_y → dom_search("Hinzufügen")
6. CDP Input.dispatchMouseEvent → Klick Hinzufügen
7. _verify_alias_in_iframe(alias_email, present=True) → Server-Verifikation
```

**Implementation:** `agent_toolbox/core/gmx_service.py` Methoden
`_resolve_gmx_oopif`, `_find_alias_input_coords`, `_find_alias_input_via_cdp`,
`_fill_alias_input_via_cdp`, `_find_hinzufuegen_button_coords`,
`_click_button_via_cdp`, `_verify_alias_in_iframe`, `create_alias`, `rotate_alias`.

## 🚨 MANDATORY SCAN PROTOCOL (PERMANENT)
niemals wieder machst du auch nurrrr eine kleine aktion bevor du nicht gesamten mac alle elemente gescannt hast vor und nach JEDEM klick

## 🛠️ BROWSER WAIT COMMAND
/browser-wait-element — warte auf selector element, timeout 15s, return: gefunden/nicht gefunden

## ⚠️ EINFACHE REGEL — AX ELEMENT CLICK:
Bei jedem Scan: Speichere VOLLSTÄNDIGEN PFAD + TEXT:
```python
elements = []
for i, line in enumerate(lines):
    stripped = line.strip()
    if 'AXCheckBox' in stripped or 'AXButton' in stripped:
        # Extrahiere den TEXT im element
        text_match = re.search(r'AXButton "(.*?)"|AXCheckBox "(.*?)"', stripped)
        if text_match:
            text = text_match.group(1) or text_match.group(2)
            # Extrahiere secondary ID (DIE RICHTIGE!)
            parts = stripped.split('] - [')
            sec_id = parts[1].split(']')[0]
            
            # Speichere: text + id
            elements.append({
                'text': text,
                'element_index': int(sec_id),  # <-- DIESE ID, nicht tree_line!
                'line': i
            })
```

**Vor dem Click:** Rescan prüfen ob gespeicherter text IM AX-tree noch existiert:
```python
current_tree = get_ax_tree()
if gesuchter_text in current_tree:
    cua-driver click element_id
else:
    # RESCAN nötig! Element verschoben/geändert
```

**Regel:**
> MATCH text + MATCH parent + MATCH id = CLICK
> MATCH text + MISSING id = RESCAN

## 🎯 PROJECT VISION

**Ziel:** Automatisierte Erstellung von Fireworks AI API-Keys via GMX Alias → Fireworks Account → OTP Verification → API-Key Pool.

**Endprodukt:** `POST /rotation/full` liefert einen `fw-...` API-Key. Jeder Key = ein neuer GMX Alias + ein neuer Fireworks Account + $5 Credits.

**Stack:** Python + FastAPI + **CUA-DRIVER** (Native macOS AX, NOT CDP!)

**Start:** `python agent_toolbox/start_toolbox.py` → `http://localhost:8000/docs`

---

## 🚨 PROZESS-REGELN (aus Fehlschlägen gelernt)

### REGEL 1: DELETE WRONG IMMEDIATELY
Nach einem Fehlschlag: **SOFORT** Dateien/Ordner löschen die den failed approach enthalten.
NIE: "vielleicht brauch ich das später" — es kostet nur Zeit beim nächsten Versuch.

### REGEL 2: ONCE VERIFIED = READ-ONLY
Ein funktionierender Code-Abschnitt wird NICHT mehr angefasst. NUR Änderungen für:
Bug-Fix, Performance-Issue, neuer Use-Case. Bei Unsicherheit: NEUE Datei, nicht existierende ändern.

### REGEL 3: FÜTTERE AGENTS.MD NACH JEDEM ERFOLG
Neue Learnings → SOFORT in AGENTS.md. Prozedur:
- Erfolg → AGENTS.md updaten (bewiesene Fixes, Koordinaten, Data Models)
- Fehlschlag → banned.md updaten (verbotene Methode + warum)
- Learnings NIE nur im Chat lassen

---

## 🚨 ABSOLUTE REGELN — NIEMALS ÜBERTRETEN

| VERBOTEN | WARUM |
|---|---|
| `git checkout -- .` / `git reset --hard` | Zerstört alle Arbeitsfortschritte |
| `pkill -9 -f "Google Chrome"` | Zerstört unflushed SQLite → GMX Session tot |
| Profil 901 nach /tmp kopieren | Cookies an Original-Pfad gebunden (macOS Keychain) → Session unbrauchbar |
| `--user-data-dir=/tmp/...` | GMX-Session geht verloren |
| `waitForNavigation()` bei GMX | GMX ist SPA — keine Page-Reloads → hängt ewig |

---

## 🏗️ SYSTEM CONFIGURATION (IMMUTABLE)

```
Chrome Binary:     /Applications/Google Chrome.app/Contents/MacOS/Google Chrome
User Data Dir:     /Users/jeremy/Library/Application Support/Google Chrome
Profile:           Profile 901 ("SINator (Fireworks AI)")
CDP Port:          9222
Chrome User:       simoneschulze (macOS login profile)
CDP Endpoint:      ws://127.0.0.1:9222/devtools/browser/...
```

**Chrome Start (DER EINZIG RICHTIGE WEG) — OHNE accessibility flag:**
```bash
# Chrome BEENDEN
kill $(ps aux | grep "[c]hrome.*user-data-dir" | awk '{print $2}' | head -1)

# Chrome STARTEN (OHNE --force-renderer-accessibility!)
nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="/Users/jeremy/Library/Application Support/Google Chrome" \
  --profile-directory="Profile 901" \
  --remote-debugging-port=9222 \
  --no-first-run --no-default-browser-check \
  > /tmp/chrome_sinator.log 2>&1 &

sleep 6 && curl -s http://127.0.0.1:9222/json/version | python3 -c "import sys,json; print('Chrome OK')"
```

**⚠️ WICHTIG: NIEMALS `--force-renderer-accessibility` verwenden!**
- Mit dem Flag: GMX zeigt "Barrierefreies Postfach" (Email-Rows NICHT klickbar!)
- Ohne dem Flag: GMX funktioniert normal + CUA-Driver AX-Tree funktioniert trotzdem

**Chrome Beenden (SIGTERM, nicht SIGKILL):**
```bash
kill $(ps aux | grep "[c]hrome.*user-data-dir" | awk '{print $2}' | head -1)
```

---

## 🔧 CUA-DRIVER — NATIVE MACOS AX (NOT CDP!)

**ENTDECKUNG:** 2026-05-10 — GMX erkennt CDP als Bot! HTTP requests return 413/302/403. 
**LÖSUNG:** `cua-driver` nutzt native macOS Accessibility (AX) API — NICHT detectierbar!

### CUA-DRIVER SETUP

```bash
# Start cua-driver daemon
nohup cua-driver serve > /tmp/cua-driver.log 2>&1 &
sleep 3 && cua-driver status

# Ergebnis: socket: /Users/jeremy/Library/Caches/cua-driver/cua-driver.sock, pid: 87079
```

### WICHTIGE TOOLS

| Tool | Beschreibung |
|------|-------------|
| `list_windows` | Alle Browser-Fenster mit pid, window_id, bounds |
| `get_window_state` | AX-Tree als Markdown mit element_index |
| `click` | AX-Press auf element_index (muss get_window_state VORHER im gleichen Turn) |
| `press_key` | Key-Events an pid senden (cmd, shift, option, ctrl) |
| `hotkey` | Tastenkombinationen (z.B. ["cmd", "left"]) |
| `type_text` | Text an pid senden |
| `screenshot` | PNG Screenshot |

### GMX EMAIL WORKFLOW (HYBRID: CUA-DRIVER + CDP)

**ENTDECKUNG:** GMX Email-Rows haben KEIN AXPress im AX-Tree. Email klicken funktioniert NUR via CDP JavaScript `item.click()`.

```bash
# 1. Chrome OHNE --force-renderer-accessibility starten!
kill $(ps aux | grep "[c]hrome.*user-data-dir" | awk '{print $2}' | head -1) 2>/dev/null
sleep 3
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --user-data-dir="/Users/jeremy/Library/Application Support/Google Chrome" \
  --profile-directory="Profile 901" \
  --remote-debugging-port=9222 \
  --no-first-run --no-default-browser-check \
  "https://www.gmx.net" &>/dev/null &
sleep 8

# 2. Chrome Window finden
cua-driver call list_windows '{"query": "Chrome"}'
# → wID: 10372, pid: 96377, title: 'GMX - kostenlose E-Mail...'

# 3. GMX Homepage State checken
echo '{"pid": 96377, "window_id": 10372}' | cua-driver call get_window_state | python3 -c "
import sys, json
d = json.load(sys.stdin)
lines = d['tree_markdown'].split('\n')
print('Title:', [l for l in lines if 'AXWindow' in l][0][:80])
for i, line in enumerate(lines[:60]):
    if 'E-Mail' in line:
        print(f'[{i}] {line}')
"
# → [28] AXLink (E-Mail)

# 4. E-Mail Header Link klicken (CUA-Driver für Navigation!)
cua-driver call click '{"pid": 96377, "window_id": 10372, "element_index": 28}'
# → ✅ Performed AXPress on [28] AXLink ""

# 5. Warten und GMX FreeMail Inbox prüfen
sleep 5
echo '{"pid": 96377, "window_id": 10372}' | cua-driver call get_window_state | python3 -c "
import sys, json
d = json.load(sys.stdin)
lines = d['tree_markdown'].split('\n')
print([l for l in lines if 'AXWindow' in l][0][:80])
"
# → "GMX FreeMail - Google Chrome"

# 6. Email klicken (CDP JavaScript - CUA-Driver funktioniert NICHT!)
# Via CDP client.evaluate():
async def _click_fireworks_email_in_iframe(client, session_id):
    click_result = await client.evaluate(
        session_id,
        """
        (function() {
            const selectors = [
                '[class*="inbox-content"]',
                '[class*="maillist"]',
                '[class*="mail_list"]',
                'main [class*="list"]'
            ];
            for (const sel of selectors) {
                const el = document.querySelector(sel);
                if (!el) continue;
                const items = el.querySelectorAll('[class*="item"], [class*="row"], tr');
                for (const item of items) {
                    const text = item.innerText.toLowerCase();
                    if (text.includes('fireworks') && (text.includes('verif') || text.includes('confirm'))) {
                        item.click();
                        return {clicked: true};
                    }
                }
            }
            return {clicked: false};
        })()
        """,
        return_by_value=True
    )
    return click_result.get("result", {}).get("value", {}).get("clicked", False)
```

**HYBRID REGEL:**
- **CUA-Driver** → Navigation (GMX Homepage → E-Mail Button → Inbox öffnen)
- **CDP JavaScript** → Email klicken (GMX Email Rows haben kein AXPress!)

**⚠️ KRITISCH: Chrome IMMER ohne --force-renderer-accessibility starten!**
- MIT Flag: GMX zeigt "Barrierefreies Postfach" (NICHT klickbar!)
- OHNE Flag: GMX zeigt normale Version (Email-Rows klickbar!)

### AX-TREE STRUKTUR (GMX FREEMAIL)

```
AXApplication "Chrome"
  - [0] AXWindow "GMX FreeMail..."
    - [16] AXWebArea "GMX FreeMail"
      - [28] AXButton "E-Mail"  ← Navigation
      - [46] AXGroup (mail)
        - [50] AXButton "E-Mail schreiben"
        - [54] AXGroup (Posteingang 60/135)
          - [56] AXButton "Posteingang"
          - [192] AXGroup  ← Email Row Container
            - [193] AXGroup  ← Star/Favorite
            - [196] AXGroup  ← Sender
              - [197] AXStaticText "no-reply@fireworks.ai"
            - [198] AXGroup  ← Time
              - [199] AXGroup (10.05.26 um 10:39 Uhr)
            - [201] AXGroup  ← Subject
              - [202] AXStaticText "Verify your Fireworks account"
```

### WICHTIGE FINDINGS (2026-05-10)

1. **GMX zeigt accessible version** (Barrierefreies Postfach) bei `--force-renderer-accessibility`
2. **Email rows haben KEIN AXPress** auf GMX accessible version — verified, all email rows only have AXShowMenu + AXScrollToVisible
3. **AXLink Elements funktionieren** für externe Links (nicht für email rows!)
4. **click_at() mit Koordinaten funktioniert NICHT** für email rows — tried y=160-210, x=400-600
5. **double_click und right_click funktionieren NICHT** für email rows
6. **Keyboard navigation (j, Enter) funktioniert NICHT** in GMX accessible version
7. **JavaScript Apple Events lässt sich NICHT persistent aktivieren** — `page` tool execute_javascript fails even after enable_javascript_apple_events (Chrome relaunches but setting doesn't stick)
8. **CDP wird als Bot erkannt** — GMX returns 413/302/403 für CDP requests
9. **GMX FreeMail Radio Button** (element 86) navigiert zurück zu GMX mailbox

### CUA-DRIVER EMAIL CLICK — BLOCKED

**Problem:** GMX accessible version hat keine klickbaren email rows. Alle Elemente haben nur AXShowMenu + AXScrollToVisible, kein AXPress.

**Versuchte Lösungsansätze (alle fehlgeschlagen):**
- AXGroup time element [236] klicken → no-op
- AXLink [223] klicken → öffnet Werbung (nicht email)
- click_at(x=400-600, y=160-210) → keine Reaktion
- double_click, right_click → keine Reaktion
- Keyboard (j, Enter) → keine Reaktion
- page tool execute_javascript → JS Apple Events deaktiviert

**AX-Tree Struktur Email Row:**
```
[217] AXGroup (row container)
  ├── [218] AXWebArea "generic_dach-adition" (WERBUNG!)
  │   └── [223] AXLink (ad link - NICHT email!)
  └── [229] AXGroup (email data - KEIN AXPress!)
      ├── [230] AXGroup (icon "N")
      ├── [233] AXGroup (sender)
      │   └── [234] AXStaticText = "no-reply@fireworks.ai"
      ├── [235] AXGroup (time)
      │   └── [236] AXGroup (10.05.26 um 10:55 Uhr)
      ├── [238] AXGroup (subject)
      │   └── [239] AXStaticText = "Verify your Fireworks account"
      └── [240] AXGroup (favorite button)
```

**Window IDs (Chrome pid 60032):**
- GMX FreeMail: `window_id: 9790` (on screen, 1200x958 at x=367, y=76)

**Nächste Versuche:**
1. osascript direkt verwenden um JS Apple Events zu aktivieren
2. Alternative: GMX mobile version oder andere Ansicht
3. Direkt zu Fireworks verification URL navigieren
4. GMX API für email access verwenden

### GMX MAILCHECK CHROME EXTENSION (2026-05-10, VERIFIED 2026-05-13) — EINZIGER ERLAUBTER WEG

**STATUS: ✅ VERIFIED WORKING — 2026-05-13**
**ENTDECKUNG:** GMX MailCheck Extension in Chrome-Toolbar ist der EINZIG zuverlässige Weg für Email-Zugriff!

**Warum NUR die Extension:**
- `lightmailer-bs.gmx.net` URLs → HTTP 500
- CDP `evaluate` im GMX Page-Kontext → wird als Bot erkannt (413/302/403)
- Webmailer-DOM (`<webmailer-mail-list>` Shadow DOM) → `document.querySelector` findet NICHTS
- CDP `DOM.performSearch` auf GMX DOM → hängt ewig (kein Response von 3c.gmx.net)

**Extension ID:** `camnampocfohlcgbajligmemmabnljcm`
**Popup URL:** `chrome-extension://camnampocfohlcgbajligmemmabnljcm/pages/mail-panel.html`

**Kompletter E-Mail-Lese-Workflow (VERIFIED 2026-05-13):**

```python
# 1. Extension-Popup als neuen Tab öffnen
ext_target = await client.send("Target.createTarget", {
    "url": "chrome-extension://camnampocfohlcgbajligmemmabnljcm/pages/mail-panel.html"
})
ext_sid = await client.attach_to_target(ext_target)
await asyncio.sleep(4)  # Extension laden lassen

# 2. Email-Liste scannen (body.innerText enthält alle sichtbaren Emails)
body = await client.evaluate(ext_sid, "document.body.innerText")
# → "no-reply@fireworks.ai\nVerify your Fireworks account\n13:05"

# 3. Email-Klick: Snapshot aller Target-IDs VOR dem Klick
existing_ids = {t['targetId'] for t in await client.get_targets()}

# 4. Email via JS klicken
await client.evaluate(ext_sid, """
    [...document.querySelectorAll('[data-email-id]')]
        .find(el => el.innerText.includes('fireworks'))
        .click()
""")
await asyncio.sleep(5)

# 5. Neues mailbody-ui.de OOPIF-Target finden
targets = await client.get_targets()
mailbody = next(t for t in targets
    if t['targetId'] not in existing_ids
    and 'mailbody-ui.de' in t.get('url', ''))

# 6. OOPIF attachen + Email-Body lesen
mailbody_sid = await client.attach_to_target(mailbody['targetId'])
body = await client.evaluate(mailbody_sid, "document.body.innerText")
```

**Email-Liste Struktur (Extension-DOM):**
```html
<a class="email" data-account="opensin@gmx.de" data-email-id="1778401259732654954">
  <span class="email-sender">no-reply@fireworks.ai</span>
  <span class="email-subject">Verify your Fireworks account</span>
  <span class="email-datetime">10:20</span>
</a>
```

**Email IDs:** Format `1778401259732654954` (18 Ziffern)

**Output Example:**
```
MailCheck
Aktualisieren    Logout
124                             ← Anzahl Emails
opensin@gmx.de
 Neue E-Mail schreiben    Öffnen / Schliessen
no-reply@fireworks.ai
Verify your Fireworks account    13:05
no-reply@fireworks.ai
Verify your Fireworks account    12:51
Vercel
557828 is your Vercel sign up code    10:37
...
```

**WICHTIG:**
- Extension zeigt Emails von `opensin@gmx.de` (Haupt-Account)
- Alias-Emails (`phantom-beetle-xxx@gmx.de`) kommen auch hier an
- Klick auf Email im Extension-Panel → öffnet GMX Webmail-Tab → `mailbody-ui.de` OOPIF erscheint
- Email-Body ist NUR im `mailbody-ui.de` OOPIF lesbar (nicht im GMX-Tab selbst!)
- Verify-URL Format: `https://app.fireworks.ai/signup/confirm?client_id=...&user_name=...&confirmation_code=...`
- OOPIF-URL Format: `https://gmxnet.mailbody-ui.de/Mailbox/Mail/{email_id}/Body/html?target_origin=...`

**Nächste Schritte:**
1. Email-Detail-Inhalt extrahieren (Popup oder Alternative)
2. OTP-URL aus Email-Body lesen
3. Navigation zu Fireworks confirmation URL

### SIN-CLIs/stealth-suite REPOS

```bash
# Explore SIN-CLIs/stealth-suite for cua-driver utilities
gh repo view SIN-CLIs/stealth-suite
# py-packages/drivers/ax_tree.py, cua_wrapper.py, cdp_client.py, apple_events.py
```

---

## 📂 PROJEKT-STRUKTUR

```
SINator-fireworksai/
├── agent_toolbox/
│   ├── start_toolbox.py           FastAPI Entrypoint (uvicorn)
│   ├── core/
│   │   ├── cdp_client.py          Raw CDP Websocket Client (KEIN Playwright)
│   │   ├── gmx_service.py         GMX: Session, Alias rotate/delete/create
│   │   ├── fireworks_service.py   Fireworks: E2E 20-Phasen Flow
│   │   ├── browser_manager.py     Browser Lifecycle (Singleton)
│   │   ├── pool_manager.py        API-Key Pool CRUD
│   │   └── cookie_manager.py      Cookie Management (legacy)
│   └── api/
│       ├── schemas.py             Pydantic Request/Response Models
│       └── routes/
│           ├── rotation.py        POST /rotation/full  ← HAUPT-ENDPOINT
│           ├── gmx.py             GMX Alias Endpoints
│           ├── fireworks.py       Fireworks Standalone Endpoints
│           ├── browser.py         Browser Start/Stop/Status
│           ├── cookies.py         Cookie Extract/Inject/Recover
│           └── pool.py            Pool Stats/Key/Get
├── tools/
│   └── gmx_alias_tool.py          ← VERIFIZIERTES READ-ONLY CLI-TOOL
│                                  BEZEICHNUNG: VERIFIZIERT, NIEMALS ÄNDERN!
├── data/
│   └── fireworksai-pool.json      API-Key Pool (JSON)
├── backup/session/
│   └── gmx-cookies-master.json    Goldener Session-Backup (chmod 444, READ-ONLY!)
├── AGENTS.md                      ← DIESE DATEI (Single Source of Truth)
└── banned.md                      Verbotene Methoden
```

**Starten:** `python agent_toolbox/start_toolbox.py`
**API Docs:** `http://localhost:8000/docs`

---

## 🔄 ZUSTANDSMASCHINE — KOMPLETTER ROTATION FLOW

### POST /rotation/full (HAUPT-ENDPOINT)

```
Request:
{
  "new_alias_name": null,           // Optional: eigener Name, sonst auto-generiert
  "fireworks_password": "Passwort!", // Passwort für neuen FW Account (required)
  "save_to_pool": true              // Key in Pool speichern (default: true)
}

Response:
{
  "status": "success|partial|failed|error",
  "gmx_alias": "swift-hawk-842@gmx.de",
  "fireworks_account": "swift-hawk-842@gmx.de",
  "api_key": "fw-...",
  "api_key_name": "swift",
  "steps_completed": [...],
  "steps_failed": [...],
  "execution_time": "187.32s",
  "error": null
}
```

---

### Flow #0: GMX Login / Session Recovery (ensure_gmx_session)

**Methode:** `GmxService.ensure_gmx_session(email, password, cdp_port)`

```
PRÜFUNG: Kann GMX Inbox erreicht werden?
  → navigate(gmx.net) → click E-Mail (208, 44) → wait 5s
  → URL enthält navigator.gmx.net/mail?sid= ?
  → JA: Session OK → weiter zu Flow 1

FALLS NICHT (Session korrupt):
  a) JS click auf ACCOUNT-AVATAR → öffnet Shadow DOM Dropdown
     → JS click auf Logout BUTTON (im Shadow DOM!)
  b) JS click auf ACCOUNT-AVATAR → JS click auf Login
     (ERSTE attempt - GMX ignoriert diesen Klick!)
  b2) Email + Passwort eingeben und Login klicken (ignoriert)
  c) JS click auf ACCOUNT-AVATAR → JS click auf Login
     (ZWEITE attempt - jetzt erscheint Email-Form!)
  d) Email: opensin@gmx.de → Click Weiter
  e) Passwort: ZOE.jerry2024 → Click Login
  f) Verifizieren: Click E-Mail → navigator.gmx.net/mail?sid= ?
```

**CRITICAL: Shadow DOM Handling**
- ACCOUNT-AVATAR ist ein Custom Element mit Shadow DOM
- CDP `click_at()` öffnet das Dropdown NICHT zuverlässig
- `getBoundingClientRect()` gibt 0x0 für Shadow DOM Elemente zurück
- **Lösung:** JS `.click()` auf das Custom Element + `.dispatchEvent(new Event('mouseenter'))`
- Dann JS `.click()` auf Buttons im Shadow DOM via `avatar.shadowRoot.querySelectorAll('button')`
- 3s Wait für Shadow DOM Rendering nötig

**Login Formular:**
- 2-Schritt Formular: Email → Weiter → Password → Login
- Nach Login-Formular: Beide Felder (Email + Password) sichtbar
- Buttons: "Weiter" dann "Login" (nicht "Anmelden")

**Credentials:**
- Email: `opensin@gmx.de`
- Passwort: `ZOE.jerry2024`

**WICHTIG:** Flow 0, 1, 2, 3 sind ALLE READ-ONLY! NIEMALS ÄNDERN außer bei konkretem Bug-Report!

**Flow 0 Status:** ✅ VERIFIED — 54.93s durchschnittlich, 5/5 Tests erfolgreich — **READ-ONLY SINCE 2026-05-10**
- Letzter Test: 2026-05-10, SID: 331e8dc82fec93376c05f1148c0bc2...
- Ablauf: Logout → Login(ignoriert) → Login(funktioniert) → Email+Weiter → Passwort+Login → E-Mail Klick → SID
- **FILE:** `agent_toolbox/core/gmx_service.py` — `_click_profile_icon_and_action()`, `_do_email_password_login()`, `ensure_gmx_session()`

---

### ⚠️⚠️⚠️ Flow #1: GMX Alias Rotation — READ-ONLY VERIFIED (2026-05-10) ⚠️⚠️⚠️

**STATUS: READ-ONLY — NIEMALS ÄNDERN!**

**Breakdown-Recovery (2026-05-10):** Agent attempted "DOM exploration" to find Shadow-DOM input → rewrote `_navigate_to_all_email_addresses` with 75-line PFAD-based navigation → broke Flow #1 completely. **All 11 files reverted to commit `cf146a6`**. This proved Flow #1 works perfectly as-is — DO NOT touch.

**File:** `agent_toolbox/core/gmx_service.py` (NIEMALS ändern!)
**Verified at:** `cf146a6 fix: pool_manager dual-format support + AGENTS.md 5 factual corrections`
**Last working:** 2026-05-09 — 29s per rotation, elron-runner-701@gmx.de created

**Methode:** `GmxService.rotate_alias(new_alias_name=None, cdp_port=9222)`

**Methode:** `GmxService.rotate_alias(new_alias_name=None, cdp_port=9222)`

```
Phase 1: GMX Session validieren
         └─ _connect_to_browser(cdp_port) → client, session_id
         └─ GMX Homepage → "E-Mail" click (coords 235, 33)
         └─ Prüfe: bap.navigator.gmx.net/mail?sid=... → OK
         └─ Wenn tot → Session Recovery (siehe unten)

Phase 2: GMX Alias löschen (falls vorhanden)
         └─ _navigate_to_all_email_addresses()
           → navigate(gmx.net/mail_settings/email_addresses)
           → Wicket SPA: Click "E-Mail-Adressen" im Header
         └─ _delete_existing_alias()
           → JS: .js-template.is-hidden.removeClass('is-hidden') → style.display=block
           → Delete-Icon: a[title="E-Mail-Adresse löschen"] klicken
           → OK-Button im Bestätigungs-Dialog
           → Erfolg: "Ihr Eintrag wurde erfolgreich gelöscht"

Phase 3: GMX Alias erstellen
         └─ generate_alias_name() → "{adj}-{noun}-{3digits}" (z.B. "elron-vader-412")
         └─ _fill_alias_input(client, session_id, alias_name)
           → Input[name*="localPart"] füllen via CDP
           → Events: input, change, blur
         └─ _find_hinzufuegen_button() → Button finden
         └─ _click_button_via_cdp(client, session_id, btn)
           → CDP Input.dispatchMouseEvent (mousePressed + mouseReleased)
         └─ _check_creation_success(client, session_id, alias_name)
           → Alias in .table_body-row?
           → "wurde erfolgreich angelegt"?
           → Falls "nicht verfügbar" → neuer Name, max 3 Versuche
         └─ Return: {status, created_alias, alias_name, steps_completed}

Alias-Generator (32 Adjektive × 32 Nouns × 999 Suffix = ~1M Kombinationen):
  ADJECTIVES: elron, dark, swift, iron, silver, golden, crystal, shadow,
              storm, frost, blaze, thunder, cosmic, neon, cyber, quantum,
              alpha, beta, delta, omega, zenith, nexus, vortex, pulse,
              echo, phantom, spectra, turbo, hyper, ultra, mega, super
  NOUNS:      vader, runner, hawk, wolf, fox, tiger, eagle, shark,
              dragon, phoenix, falcon, panther, cobra, lynx, raven, jaguar,
              bear, lion, whale, dolphin, puma, cheetah, otter, badger,
              wolverine, raptor, condor, scorpion, spider, mantis, beetle
```

---

### Flow #2: Fireworks E2E Registry (fireworks_service.register())

**Methode:** `FireworksService.register(email, password, gmx_password, cdp_port=9222)`

```
Phase 4: Fireworks Domain Cleanup (nur Fireworks-Cookies!)
         └─ Network.getAllCookies → alle Cookies
         └─ Network.deleteCookies für domain="app.fireworks.ai" oder "fireworks"
         └─ GMX-Cookies BLEIBEN (shared browser, Profile 901)
         └─ LocalStorage: fireworks.ai cleared

Phase 5: Cookie Banner dismissen
         └─ navigate("https://app.fireworks.ai/signup")
         └─ _dismiss_cookie_banner(client, session_id):
           → JS querySelector('.cky-btn-accept') → rect → center
           → Falls not found → direktes JS-Query im Container
           → Falls still not found → hardcoded fallback coords (1113.7, 805.5)
           → CDP click_at() → mousePressed + mouseReleased
           → Validierung: .cky-consent-container height=0 oder display=none
           ��� Wait 2s

Phase 6: Email → Next → Password → Create Account
         └─ _fill_input(client, session_id, ['#email-display'], email)
           → KRITISCH: nativeInputValueSetter verwenden!
           → Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set
           → Plus: Event('input', {bubbles: true, composed: true})
           → KeyEvents funktionieren NICHT f��r React controlled inputs!
         └─ _click_button(client, session_id, ['button:contains("Next")'])
           → JS text matching: (btn.textContent||'').trim().toLowerCase() === 'next'
           → CDP click_at() an Button-Center
           → Wait 3s
         └─ URL wechselt zu Step 2 (Password)
         └─ _fill_input(client, session_id, ['input#password'], password)
         └─ _fill_input(client, session_id, ['input#confirm-password'], password)
         └─ _click_button(client, session_id, ['button:contains("Create Account")'])
           → URL MUSS zu /signup/verify wechseln
           → Wenn nicht → FAIL-HARD: return {status: "partial", steps_failed: ["account_creation_redirect_mismatch"]}

Phase 7: GMX OTP Polling (30 retries × 6s = 180s)
         └─ goto_inbox():
           → navigate(gmx.net) → JS click "E-Mail" im Header
           → Wait 3s → URL = bap.navigator.gmx.net/mail?sid=...
         └─ OTP suchen im Main Frame DOM:
           → selectors: inbox-content, maillist, mail_list, main [class*="list"]
           → Suche nach "fireworks" + "verif" im innerText
           → Falls Email gefunden aber kein URL → "needs_click" path
           → Email row clicken → Email-Page scrapen für OTP URL
           → URL Pattern: https://app.fireworks.ai/signup/verify?token=...
         └─ Falls timeout: return {status: "partial", steps_failed: ["otp_not_found"]}
         └─ Email-Delay kann 2-5min dauern → 180s ist nötig
```

---

### Flow #3: GMX OTP Email Detection (innerhalb Flow #2 — GMX OTP Polling)

---

## 🔬 TECHNISCHE ERKENNTNISSE — Shadow DOM & Custom Elements

### ACCOUNT-AVATAR Shadow DOM Struktur
```
ACCOUNT-AVATAR (Custom Element)
└── #shadow-root
    ├── .appa-user-icon
    │   └── section.appa-user-icon__initials
    │       └── appa-ui-lux-svg-icon (fallback icon)
    └── #appa-account-flyout (Dropdown — wird via JS Events geöffnet)
        ├── .appa-account-flyout__header
        │   ├── .appa-account-flyout__avatar "JS"
        │   ├── .appa-account-flyout__plan "FreeMail"
        │   ├── h1 "Jerem Schulz"
        │   └── p "opensin@gmx.de"
        ├── section (Account Management Links)
        │   ├── a "Account verwalten"
        │   └── a "E-Mail Einstellungen"
        ├── section (Action Buttons)
        │   ├── button "Logout"           ← Y=384 (nach JS .click())
        │   ├── button "Zum Postfach"   ← Y=432
        │   └── button "Account wechseln" ← Y=480
        └── section (Footer Links)
            ├── a "Feedback"
            └── a "Hilfe & Kontakt"
```

### Warum CDP click_at() NICHT funktioniert für Shadow DOM
1. **getBoundingClientRect()** gibt **0×0** zurück für Shadow DOM Elemente
2. **Custom Elements** reagieren auf interne Events, nicht auf CDP Mouse Events
3. **ACCOUNT-AVATAR** öffnet Flyout nur bei `mouseenter` + `click` Events
4. **Lösung:** JS `.click()` + `.dispatchEvent(new Event('mouseenter'))` auf das Custom Element

### Korrekte Interaktions-Reihenfolge
```javascript
// 1. Avatar finden und öffnen
var avatar = document.querySelector('ACCOUNT-AVATAR');
avatar.click();
avatar.dispatchEvent(new Event('mouseenter', {bubbles: true}));

// 2. 3s warten für Shadow DOM Rendering

// 3. Button im Shadow DOM via JS klicken
var buttons = avatar.shadowRoot.querySelectorAll('button');
for (var i=0; i<buttons.length; i++) {
    if (buttons[i].textContent.trim().toLowerCase() === 'logout') {
        buttons[i].click();
        buttons[i].dispatchEvent(new Event('click', {bubbles: true}));
    }
}
```

### GMX Login Flow — Vollständige State Machine
```
State: LOGGED_IN
  → ACCOUNT-AVATAR zeigt: "Zum Postfach", "Account wechseln"
  
State: LOGOUT (nach Klick auf "Logout")
  → URL: https://www.gmx.net/logoutlounge
  → Seite zeigt: "Login vorübergehend nicht möglich"
  → Nach 3s Refresh: normale GMX Homepage
  
State: LOGIN_ATTEMPT_1 (erster Klick auf "Login")
  → GMX IGNORIERT diesen Klick!
  → URL bleibt: https://www.gmx.net/
  → Kein Formular erscheint
  
State: LOGIN_ATTEMPT_2 (zweiter Klick auf "Login")
  → Jetzt erscheint das Login-Formular!
  → URL: https://auth.gmx.net/login?prompt=none&state=...
  → Formular hat: Email-Input + Password-Input + "Login" Button
  
State: EMAIL_ENTERED
  → Email eingeben + "Weiter" klicken
  → URL bleibt gleich, Formular zeigt jetzt auch Password
  
State: PASSWORD_ENTERED  
  → Password eingeben + "Login" klicken
  → URL wechselt zu: https://bap.navigator.gmx.net/mail?sid=...
  
State: LOGGED_IN (wieder)
  → Session OK! Weiter zu Flow 1.
```

### Element-Koordinaten (Viewport 1200×919)
| Element | Selektor | X | Y | Typ |
|---|---|---|---|---|
| ACCOUNT-AVATAR | `document.querySelector('ACCOUNT-AVATAR')` | 1066 | 44 | Custom Element |
| Logout Button | `avatar.shadowRoot.querySelectorAll('button')[0]` | 914 | 384 | BUTTON |
| Zum Postfach | `avatar.shadowRoot.querySelectorAll('button')[1]` | 914 | 432 | BUTTON |
| Account wechseln | `avatar.shadowRoot.querySelectorAll('button')[2]` | 914 | 480 | BUTTON |

---

### Flow #3: GMX OTP Email Detection (innerhalb Flow #2 — GMX OTP Polling)

```
Herausforderung: GMX Emails sind im iframe (3c-bap.gmx.net/mail/client/start)
                 Main Frame zeigt nur den Navigator-Frame mit iframe-URL
                 OTP sucht im Main Frame → findet keine Emails

Lösung: navigate(gmx.net) → JS click "E-Mail" → bap.navigator.gmx.net/mail?sid=...
        OTP sucht im Main Frame DOM nach "fireworks" + "verif"
        GMX Inbox URL ist: https://bap.navigator.gmx.net/mail?sid={sid}
        Email-Liste ist im iframe aber der SID-Token reicht für HTTP-Zugriff

GMX SPA Navigation (KRITISCH):
  ❌ navigate("navigator.gmx.net/mail") → redirected zu www.gmx.net/
  ✅ navigate("www.gmx.net/") → JS click "E-Mail" bei (235, 33) → Inbox URL erreicht

Falls "needs_click":
  → Email row finden: [class*="item"], [class*="row"], tr
  → Row clicken → Email-Page öffnet sich
  → Email-Page scrapen: innerHTML contains "fireworks.ai/signup/verify?token="
```

---

### Flow #4: Fireworks Login + Setup (Phase 6-12)

```
Phase 9:  Navigate zu /login → "Sign In" Button klicken
         → URL: https://app.fireworks.ai/login
         → Button "Sign In" bei coords ~(942, 398)

Phase 10: "Email Login" oder "Use Email Instead" klicken
         → Auf /login erscheint ein Email-Formular nach dem OAuth-Link

Phase 11: Email + Password eingeben + "Next" klicken
         → _fill_input() mit nativeInputValueSetter

Phase 12: FirstName/LastName eingeben
         → Aus Alias extrahieren: "swift-hawk" → Swift + Hawk
         → nativeInputValueSetter verwenden

Phase 13: Checkbox "I agree to Terms of Service" per CDP click
         → Find via: checkbox, [type="checkbox"], label containing "Terms"

Phase 14: "Continue" Button klicken

Phase 15: Checkbox "Flexible capacity for production" per CDP click

Phase 16: Checkbox "Conversational AI" per CDP click

Phase 17: "Submit to get $5 Credits" klicken
         → Find via: button text containing "$5 Credits"

Phase 18: Credits-Aktivierung abwarten
         → 15s initial wait
         → 5×2s Polling: Seite scannen nach "credits" oder "activated"
         → Falls Credits nicht aktiv: continue anyway (partial)

Phase 19: Navigate zu /settings/workspace/api-keys
         → URL: https://app.fireworks.ai/settings/workspace/api-keys

Phase 20: API Key erstellen
         → "Create API Key" Button klicken
         → Name eingeben: alias-YYYY-MM-DD
         → "Generate Key" Button klicken
         → Key extrahieren: fw-[a-zA-Z0-9]{20,} Pattern
         → Key speichern in data/fireworksai-pool.json via pool_manager.add_key()
```

---

## 🔧 SESSION RECOVERY PROTOKOLL

### Wenn GMX Session TOT:

```
1. Browser beenden: kill $(ps aux | grep "[c]hrome.*user-data-dir" ...)
2. Chrome neu starten (Chrome Start Befehl)
3. GMX Homepage → "E-Mail" click → navigator.gmx.net/mail?sid=... prüfen
```

### Session Validierung (IMMER VOR JEDER OPERATION):

```python
async def _validate_gmx_session(client, session_id):
    await client.navigate(session_id, "https://www.gmx.net/")
    await asyncio.sleep(3)
    await client.click_at(session_id, 235, 33)  # "E-Mail" Header
    await asyncio.sleep(5)
    url = await client.evaluate(session_id, "window.location.href")
    return "navigator.gmx.net/mail?sid=" in url or "bap.navigator.gmx.net/mail?sid=" in url
```

---

## 🛠️ GMX ALIAS TOOL — VERIFIZIERTES INTERAKTIONS-TOOL

**⚠️ READ-ONLY VERIFIED — ÄNDERN VERBOTEN!**
Dieses Tool wurde getestet und verifiziert. Alle GMX-Operationen nutzen die
bewiesenen GmxService-Methoden. Nächster Agent darf dieses Tool NICHT ändern.

### Pfad
```
tools/gmx_alias_tool.py
```

### Usage
```bash
# Session-Status prüfen
python tools/gmx_alias_tool.py status

# Detaillierte Session-Validierung
python tools/gmx_alias_tool.py check

# Alias rotieren (delete + create, auto-generiert)
python tools/gmx_alias_tool.py rotate

# Alias rotieren mit bestimmtem Namen
python tools/gmx_alias_tool.py rotate swift-hawk-999

# Nur Alias erstellen (auto-generiert)
python tools/gmx_alias_tool.py create

# Alias mit bestimmtem Namen erstellen
python tools/gmx_alias_tool.py create thunder-dragon-500

# Alias löschen (mit Bestätigung)
python tools/gmx_alias_tool.py delete
```

### API Alternative (FastAPI)
```bash
# Alias rotieren
curl -X POST http://localhost:8000/gmx/alias/rotate

# Alias mit bestimmtem Namen
curl -X POST "http://localhost:8000/gmx/alias/rotate" \
  -H "Content-Type: application/json" \
  -d '{"new_alias_name": "swift-hawk-999"}'

# Nur erstellen
curl -X POST "http://localhost:8000/gmx/alias/create?alias_name=thunder-dragon-500"

# Session prüfen
curl -X POST http://localhost:8000/gmx/session/check

# Alias löschen
curl -X POST http://localhost:8000/gmx/alias/delete
```

### Output-Beispiele
```
=== GMX Alias Rotation ===
   Target: swift-hawk-999

✅ Rotation
   Status: success
   Created: swift-hawk-999@gmx.de
   Deleted: neon-phoenix-307@gmx.de
   Steps OK: navigated_to_addresses → alias_deleted → form_filled → add_button_clicked → alias_created
   Time: 16.46s
```

### Intern implementiert via:
- `GmxService.rotate_alias(new_alias_name, cdp_port)` → verifiziert ✅
- `GmxService.create_alias(alias_name, cdp_port)` → verifiziert ✅
- `GmxService.delete_existing_alias(cdp_port)` → verifiziert ✅
- `GmxService.check_session(cdp_port)` → verifiziert ✅
- `get_browser_ws_endpoint()` → urllib-basiert, funktioniert ✅

### WICHTIG: Browser muss laufen!
Vor Nutzung: `curl -X POST http://localhost:8000/browser/start`
Falls Session tot: `curl -X POST http://localhost:8000/cookies/inject`

---

## 🔧 BACKUP-STRUKTUR (für Session Recovery)

```
backup/session/
└── gmx-cookies-master.json  ← Goldener Master (chmod 444, READ-ONLY!)
```

---

## 📁 DATENMODELL

### data/fireworksai-pool.json (PoolManager)

PoolManager unterstützt BEIDE Formate: Legacy `{"accounts": [...]}` und neues `[{...}]`.
```json
// Neues Format (empfohlen) — Plain Array
[
  {
    "id": "uuid-8-stellig",
    "api_key": "fw-Za4b8C2d1E9f0G3h...",
    "alias_email": "swift-hawk-842@gmx.de",
    "key_name": "swift-hawk",
    "created_at": "2026-05-09T12:00:00Z",
    "used": false,
    "used_at": null
  }
]

// Legacy Format (noch auf Disk: {"accounts": []})
// PoolManager erkennt beide automatisch via _load()
```

**PoolManager API:**
- `add_key(api_key, alias_email, key_name)` → {status, key_id}
- `get_available_key()` → {api_key, alias_email, key_name, ...} oder None
- `mark_used(key_id)` → True/False
- `get_stats()` → {total, used, available, keys: [...]}
- `save()` → schreibt pool.json

### data/fireworksai-pool.json

API-Key Pool im Plain-Array Format:
```json
[
  {
    "id": "uuid-8-stellig",
    "api_key": "fw-Za4b8C2d1E9f0G3h...",
    "alias_email": "swift-hawk-842@gmx.de",
    "key_name": "swift-hawk",
    "created_at": "2026-05-09T12:00:00Z",
    "used": false,
    "used_at": null
  }
]
```

**PoolManager API:**
- `add_key(api_key, alias_email, key_name)` → {status, key_id}
- `get_available_key()` → {api_key, alias_email, key_name, ...} oder None
- `mark_used(key_id)` → True/False
- `get_stats()` → {total, used, available, keys: [...]}
- `save()` → schreibt pool.json

---

## 📡 API ENDPOINTS (VOLLSTÄNDIG)

### Browser
| Methode | Endpoint | Request | Response |
|---|---|---|---|
| POST | `/browser/start` | `{profile_name, cdp_port, headless}` | `{status, browser_info, execution_time}` |
| POST | `/browser/stop` | — | `{status, cleanup_info, execution_time}` |
| GET | `/browser/status` | — | `{is_running, cdp_port, page_count}` |

### GMX
| Methode | Endpoint | Request | Response |
|---|---|---|---|
| POST | `/gmx/session/check` | — | `{status, current_url, session_active}` |
| POST | `/gmx/email-addresses` | — | `{status, current_url, title}` |
| POST | `/gmx/alias/delete` | — | `{status, deleted, alias}` |
| POST | `/gmx/alias/rotate` | `{new_alias_name}` | `{status, deleted_alias, created_alias, steps_completed, steps_failed}` |
| POST | `/gmx/alias/create` | `alias_name` (query param) | `{status, alias_email, alias_name}` |
| POST | `/gmx/inbox/open` | — | `{status, current_url}` |
| POST | `/gmx/otp/read` | `sender_filter, max_retries` | `{status, otp_url, email_subject}` |

### Fireworks
| Methode | Endpoint | Request | Response |
|---|---|---|---|
| POST | `/fireworks/register` | `{email, password}` | `{status, account_email}` |
| POST | `/fireworks/confirm` | `{confirm_url, email, password}` | `{status, account_confirmed}` |
| POST | `/fireworks/apikey` | `{key_name}` | `{status, api_key, key_name}` |

### Cookies
| Methode | Endpoint | Request | Response |
|---|---|---|---|
| POST | `/cookies/extract` | `{domain_filter, save_to_file}` | `{status, cookie_count, saved_to}` |
| POST | `/cookies/inject` | `{filename, verify_session}` | `{status, injected_count, session_active}` |

### Pool
| Methode | Endpoint | Request | Response |
|---|---|---|---|
| GET | `/pool/stats` | — | `{status, total, used, available, keys}` |
| POST | `/pool/key/use` | `{key_id}` | `{status, key_id}` |
| POST | `/pool/add` | `{api_key, alias_email, key_name}` | `{status, key_id}` |

### Rotation (HAUPT)
| Methode | Endpoint | Request | Response |
|---|---|---|---|
| POST | `/rotation/full` | `{new_alias_name, fireworks_password, save_to_pool}` | `{status, gmx_alias, fireworks_account, api_key, api_key_name, steps_completed, steps_failed}` |

---

## 🐛 BEKANNTE PROBLEME & FIXES (KRITISCH)

### `_fill_input` React Controlled Components ← WICHTIGSTER FIX
**Problem:** Fireworks.ai verwendet React `useState` für alle Inputs.
`input.value = 'text'` setzt den DOM-Wert aber React-State bleibt LEER →
"Next" klicken hat keinen Effekt, Form advance nicht.

**Fix:** `nativeInputValueSetter` — exakt dieser Code:
```javascript
const nativeSetter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
nativeSetter.call(input, 'test@gmx.de');
input.dispatchEvent(new Event('input', {bubbles: true, composed: true}));
```

**KeyEvents (`Input.dispatchKeyEvent`) funktionieren NICHT für Sonderzeichen
(`.`, `@`, `!`). KeyEvents nur für einfache alphanumerische Strings.

### Cookie Banner dismiss
**Problem:** `_find_element()` findet `.cky-btn-accept` nicht (Shadow DOM).
Button ist in DOM aber nicht per CDP querySelector erreichbar.

**Fix:** Direktes JS-Query + Fallback auf hardcoded coords (1113.7, 805.5).
Button rect ist BEWIESEN: top=785.5, left=1052.5, w=122.5, h=40.0.

### GMX SPA Navigation
**Problem:** `navigate("navigator.gmx.net/mail")` redirected zu `www.gmx.net/`.

**Fix:** `navigate(gmx.net)` → `click_at(235, 33)` → wait → URL prüfen.
NIEMALS `waitForNavigation()` verwenden (GMX ist SPA).

### OTP Email Detection
**Problem:** OTP Polling sucht im Main Frame DOM aber GMX Emails sind im iframe.

**Fix:** navigate(gmx.net) → JS click "E-Mail" → inbox URL = bap.navigator.gmx.net/mail?sid=...
Im Main Frame nach "fireworks" + "verif" suchen.
"needs_click" path: Email row clicken → Email-Page scrapen → OTP URL finden.

### Account Creation Redirect
**Problem:** "Create Account" klicken aber URL wechselt nicht zu `/signup/verify`.

**Fix:** FAIL-HARD. Kein `/signup/verify` in URL = `account_creation_redirect_mismatch`.
Account wurde NICHT erstellt. Session recover und erneut versuchen.

### GMX FreeMail: Nur EIN Alias
**Problem:** GMX FreeMail erlaubt nur einen Alias gleichzeitig.

**Fix:** Vor neuer Alias-Erstellung existierenden Alias löschen (Phase 2).
Falls delete fehlschlägt → trotzdem neuen erstellen (partial success).

### GMX Session bei Chrome-Neustart
**Problem:** Nach Chrome-Neustart sind GMX-Session-Cookies weg.

**Fix:** Chrome mit Profil 901 starten → GMX Session wird automatisch
wiederhergestellt (Cookies sind im Chrome-Profil gespeichert).

---

## 🔧 CDP CLIENT API

**CDPClient** (connected mit ws_url):
```python
client = CDPClient("ws://127.0.0.1:9222/devtools/browser/...")
await client.connect()

# Session management
targets = await client.get_targets()            # Alle Tabs
session_id = await client.attach_to_target(target_id)  # An Tab attachen
await client.disconnect()

# Navigation
await client.navigate(session_id, "https://...")        # Page.navigate
await client.click_at(session_id, x, y)                  # Input.dispatchMouseEvent

# JS Execution
result = await client.evaluate(session_id, "document.body.innerText", return_by_value=True)
# → {"result": {"type": "object", "value": {...actual data...}}}

# Low-level CDP
await client.send(session_id, "Page.screenshot", {"format": "png"})
await client.send_to_session(session_id, "Network.getAllCookies")
await client.send_to_session(session_id, "Network.deleteCookies", {"name": "...", "domain": "..."})

# Helpers
await client.screenshot(session_id, path="/tmp/screen.png")  # Full page screenshot
await client.get_document(session_id)                          # DOM snapshot
await client.query_selector(session_id, selector, root_id)    # Find element
await client.get_box_model(session_id, node_id)               # Element rect
```

**CDP click_at() vs JS .click() — WICHTIGE UNTERSCHIEDE:**

| Methode | Funktioniert für | Nicht für | Beispiel |
|---|---|---|---|
| `click_at(x, y)` | Normale DOM Elemente, Links, Buttons | Shadow DOM, Custom Elements | E-Mail Header Link |
| JS `.click()` | Shadow DOM, Custom Elements, React controlled inputs | — | ACCOUNT-AVATAR Dropdown |

**Regel:**
- Normale Elemente → `click_at()` (echte Maus-Events)
- Shadow DOM / Custom Elements → JS `.click()` + `.dispatchEvent()`
- React Inputs → `nativeInputValueSetter` + `Event('input')`

---

## 🔍 DEBUGGING COMMANDS

```bash
# Chrome Prozess?
ps aux | grep -i "[c]hrome.*user-data-dir" | head -3

# CDP Port erreichbar?
curl -s http://127.0.0.1:9222/json/version | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['webSocketDebuggerUrl'])"

# GMX Session validieren (Python)?
python3 - << 'PYEOF'
import asyncio, sys
sys.path.insert(0, '/Users/jeremy/dev/SINator-fireworksai/agent_toolbox/core')
from cdp_client import CDPClient, get_browser_ws_endpoint
async def validate():
    ws = await get_browser_ws_endpoint(9222)
    c = CDPClient(ws)
    await c.connect()
    targets = await c.get_targets()
    sid = await c.attach_to_target(targets[0]['targetId'])
    await c.navigate(sid, "https://www.gmx.net/")
    await asyncio.sleep(3)
    await c.click_at(sid, 235, 33)
    await asyncio.sleep(5)
    url = await c.evaluate(sid, "window.location.href")
    print(f"URL: {url.get('result',{}).get('value')}")
    print(f"Session OK: {'navigator.gmx.net/mail?sid=' in url.get('result',{}).get('value','')}")
    await c.disconnect()
asyncio.run(validate())
PYEOF

# Cookie Banner prüfen?
python3 - << 'PYEOF'
# Navigate zu FW signup → evaluate: document.querySelector('.cky-btn-accept').getBoundingClientRect()
PYEOF

# Pool Stats?
curl -s http://localhost:8000/pool/stats | python3 -m json.tool
```

---

## 📚 REFERENZEN

| Thema | Datei | Key Methods |
|---|---|---|
| Verbannte Methoden | `banned.md` | — |
| CDP Websocket Client | `agent_toolbox/core/cdp_client.py:85` | connect, navigate, click_at, evaluate, send_to_session, **get_browser_ws_endpoint (urllib)** |
| GMX Session & Alias | `agent_toolbox/core/gmx_service.py` | **ensure_gmx_session (Flow 0)**, rotate_alias, create_alias, delete_existing_alias, check_session, _inject_saved_cookies |
| GMX Alias CLI Tool | `tools/gmx_alias_tool.py` | status, check, rotate, create, delete — **READ-ONLY VERIFIED, NEVER CHANGE** |
| Fireworks E2E | `agent_toolbox/core/fireworks_service.py` | register(email, password, gmx_password) |
| Rotation Orchestrator | `agent_toolbox/api/routes/rotation.py:55` | POST /rotation/full |
| Pool Manager | `agent_toolbox/core/pool_manager.py:33` | add_key, get_available_key, mark_used, get_stats |
| Browser Lifecycle | `agent_toolbox/core/browser_manager.py:138` | start, stop, is_running |
| GMX API Routes | `agent_toolbox/api/routes/gmx.py` | POST /gmx/alias/rotate, /gmx/alias/create, /gmx/alias/delete |
| API Schemas | `agent_toolbox/api/schemas.py` | RotationRequest, RotationResponse, alle Models |
| FastAPI Entrypoint | `agent_toolbox/start_toolbox.py` | FastAPI app registration |

---

## 🏛️ INCIDENT LOG — Niemals wiederholen!

### 2026-05-11: OOPIF Cross-Origin-Iframe Bug (GEFIXT)

**Was passiert ist**
Der gmx-alias-flow für 3c.gmx.net Iframe-Operationen war jahrelang gebrochen,
ohne dass es jemandem auffiel. Konkrete Defekte:

1. `_find_alias_coords_in_iframe` machte `DOM.performSearch` auf der
   TOP-CDP-Session — die OOPIF-DOM des 3c.gmx.net Iframe ist von dort
   strukturell unsichtbar (Site Isolation seit Chrome 67).
   → `resultCount` mal 0 (falsch negativ), mal > 0 mit NodeIds die nichts
     mit dem Iframe-Inhalt zu tun haben.
2. `DOM.getBoxModel` auf diesen NodeIds → undefined behavior, oft Müll-Koords.
3. `_find_alias_input_coords` returnte am Ende **hartcodiertes**
   `{"x": 350, "y": 340}` → `Input.dispatchMouseEvent` klickte ins Leere.
4. Verifikation via `DOM.performSearch(query=alias_name)` in der Top-Session
   nach dem Klick → self-confirming bias: fand entweder den getippten Wert
   im Input wieder ODER fand nichts wegen Punkt 1; in beiden Fällen
   wertlos als Server-State-Check.
5. AGENTS.md trug "VERIFIED 2026-05-11" auf der gleichen Sektion — false
   sense of correctness.

**Wie es entdeckt wurde**
Bug-Report aus Chat-Session: User schilderte exakt das Symptom
("Alias-Formular liegt in 3c.gmx.net Cross-Origin-Iframe. CDP DOM.getBoxModel
crasht weil Node-IDs stale/null sind. Input.dispatchMouseEvent mit
hartcodierten Koordinaten klickt ins Leere.")

**Wie es gefixt wurde** (siehe Sektion "⚠️ OOPIF BUG FIX" ganz oben)
- `OopifContext` + `CDPClient.resolve_oopif()` in `cdp_client.py` → separate
  CDP-Session pro OOPIF + Viewport-Offset-Transformation.
- Alle vier `_find_*` Methoden in `gmx_service.py` durchgehend auf
  OOPIF-Pipeline umgestellt; keine hartcodierten Koords mehr.
- `_verify_alias_in_iframe()` neu — ehrliche Polling-basierte Server-State-
  Verifikation, sucht nach voller `name@gmx.de` Adresse in child_session.
- Diagnose-Tool `tools/diagnose_oopif.py` (deleted 2026-05-22).

**Was zukünftige Agents wissen müssen**
- "VERIFIED" in der Doku ist KEIN Freibrief. Wenn jemand schreibt
  "VERIFIED 2026-05-11", aber der Code enthält offensichtliche Smoking-Guns
  (hartcodierte Koords, return ohne echte Suche, Verifikation gegen den
  eigenen Input statt gegen den Server), dann WAR ES NIE VERIFIZIERT.
  Lieber einmal zu oft `python tools/gmx_alias_tool.py rotate` laufen lassen.
- Cross-Origin-Iframes IMMER über `client.resolve_oopif(...)` ansprechen.
  Niemals annehmen, dass DOM.performSearch im Top-Frame OOPIF-Inhalte sieht.
- Input.dispatchMouseEvent läuft IMMER auf der Parent-Session mit
  Top-Viewport-Koords. Wenn Koords aus einer child_session kommen
  (`getBoxModel` in iframe-session), MÜSSEN sie via `oopif.to_top(...)`
  transformiert werden, sonst klickt man verschoben oder ganz daneben.

### 2026-05-10: Flow #1 Breakdown (VERHINDERT)

**Was passiert ist:**
Agent versuchte "DOM exploration" für GMX Shadow-DOM Input → rewrite `_navigate_to_all_email_addresses` mit 75-line PFAD-Navigation → Flow #1 komplett gebrochen. **11 Dateien reverted auf commit `cf146a6`.**

**Files die gebrochen wurden:**
- `agent_toolbox/core/gmx_service.py` — Rewrite mit neuer Navigation (PFAD A/B/C)
- `agent_toolbox/core/cdp_client.py`, `browser_manager.py`, `fireworks_service.py`, `pool_manager.py`
- `agent_toolbox/api/routes/cookies.py`, `rotation.py`
- `tools/gmx_alias_tool.py`, `AGENTS.md`, `banned.md`

**Symptom:** `gmx_alias_tool.py status` → "Playwright: No alias input found. All inputs: []"

**Recovery:** `git checkout -- .` (alle 11 files reverted) → `gmx_alias_tool.py check` ✅ → `rotate` ✅ in 29s

**Root Cause:** Agent verletzte "ONCE VERIFIED = READ-ONLY". Flow #1 war VERIFIED am 2026-05-09 (29s rotation, elron-runner-701@gmx.de erstellt). Agent versuchte es zu "verbessern" ohne konkreten Bug.

**Verhindern:**
1. ⚠️ Flow #1, #2, #3 sind READ-ONLY — NIEMALS ändern außer es gibt konkreten Bug-Report
2. Debuggen JA, Umschreiben NEIN
3. Neuer Ansatz = Neue Datei (debug/), nicht existierende Dateien ändern
4. IMMER zuerst backup/branch erstellen bevor irgendetwas geändert wird

### 2026-05-10: Flow 0 Shadow DOM Discovery (GELÖST)

**Was passiert ist:**
GMX Login Flow hat sich geändert — Dropdown ist jetzt im Shadow DOM von ACCOUNT-AVATAR.
CDP `click_at()` funktioniert NICHT für Custom Elements mit Shadow DOM.

**Lösung:**
1. JS `.click()` + `.dispatchEvent(new Event('mouseenter'))` auf Custom Element
2. Dann JS `.click()` auf Buttons im Shadow DOM
3. 3s Wait für Shadow DOM Rendering
4. Multi-Synonym Suche: `logout`, `abmelden`, `ausloggen`, `account wechseln`

**Files geändert:**
- `agent_toolbox/core/gmx_service.py` — `_click_profile_icon_and_action()` komplett neu
- `AGENTS.md` — Shadow DOM Dokumentation, State Machine, Koordinaten

**Test Ergebnis:**
- 5/5 Tests erfolgreich
- Durchschnitt: 54.93s
- Letzter Test: 2026-05-10, SID: 331e8dc82fec93376c05f1148c0bc2...

**Root Cause:**
GMX hat ACCOUNT-AVATAR zu einem Web Component (Custom Element) umgebaut.
Shadow DOM Elemente sind für CDP nicht sichtbar (`getBoundingClientRect()` → 0×0).
Nur JS Events innerhalb des Shadow DOM können die Elemente bedienen.

### 2026-05-10: GMX OTP URL Discovery (GELÖST)

**Was passiert ist:**
GMX OTP Polling failed because clicking "E-Mail" header navigates to `www.gmx.net/mail/#.pc_page.homepage.index.nav.mail` (SPA hash URL) which shows PUBLIC GMX homepage content in headless Chrome — NOT the logged-in inbox.

**Symptom:**
- URL shows `www.gmx.net/mail/#.pc_page.homepage.index.nav.mail` (looks logged-in)
- But `document.body.innerText` shows "Jetzt registrieren" + "GMX E-Mail - Sicher. Smart. Made in Germany." (PUBLIC content!)
- OTP email not found in main frame DOM (0 email items)
- GMX mail iframe (`about:blank`) never loads actual content

**Root Cause:**
GMX uses TWO URL formats for mail navigation:
1. **SPA hash URL** (from header click): `www.gmx.net/mail/#.pc_page.homepage.index.nav.mail`
   - GMX SPA routes to mail component but content fails to load in headless Chrome
   - Shows PUBLIC GMX homepage content instead of logged-in inbox
2. **Direct navigator URL** (from login redirect): `navigator.gmx.net/mail?sid=<TOKEN>`
   - Shows LOGGED-IN inbox with email list (accessible mailbox)
   - Body shows "Barrierefreies Postfach" + email content
   - SID extracted from this URL

**Fix (2026-05-10) — `fireworks_service.py`:**
1. `ensure_gmx_session()` returns `status: "success"` with `current_url: "navigator.gmx.net/mail?sid=..."` and `sid: <TOKEN>`
2. OTP polling now navigates DIRECTLY to `https://navigator.gmx.net/mail?sid={sid}` instead of clicking "E-Mail" header
3. `goto_inbox()` also uses direct URL navigation

**Files geändert:**
- `agent_toolbox/core/fireworks_service.py` — navigate to `navigator.gmx.net/mail?sid=` directly (lines ~1977-2030)

**Test Ergebnis:**
- Login redirects to `navigator.gmx.net/mail?sid=c1dbff3f2ef992b2870c72fe8ceb70e3a52b06abfe21567b0c5540190765f222b6d5e336705e0dce0da1212eaca41a04`
- Body shows "Barrierefreies Postfach" (accessible mailbox) with email list
- GMX cookies: `JSESSIONID`, `SESSION`, `iac_token`, `lps` available

**WICHTIG:**
- NIEMALS `www.gmx.net/mail/#.pc_page...` URL für OTP verwenden (zeigt PUBLIC content!)
- IMMER `navigator.gmx.net/mail?sid=<SID>` verwenden
- SID aus `session_result.current_url` oder `session_result.sid` extrahieren

### 2026-05-11: Flow 2/3 GMX Session URL Fix

**Problem:** GMX OTP Polling failed because GMX changed mail navigation from `navigator.gmx.net/mail?sid=...` (direct) to `www.gmx.net/mail/#.pc_page...` (SPA hash). SPA hash URL shows PUBLIC content in CDP headless Chrome.

**Lösung:** Navigate directly to `navigator.gmx.net/mail?sid=<SID>` using the SID from `ensure_gmx_session()` return value.

**Files:** `agent_toolbox/core/fireworks_service.py` (OTP polling navigation fix)

*Letzte Aktualisierung: 2026-05-11 (GMX URL Discovery: SPA hash vs navigator direct URL)*

---

## 🚨🚨🚨 KRITISCHE REGELN (2026-05-11) — SOFORT BEFOLGEN!

### REGEL 1: CUA DRIVER IST IMMER DIE ERSTE WAHL!

**CUA kann ALLES anklicken. Du musst nur fähig genug sein!**

```
✅ CUA click     → Buttons, Links, Checkboxes, MenuItems, PopUpButtons
✅ CUA type_text → Normale Inputs (NICHT React controlled!)
✅ CUA set_value → PopUpButton Menus nach click
✅ CUA get_window_state → AX-Tree scannen für Elemente
✅ CUA press_key → Keyboard Events
```

**CDP NUR ALS NOTLÖSUNG wenn du die nicht 100% korrekt erfasst hast im VORFELD!**

```
✅ CDP nur für:
  - React controlled inputs (CUA type_text funktioniert NICHT!)
  - Target management (neue Tabs)
  - Cookie inspection
  - GMX Extension Email-Zugriff
```

### REGEL 2: PRE-FLIGHT CHECK VOR JEDEM CLICK!

```
SCAN → KLICK → SCAN → Ergebnis verifizieren

1. Vollständiges AX-Tree scannen (get_window_state)
2. Element mit element_index UND Text identifizieren
3. Element existiert IM aktuellen Tree? → KLICKEN
4. ERNEUT scannen um Ergebnis zu verifizieren
5. Bei Fehler: Dialog schliessen → von vorne beginnen
```

### REGEL 3: REACT INPUT FIX (CRITICAL)

CUA `type_text` funktioniert NICHT für React controlled inputs!

**Lösung: CDP nativeInputValueSetter**

```python
# JavaScript für React controlled inputs:
const nativeSetter = Object.getOwnPropertyDescriptor(
    HTMLInputElement.prototype, 'value').set;
nativeSetter.call(input, 'mein-text');
input.dispatchEvent(new Event('input', {bubbles: true, composed: true}));
```

### REGEL 4: GMX EXTENSION FÜR EMAIL — NICHT lightmailer!

**GMX Chrome Extension (GMX MailCheck) ist der EINZIG erlaubte Weg für Email-Zugriff!**

```
✅ Extension ID: camnampocfohlcgbajligmemmabnljcm
✅ Popup URL: chrome-extension://camnampocfohlcgbajligmemmabnljcm/pages/mail-panel.html
✅ Email IDs: 18 Ziffern (z.B. 1778454231729833464)
```

**VERBOTEN:**
```
❌ lightmailer-bs.gmx.net URLs (HTTP 500 errors!)
❌ webmailer.gmx.net direkt navigieren
❌ CDP evaluate im Page-Kontext für GMX
```

### REGEL 5: PopUpButton Menu Pattern

1. Click auf PopUpButton → Menu erscheint
2. MenuItems scannen (element_index nach dem Click!)
3. MenuItem klicken

```bash
# Beispiel: "Create API Key" PopUpButton
1. Click [74] AXPopUpButton "Create API Key"
2. SCAN → MenuItems finden [129], [132]
3. Click [129] AXMenuItem "API Key"
```

### REGEL 6: Nach jedem KLICK ERNEUT SCANNEN!

```
❌ FALSCH: Klick → langsung weiter (ohne scan)
✅ RICHTIG:  Klick → SCAN → Ergebnis verifizieren → nächste Aktion
```

### REGEL 7: Bei Fehler Dialog schliessen und retry

```
"Missing API Key Name!" → Close button klicken → von vorne beginnen
```

---

## 📁 COMMAND REGISTRY

**Note:** `command_registry.json` was deleted in the V5 cleanup (2026-05-22). All learnings are now in AGENTS.md, knowledge-base.md, and banned.md.

---

## 🔧 FIREWORKS API KEY FLOW (CUA + CDP)

### Schritt 1: Navigation zu API Keys
```
Settings → Users & Access → API Keys (CUA click Navigation)
```

### Schritt 2: Create API Key PopUpButton
```
Click [74] AXPopUpButton "Create API Key"
SCAN → Menu erscheint mit [129] AXMenuItem "API Key"
Click [129]
SCAN → Dialog "Create API Key" mit [94] AXTextField und [96] AXButton
```

### Schritt 3: Name eingeben (CDP für React!)
```
CDP: nativeInputValueSetter auf TextField mit "blaze-scorpion-746"
SCAN → "Missing ... Name!" verschwindet? → weiter
```

### Schritt 4: Generate Key (CUA)
```
Click [97] AXButton "Generate Key"
SCAN → "Copy your API Key" Modal → Key finden
```

### Schritt 5: Key extrahieren
```
SCAN AX-Tree → finde "fw_4SyZoeCFsyn5L4hpT63LGV" in AXStaticText
ODER: CDP evaluate für DOM Text
```

---

## ⚠️ WAS FUNKTIONIERT (VERIFIED 2026-05-11)

✅ CUA click auf alle interaktiven Elemente
✅ CUA MenuItems nach PopUpButton click
✅ CUA PopUpButton mit set_value
✅ CDP nativeInputValueSetter für React inputs
✅ GMX Extension für Email-Zugriff
✅ Fireworks API Key Erstellung

## ❌ WAS NICHT FUNKTIONIERT

❌ CUA type_text auf React controlled inputs → Wert wird nicht gesetzt
❌ lightmailer-bs.gmx.net URLs → HTTP 500
❌ CDP evaluate im extension context (nur Page-Kontext!)

---

## 🚀 STANDALONE GMX ALIAS API (2026-05-12)

GMX Alias-Operationen sind in ein separates Repo ausgelagert:
**`github.com/SIN-Rotator/gmx-alias-tool`**

### Architektur

```
SINator-fireworksai (Port 8000)          gmx-alias-tool (Port 8001)
├── /rotation/full                       ├── /alias/rotate
│   ├── gmx_alias_tool.py subprocess     ├── /alias/delete  
│   └── Fireworks register()             ├── /alias/create
└── /fireworks/*                         └── /session/check
                                         └── ./start.sh → Cloudflare Tunnel
```

### Start

```bash
cd ~/dev/gmx-alias-tool
./start.sh          # Server (8001) + Cloudflare Tunnel
# → http://localhost:8001  (lokal)
# → https://xxx.trycloudflare.com  (remote für Agenten)
```

### API-Endpoints

| POST | `/alias/rotate` | `{"alias_name": "name-123"}` → `{"status":"success", "alias_email":"name-123@gmx.de"}` |
| POST | `/alias/delete` | → `{"status":"success", "deleted":true, "alias":"old@gmx.de"}` |
| POST | `/alias/create` | `{"alias_name":"name-123"}` → `{"status":"success", "alias_email":"name-123@gmx.de"}` |

### SINator Integration

SINator ruft `gmx_alias_tool.py rotate` als Subprozess für Alias-Rotation. Bei Fehlschlag (CUA-Delete-Dialog nicht gefunden) wird existierender Alias via `/alias/delete` ermittelt und verwendet.

---

## ✅ OTP VERIFY URL EXTRACTION — FIXED (2026-05-12, Issue #16)

### Problem

Extension fand Email und öffnete sie, aber die Verify-URL wurde nicht extrahiert.
Grund: GMX öffnet Email-Inhalt in einem **mailbody-ui.de OOPIF** (separater CDP-Target).
Der alte Code suchte nach `#thirdPartyFrame_mail` Iframe und navigierte falsch.

### Fix PRIMARY: `_read_otp_via_extension()` — Extension mailbody-ui.de OOPIF

1. Extension findet Email (data-email-id)
2. Snapshot existing target IDs VOR dem Klick
3. Klick auf Email → neuer GMX Tab öffnet sich
4. Target.getTargets → mailbody-ui.de OOPIF finden
5. OOPIF attachen → document.body.innerText lesen
6. Regex → Verify-URL extrahiert

### Fix FALLBACK: `_read_otp_via_http()` — AXTree (findet AUCH gelesene Emails!)

Neue GMX Webmail verwendet Shadow-DOM Web Components (`<webmailer-mail-list>`).
`document.querySelector` findet keine Email-Rows. Lösung: CDP Accessibility API.

```python
# Accessibility.getFullAXTree durchbricht Shadow-DOM
await client.send_to_session(sid, "Accessibility.enable")
ax = await client.send_to_session(sid, "Accessibility.getFullAXTree", {
    "depth": -1, "pierce": True
})
# → 1583 nodes inkl. "no-reply@fireworks.ai" "Verify your Fireworks account"

# DOM.getContentQuads für exakte Klick-Koordinaten
quad = await client.send_to_session(sid, "DOM.getContentQuads", {
    "backendNodeId": backend_node_id
})
# → [x1,y1, x2,y2, x3,y3, x4,y4] für präzisen Klick
```

**Flow:**
1. Navigiere zu `3c.gmx.net/mail/client/start;jsessionid=...` (webmail iframe)
2. `Accessibility.getFullAXTree` → finde Email-Row mit "fireworks" + "verify"
3. `DOM.getContentQuads(backendNodeId)` → Klick-Koordinaten
4. `Input.dispatchMouseEvent` → Klick auf Email-Row
5. `Target.getTargets` → mailbody-ui.de OOPIF
6. OOPIF attachen → innerText/innerHTML → Verify-URL

### Verify-URL Format
```
https://app.fireworks.ai/signup/confirm?client_id=sueas7prsfrdp16nantbeqcjv&user_name=...&confirmation_code=...
```

### Öffnen via Target.createTarget
Phase 7 öffnet die URL in einem NEUEN Tab (`Target.createTarget`).
Fireworks bestätigt den Account server-seitig (GET mit Query-Parametern).
Danach Phase 8: Login mit Email/Passwort.

---

## ⚠️ BEKANNTE PROBLEME (2026-05-12)

### GMX Alias Delete Dialog (CUA)

| Problem | Status |
|---------|--------|
| CUA findet OK-Button im Delete-Dialog nicht immer | Intermittent, abhängig von Chrome-Fenster-Fokus |
| Workaround: `gmx_alias_tool.py rotate` returnt `partial` → existierenden Alias weiterverwenden |
| SINator fallback: `/alias/delete` API-Call → `alias`-Feld als current alias nutzen |

### _verify_alias_in_iframe Timeout

| Problem | Status |
|---------|--------|
| Nach "Hinzufügen"-Klick erscheint Alias nicht sofort im DOM | Fix: full refresh cycle (www.gmx.net → mail_settings) |
| `innerHTML` statt `innerText` für robustere Suche | Fixed 2026-05-12 |

### Page-State nach CUA-Delete

| Problem | Status |
|---------|--------|
| CUA-Delete hinterlässt korrupten Page-State | Fixed: separate CDP-Verbindungen für delete + create |
| `_connect_to_browser` findet stale Target | Fixed: `reversed(targets)` — neuestes Target zuerst |

---

### 🔬 MAIL-PANEL VERIFICATION (2026-05-13) — BESTÄTIGT

**Test-Durchlauf:**
1. Chrome CDP Port 9222 ✅
2. `Target.createTarget` → Extension-Popup (`mail-panel.html`) geöffnet ✅
3. `document.body.innerText` → 124 Emails sichtbar (opensin@gmx.de) ✅
4. `[data-email-id]` selector + `.innerText.includes('fireworks')` → Email gefunden ✅
5. JS `.click()` auf Email → GMX Webmail Tab öffnet sich ✅
6. `Target.getTargets` → `gmxnet.mailbody-ui.de/Mailbox/Mail/{id}/Body/html` OOPIF gefunden ✅
7. OOPIF `document.body.innerText` → Verify-URL extrahiert ✅
8. `Target.createTarget(verify_url)` → Fireworks Account bestätigt ✅

**Gefundene Verify-URL (13:05 Email):**
```
https://app.fireworks.ai/signup/confirm?client_id=sueas7prsfrdp16nantbeqcjv&user_name=fed77983-87d1-460a-a372-f3e9ecd4fece&confirmation_code=178814
```

**Key Takeaway:** Mail-Panel Extension → `mailbody-ui.de` OOPIF ist der EINZIGE Weg.
NIEMALS `3c.gmx.net` direkt, NIEMALS `lightmailer-bs.gmx.net`, NIEMALS CDP DOM API.

**Letzte Aktualisierung: 2026-05-13 (Mail-Panel Verified + Documentation Sync)**

*All learnings propagated to AGENTS.md, knowledge-base.md, and banned.md.*
