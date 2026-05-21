# SINator Knowledge Database — Lessons Learned

> "Once Verified = Read-Only. New code = New file. Learnings → Here."
> Last verified: 2026-05-21 — COMPLETE FLOW: GMX Rotation → Fireworks → API Key `fw_8d1PLFjvQMdgJFzjDZSTRx`

## 🟢 WHAT WORKS

### GMX Alias Rotation (19.8s avg, 3/3 verified)
- **Delete**: `.table_field:has-text(alias)` hover(force=True) → `[title*="löschen"]` click(force=True) → CUA OK
- **Create**: fill `input[type="text"]` → `button:has-text("Hinzufügen")` click (no force) → verify `inp.input_value() == ''`
- **Email filter**: `e != 'opensin@gmx.de'` (exact match, NOT substring)
- **Nav**: CUA E-Mail AXLink → Einstellungen AXButton → allEmailAddresses iframe in mail_settings

### Fireworks Login
- **Login URL**: `/login` → "Email Login" link → `/login/email?redirectURI=`
- **Email input**: `input[name="email"]` (KEIN `type="email"` Attribut!)
- **Password**: `input[name="password"]` (mit `type="password"`)
- **Submit**: Playwright `page.locator('input[name="email"]').fill()` + button click

### Fireworks Onboarding (CUA required — React ignores Playwright)
- **Terms checkbox**: NUR CUA `AXPress` toggelt React-CB. Playwright `check()` + JS `click()` = IGNORIERT
- **Names**: CUA `type_text` (Playwright `fill()` = React re-renders and clears)
- **Order**: ALLE Felder zuerst → DANN Terms-CB → DANN Continue

### Fireworks API Key
- **URL**: `/settings/users/api-keys` (NICHT `/settings/workspace/api-keys`!)
- **Create button**: `AXPopUpButton "Create API Key"` → force-click → `[role="menuitem"]:has-text("API Key")`
- **Name**: `input[name*="name"]` → "Generate" button
- **Extract**: `re.findall(r'fw_[a-zA-Z0-9]{20,}', text)`

### Session Management
- Click "E-Mail" link on www.gmx.net → redirects to inbox with fresh SID
- No explicit login needed if session cookie exists
- `bap.navigator.gmx.net/mail?sid=...` is the working inbox URL

### IAC (GMX Anti-Automation)
- Close IAC pages via Playwright: `for pg in pages: if 'iac' in pg.url: await pg.close()`
- Direct URL navigation to `3c.gmx.net` triggers IAC → use CUA navigation instead

## 🔴 WHAT'S BROKEN / BANNED

### CDP DOM on Cross-Origin Iframes
- `DOM.performSearch` returns texts but nodeIds are 0 (stale)
- `DOM.getBoxModel` fails on cross-origin nodes
- `DOM.getSearchResults` with `toIndex: 1` returns only stale node — use `toIndex: resultCount`

### React Form Interaction (NICHT mit Playwright)
- Playwright `check()` auf React-Checkbox → "did not change state"
- JS `.click()` auf React-Button → ignoriert
- **Lösung**: CUA `AXPress` für React-CB und Buttons

### Hardcoded Coordinates
- `{"x": 350, "y": 340}` → NIE funktioniert
- `input_y + 95` für Button → NIE funktioniert

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
| `1d3ddf5` (HEAD) | May 21 | ✅ Complete flow: GMX → FW → API Key |
| `aa9b538` (v3) | May 12 | ⚠️ Partial (CDP-based, broke when GMX enabled accessible mode) |
| `f61091d` | May 11 | ❌ Broken verify (false positive on stale nodes) |

## ⚡ QUICK REFERENCE

```bash
# Start Chrome (temp profile for debugging)
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-sinator --no-first-run &

# Start CUA
cua-driver serve &

# GMX Rotation
python tools/gmx_alias_tool.py rotate

# Fireworks API Key URL
https://app.fireworks.ai/settings/users/api-keys
```
