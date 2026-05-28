# SINator Knowledge Database — Lessons Learned

> "Once Verified = Read-Only. New code = New file. Learnings → Here."
> Last verified: 2026-05-26 — V12 COMPLETE: 146 Keys (59 available, 77 suspended, 10 used), ~180s avg

## 🟢 WHAT WORKS (V12 Playwright+CUA+CDP Hybrid)

### GMX Alias Rotation (~41s, Playwright Shadow DOM)
- **Nav**: Playwright `ACCOUNT-AVATAR-NAVIGATOR` JS click → `dispatchEvent(mouseenter)` → Shadow DOM traversal "E-Mail Einstellungen" → Settings iframe "E-Mail-Adressen" → 20×1s Polling bis allEmailAddresses iframe gefunden
- **Delete**: Playwright new-tab iframe-URL → hover `.table_field:has-text(alias)` → click `[title*="löschen"]` force=True → click OK button in confirmation dialog
- **Create**: Playwright new-tab iframe-URL → fill `input[name*="localPart"]` → click `button:has-text("Hinzufügen")` force=True → verify `input_value() == ''`
- **Iframe URL helper**: `_get_iframe_url()` mit 8×3s Retry-Loop
- **Email filter**: `e != 'opensin@gmx.de'` (exact match)
- **Chrome Tab Cleanup**: Nach 4h Batch-Rotation → 37+ Tabs → Chrome überlastet. `rotate.py` schließt ALLE non-essential Tabs (nur Dashboard + 1 GMX-Inbox bleiben)

> **⚠️ WICHTIG:** CUA `find_cua_window` funktioniert NICHT mehr — Chrome-Tab-Titel ist leer bei programmatischen Tabs. Reiner Playwright-Ansatz für Navigation. allEmailAddresses iframe-URL in NEUEM TAB als Top-Level-Dokument öffnen.

### Fireworks Login (Playwright)
- **Login URL**: `/login` → "Email Login" link → `/login/email?redirectURI=`
- **Email input**: `input[name="email"]` (KEIN `type="email"` Attribut!)
- **Password**: `input[name="password"]` (mit `type="password"`)
- **Submit**: `button[type="submit"]` mit Text "Next"

### Fireworks Signup (Playwright + CUA)
- **Email**: `input[name="email"]` fill → `button:has-text("Next")`
- **Password**: 2x `input[type="password"]` → `button:has-text("Create Account")`
- **OTP Poll**: MailCheck Extension + CDP `Target.getTargets` → `mailbody-ui.de` OOPIF → extract verify URL
- **Verify**: `verify_account(url)` → opens URL in new tab via Playwright `page.goto()`

### Fireworks Onboarding (CUA required — React ignores Playwright)
- **Names**: CUA `type_text` → search "First" + "Last" (NOT "Name" — matches Company Name!)
- **Terms checkbox**: NUR CUA `AXPress` toggelt React-CB. Playwright `check()` + JS `click()` = IGNORIERT
- **Playwright Fallback**: Falls CUA Submit keinen Redirect triggert → Playwright füllt Formular + Submit
- **Order**: ALLE Felder zuerst → DANN Terms-CB → DANN Continue
- **Continue redirects to login**: Account confirmed → must login again
- **Use-Cases**: CUA dynamic text-based scan (no hardcoded indices!) → checkboxes + Submit

### Fireworks API Key (Playwright)
- **URL**: `/settings/users/api-keys` (NICHT `/settings/workspace/api-keys`!)
- **Create button**: PopUpButton force-click → `[role="menuitem"]:has-text("API Key")` click
- **Name**: `input[name*="name"]` fill → Wait 1s (React re-render) → disabled→enabled polling → "Generate" button click
- **Extract**: `re.findall(r'fw_[a-zA-Z0-9]{20,}', page.content() + page.evaluate("body.innerText"))` mit 10s DOM-Polling
- **Error Handling**: "Missing API Key Name!" Modal → Close → retry fill + Generate

### Session Management
- **GMX E-Mail click**: `page.locator('a:has-text("E-Mail")').click()` → inbox with SID
- **Fireworks Logout before Signup**: CDP `Network.deleteCookies` for fireworks domain + `clearBrowserCookies`
- **IAC close**: `for pg in pages: if 'iac' in pg.url: await pg.close()`

### Config Manager (V11)
- **Singleton** `get_config()` liest `data/config.json`
- **Fields**: `gmx_email`, `gmx_password`, `fireworks_password`
- **API**: `GET/POST /api/v1/config` (public, kein Auth-Token)
- **Rotation**: Liest Config → `--gmx-email`, `--gmx-password`, `--password` an rotate.py
- **Dashboard**: `/setup` Formular mit Show/Hide Toggle

