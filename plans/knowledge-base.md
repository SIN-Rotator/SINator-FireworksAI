# SINator Knowledge Database — Lessons Learned

> "Once Verified = Read-Only. New code = New file. Learnings → Here."

## 🟢 WHAT WORKS

### CUA Navigation
- `cua-driver call click` auf AXLink "E-Mail" → accessible inbox
- `cua-driver call click` auf AXButton "Einstellungen" → settings page
- Filter: `app_name == 'Google Chrome'` (nicht iTerm2 mit "GMX" im Titel!)
- Regex: `r'\]?\s*-\s*\[(\d+)\]'` (handled both `[46] - [29]` and `- [29]` formats)
- Parentheses not quotes: `AXLink (E-Mail)` not `AXLink "E-Mail"`

### Playwright Form Interaction
- `page.locator('input[type="text"]').first.fill("name")` → Wicket input
- `page.locator('form button:has-text("Hinzufügen")').first.click()` → submit
- Button is `<button>` without `type="submit"`, name=`fieldSet:...:button`
- Input clears after successful submit (verification signal)

### Session Management
- Click "E-Mail" link on www.gmx.net → redirects to inbox with fresh SID
- No explicit login needed if session cookie exists
- `bap.navigator.gmx.net/mail?sid=...` is the working inbox URL
- `navigator.gmx.net/mail_settings/email_addresses?sid=...` redirects → `mail_settings/mail`
- `3c.gmx.net/.../allEmailAddresses;jsessionid=...` is the allEmailAddresses page
- JSESSIONID different from SID, can't be constructed manually

### Session Expiry Fix
- After connecting to allEmailAddresses tab, immediately navigate to www.gmx.net and back
- This refreshes the session cookie without losing the allEmailAddresses context

## 🔴 WHAT'S BROKEN

### CDP DOM on Cross-Origin Iframes
- `DOM.performSearch` returns texts but nodeIds are 0 (stale)
- `DOM.getBoxModel` fails on cross-origin nodes
- `DOM.getSearchResults` with `toIndex: 1` returns only stale node — use `toIndex: resultCount`
- CDP Page.navigate to `email_addresses?sid=...` redirects away
- No iframe-target exposed for `3c.gmx.net` in `Target.getTargets`

### Runtime.evaluate on Accessible Pages
- Marked BANNED after GMX enabled accessible mode
- But was the ONLY approach that worked for content interaction (v3, aa9b538)
- Returns empty results on pages showing "Barrierefreies Postfach"
- Only works on the allEmailAddresses page (3c.gmx.net direct URL)

### Hardcoded Coordinates
- `{"x": 350, "y": 340}` for input — NEVER worked
- `input_y + 95` for button — NEVER worked
- Need real DOM coordinates or Playwright locators

## 📊 TOOL COMPARISON

| Tool | Nav | Input Fill | Button Click | Verification | Iframe |
|------|:---:|:----------:|:------------:|:------------:|:------:|
| CUA | ✅ | ❌ | ✅ (dialogs) | ❌ | ❌ |
| CDP DOM | ❌ | ❌ (stale) | ❌ (stale) | ❌ (stale) | ❌ |
| Playwright | ✅ | ✅ | ✅ | ✅ | ✅ |
| JS evaluate | ❌ (empty) | ✅ (nativeInputValueSetter) | ✅ (click) | ✅ | ⚠️ |

### Best Hybrid: CUA nav + Playwright form + Playwright verify

## 🔧 VERIFIED WORKING COMMITS

| Commit | Date | Status | Approach |
|--------|------|--------|----------|
| `aa9b538` (v3) | May 12 | ⚠️ 2/3 success | JS evaluate + CUA nav |
| `f61091d` | May 11 | ❌ broken verify | CDP DOM + CUA |

## ⚡ QUICK REFERENCE

```bash
# Start Chrome
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="/Users/simoneschulze/Library/Application Support/Google Chrome" \
  --profile-directory="Profile 73" \
  --no-first-run --no-default-browser-check &

# Start CUA  
cua-driver serve &

# Start standalone API
cd ~/dev/gmx-alias-tool && python3 server.py &

# Check session
curl http://localhost:8001/health

# Create alias
curl -X POST http://localhost:8001/alias/create \
  -H 'Content-Type: application/json' \
  -d '{"alias_name": "test-123", "delete_existing": true}'
```
