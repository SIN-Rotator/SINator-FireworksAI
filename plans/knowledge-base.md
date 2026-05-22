# SINator Knowledge Database — Lessons Learned

> "Once Verified = Read-Only. New code = New file. Learnings → Here."
> Last verified: 2026-05-22 — V8 COMPLETE: pulse-jaguar-899 → `fw_6rWU4KGUPts6zVnaRreu6R` (30 Keys)

## 🟢 WHAT WORKS (V8 Playwright+CUA+CDP Hybrid)

### GMX Alias Rotation (~63s, New-Tab Approach)
- **Nav**: Playwright `goto("inbox?sid=...")` → CUA click Einstellungen [148] → JS evaluate click hidden `#nav-menu` button → extract allEmailAddresses iframe URL
- **Delete**: Playwright new-tab iframe-URL → hover `.table_field:has-text(alias)` → click `[title*="löschen"]` force=True → click OK button in confirmation dialog
- **Create**: Playwright new-tab iframe-URL → fill `input[name*="localPart"]` → click `button:has-text("Hinzufügen")` force=True → verify `input_value() == ''`
- **Iframe URL helper**: `_get_iframe_url()` mit 6×3s Retry-Loop
- **Email filter**: `e != 'opensin@gmx.de'` (exact match)

> **⚠️ WICHTIG:** allEmailAddresses iframe ist OFF-SCREEN auf `/produkte_ha`. Öffne iframe-URL in NEUEM TAB als Top-Level-Dokument. Playwright `fill()`/`click()` funktioniert dann normal.

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
- **Order**: ALLE Felder zuerst → DANN Terms-CB → DANN Continue
- **Continue redirects to login**: Account confirmed → must login again
- **Use-Cases**: CUA dynamic text-based scan (no hardcoded indices!) → checkboxes + Submit

### Fireworks API Key (Playwright)
- **URL**: `/settings/users/api-keys` (NICHT `/settings/workspace/api-keys`!)
- **Create button**: PopUpButton force-click → `[role="menuitem"]:has-text("API Key")` click
- **Name**: `input[name*="name"]` fill → "Generate" button click
- **Extract**: `re.findall(r'fw_[a-zA-Z0-9]{20,}', page.content() + page.evaluate("body.innerText"))`

### Session Management
- **GMX E-Mail click**: `page.locator('a:has-text("E-Mail")').click()` → inbox with SID
- **Fireworks Logout before Signup**: CDP `Network.deleteCookies` for fireworks domain + `clearBrowserCookies`
- **IAC close**: `for pg in pages: if 'iac' in pg.url: await pg.close()`

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

## 📊 TOOL COMPARISON

| Tool | Nav | Input Fill | Button Click | React-CB | Verify |
|------|:---:|:----------:|:------------:|:--------:|:------:|
| CUA | ✅ | ✅ (type_text) | ✅ (dialogs) | ✅ | ❌ |
| CDP DOM | ❌ | ❌ (stale) | ❌ (stale) | ❌ | ❌ |
| Playwright | ✅ | ✅ | ✅ | ❌ | ✅ |
| JS evaluate | ❌ | ✅ (nativeSetter) | ⚠️ | ❌ | ✅ |

### Best Hybrid: CUA nav + Playwright form + CUA for React-CB + Playwright verify

## 🔧 VERIFIED WORKING COMMITS

| Commit | Date | Status |
|--------|------|--------|
| `3ac4b30` (HEAD) | May 22 | ✅ **LATEST**: pulse-jaguar-899 → `fw_6rWU4KGUPts6zVnaRreu6R` (30 Keys) |
| `58618c9` | May 22 | ✅ V8 GMX Nav Fix: Playwright inbox + CUA Einstellungen + JS hidden-nav + New-Tab iframe |
| `54e0efa` | May 22 | ✅ Perf: Wartezeiten reduziert (~30s Ersparnis) |
| `35cd420` | May 22 | ✅ crystal-beetle-676 → `fw_MdM6tGucgWuuc7zQyJGeTK` |
| `1d3ddf5` | May 21 | ✅ Complete flow: GMX → FW → `fw_8d1PLFjvQMdgJFzjDZSTRx` |
| `aa9b538` (v3) | May 12 | ⚠️ CDP-based, broke when GMX enabled accessible mode |

## 🚀 QUICK REFERENCE

```bash
# Start Chrome (Profile 901, Port 9222)
nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="/Users/jeremy/Library/Application Support/Google Chrome" \
  --profile-directory="Profile 901" \
  --remote-debugging-port=9222 \
  --no-first-run --no-default-browser-check \
  > /tmp/chrome_sinator.log 2>&1 &

# Start CUA
cua-driver serve &

# Full E2E
python tools/rotate.py

# API Key URL
https://app.fireworks.ai/settings/users/api-keys

# Pool Stats
curl -s http://localhost:8000/pool/stats | python3 -m json.tool
```