### Pool-Verschlüsselung (V12)
- **macOS Keychain** `com.sinator.pool` — alle 146 API-Keys verschlüsselt
- **Pool-JSON** enthält SENTINEL-Werte (keine Keys im Klartext)
- **`keychain_store.py`** — CRUD + Migration (Pool→Keychain)
- **`GET /pool/reveal/{key_id}`** — hydratisiert Key aus Keychain

### Chat-Assistent (V11)
- **Rust Command** `chat_send` — umgeht Tauri WebView Fetch-Blockade
- **Modell**: `accounts/fireworks/models/gpt-oss-120b` ($0.15/M, billigstes Serverless)
- **System-Prompt**: `chat-system-prompt.txt` (include_str! in Rust)
- **Live-Stats**: Rust holt Pool-Stats (:8000) + Backend-Health → injiziert in System-Prompt
- **Fallback**: `content` + `reasoning_content` (Reasoning-Modelle)
- **Kein Streaming** — einfacher invoke Return

## 🔴 KNOWN ISSUES (2026-05-26)

### Account Suspension (Spending Limit)
Fireworks suspendiert Accounts wenn die $5 Credits aufgebraucht sind:
```
Account golden-cobra-560-66c is suspended, possibly due to reaching the monthly
spending limit or failure to pay past invoices.
```
- **Workaround:** `POST /pool/report` meldet Key als suspended → Backend leaset Ersatz-Key **atomar** (im gleichen Lock). Proxy nutzt `report()`-Result direkt — kein extra `lease()`.
- **Kein Recovery möglich** — Account ist tot, neuer Account nötig

### Double-Key-Waste (GEFIXT V12)
Vorher: `report()` + `lease()` = 2 Backend-Operationen → 2 Keys berührt pro Swap.
Jetzt: `report_key()` leaset Ersatz-Key atomar. 1 Swap = 1 Key suspended + 1 Key geleased.

### 429 Rate Limiting (GEFIXT V12)
Transientes 429 → Proxy wartete intern 5s → Client Timeout/InvalidHTTPResponse.
Jetzt: Proxy gibt SOFORT 429 an Client zurück mit `Retry-After` Header. Kein internes Warten.

### Chrome Tab Overload (GEFIXT V12)
Nach 4h Batch-Rotation → 37+ Tabs → Chrome überlastet → Playwright connect timeout.
Jetzt: `rotate.py` räumt ALLE non-essential Tabs auf (nur Dashboard + 1 GMX-Inbox bleiben).

### Tauri WebView Fetch Blockiert
`fetch("http://localhost:8888/...")` aus Tauri WebView → `TypeError: Load failed`
- **Workaround:** Rust Command `chat_send` macht den HTTP-Call
- ** Auch verboten:** `listen()` (ACL denied), Next.js API Routes (nicht im Static Export)

### CUA Finds Wrong Window (Multiple Chrome Instances)
Stale Chrome-Instanz auf Port 9223 + Haupt-Instanz auf Port 9222 → `find_cua_window` matched falsches Fenster
- **Fix (V10):** `lsof -i :9222 -sTCP:LISTEN` ermittelt Chrome-PID → `target_pid` in `find_cua_window`

## 🔴 BANNED / BROKEN

### CDP DOM on Cross-Origin Iframes
- `DOM.performSearch` → nodeIds vary between calls, stale
- `DOM.getBoxModel` → fails on cross-origin nodes in 3c.gmx.net

### React Interaction (NICHT mit Playwright)
- Playwright `check()` auf React-Checkbox → "did not change state"
- JS `.click()` auf React-Button → ignoriert
- **Lösung**: CUA `AXPress` für React-CB + `type_text` für Names

### Hardcoded CUA element_index
- React re-renders → ALLE Indizes ändern sich zwischen Scans
- **Lösung**: IMMER `_find_element(text, el_type)` mit AX-Tree scan

### CUA type_text auf React Email-Inputs
- React kontrollierte Inputs ignorieren CUA Keyboard Events
- **Lösung**: Playwright `fill()` für Email/Password (funktioniert über CDP)

### Tauri v2 Banned Patterns
- `__TAURI_INTERNALS__` Check → leer im Production Build
- Next.js API Routes → nicht im Static Export
- `listen()` für Streaming → ACL denied
- `fetch()` zu localhost:8888 → WebView blockiert
- `kimi-k2p5` als Chat-Modell → `reasoning_content` statt `content`
- Frontend-Fetch ohne Auth-Token → 401

## 📊 TOOL COMPARISON

| Tool | Nav | Input Fill | Button Click | React-CB | Verify |
|------|:---:|:----------:|:------------:|:--------:|:------:|
| CUA | ✅ | ✅ (type_text) | ✅ (dialogs) | ✅ | ❌ |
| CDP DOM | ❌ | ❌ (stale) | ❌ (stale) | ❌ | ❌ |
| Playwright | ✅ | ✅ | ✅ | ❌ | ✅ |
| JS evaluate | ❌ | ✅ (nativeSetter) | ⚠️ | ❌ | ✅ |
| Rust Command | ❌ | ❌ | ❌ | ❌ | ❌ |

### Best Hybrid: CUA nav + Playwright form + CUA for React-CB + Playwright verify
### Chat: Rust Command (nicht Frontend Fetch!)

### Performance: V9→V12
| Metric | V9 | V11 | V12 |
|--------|:--:|:---:|:---:|
| Pool Size | 45 | 112 | 146 |
| Cycle Time | ~173s | ~210s | ~180s |
| Key Storage | JSON file | Keychain + JSON | Keychain + JSON |
| Credentials | Hardcoded | Config Manager | Config Manager |
| Chat | N/A | Rust Command | Rust Command |
| Proxies | 1× :8888 | 1× :8888 | 3× :8888-:8890 |
| Swap Atomicity | report+lease separat | report+lease separat | report+lease atomar |

## 🔧 VERIFIED WORKING COMMITS

| Commit | Date | Status |
|--------|------|--------|
| `HEAD` | May 26 | ✅ **LATEST**: V12 — 3 Proxies, Shadow DOM Nav, Atomic Swap, 146 Keys |
| V11 | May 25 | ✅ V11: Config Manager, Chat, Keychain, 112 Keys |
| V10 | May 24 | ✅ V10: CUA PID Targeting, ~204s E2E |
| V9 | May 23 | ✅ V9: Sleep-Reduktion + Bugfixes, 45 Keys |
| `3ac4b30` | May 22 | ✅ V8: pulse-jaguar-899 → `fw_6rWU4KGUPts6zVnaRreu6R` (30 Keys) |
| `58618c9` | May 22 | ✅ V8 GMX Nav Fix |
| `1d3ddf5` | May 21 | ✅ Complete flow: GMX → FW → `fw_8d1PLFjvQMdgJFzjDZSTRx` |

## 🚀 QUICK REFERENCE

```bash
# Start Chrome (Profile 901, Port 9222, OHNE accessibility!)
nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="/Users/jeremy/Library/Application Support/Google Chrome" \
  --profile-directory="Profile 901" \
  --remote-debugging-port=9222 \
  --no-first-run --no-default-browser-check \
  > /tmp/chrome_sinator.log 2>&1 &

# Start CUA
cua-driver serve &

# Full E2E (liest Config aus data/config.json)
python tools/rotate.py

# API Key URL
https://app.fireworks.ai/settings/users/api-keys

# Pool Stats
curl -s http://localhost:8000/pool/stats | python3 -m json.tool

# Config
curl -s http://localhost:8000/api/v1/config | python3 -m json.tool

# Pool-Proxies (3 Instanzen)
Lokal: http://localhost:9998/inference/v1    → https://sinatorpool-router.delqhi.com/inference/v1
# apiKey (alle Macs): <DEIN_API_KEY>
# apiKey (alle Macs): <DEIN_API_KEY>
```

## 🔧 ARCHITECTURE (V12)

```
SINator-fireworksai/        ← Backend (:8000) + 3× Proxy (:8888-:8890) + Rotation
SINator-dashboard/          ← Next.js + Tauri v2 App (Dashboard + Chat)
sinator-pages/              ← Landing Page (:8040)

Services (LaunchAgents):
  com.sinator.backend     :8000  FastAPI
  com.sinator.pool-router       :9998  Pool-Router (ThreadingMixIn + Failover)
  com.sinator.pool-proxy-{8888..8897}  :8888-:8897  10× aiohttp SSE + silent swap
  com.sinator.pages       :8040  Landing Page
  com.sinator.chrome      :9222  Chrome Profile 901
  com.sinator.cua-driver  —      CUA AX-Daemon

Tunnel Subdomains:
  sinatorpool-router.delqhi.com  → :9998 (Pool-Router) → 10× Proxys :8888-:8897
  sinator.delqhi.com       → :8000 + :8040
```
