# fireworks_service.py — Fireworks AI E2E Flow

## Purpose
Complete Fireworks AI lifecycle: signup → OTP verify → login → onboarding → API key generation. Uses 100% SIN-Browser-Tools (zero raw Playwright evaluate calls).

## ⚠️ DO NOT TOUCH — Tag `v19.2-onboarding-fixed` ⚠️

> **Diese Datei ist der letzte bekannte funktionierende Stand der Fireworks E2E-Rotation.**  
> **5 Bugs wurden gleichzeitig in V19.2-Onboarding-Fix behoben.**  
> **Vor jeder Änderung: `git diff v19.2-onboarding-fixed` und verifizieren.**  
> **Details: siehe `AGENTS.md` § V19.2 ONBOARDING-FIX**

## Dependencies
- **Imports from:** `sin_browser_tools.tools.*` (navigation, interaction, extraction, vision)
- **Imports from:** `sin_browser_tools.core.manager` (instance registration)
- **Imported by:** `tools/rotate.py` (rotation orchestrator)
- **Reads:** Nothing from disk (ephemeral browser session)

## Architecture

### Two Chrome Instances
| Instance | Purpose | Lifecycle |
|----------|---------|-----------|
| User Chrome (Profile 73) | GMX email ops (OTP reading) | Persistent, never killed |
| Bot Chrome (ephemeral) | Fireworks signup/login/onboarding/API key | Created per rotation, closed after API key success |

### `_BrowserHandle` Duck-Type
SIN-Browser-Tools expects a `BrowserManager` with `_page`, `_context`, `_browser`, `_playwright` attributes. `_BrowserHandle` provides these from a raw Playwright launch, bypassing `BrowserManager` (which hardcodes `--start-maximized`).

Registered via `manager._set_instance(handle)` — all SIN-Browser-Tools tools then operate on this handle.

### React Controlled Inputs — DOUBLE-STRATEGY
Two strategies for filling React inputs:
1. **Native React value setter** (`browser_console`) — sets value via `Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set` + dispatches synthetic events
2. **`browser_type` with delay** — types characters one by one with `delay=30ms` (lets React pick up keystrokes naturally)

**V19.2 Onboarding uses `browser_type` (NOT React setter) for First/Last Name** — proved more reliable for the live Fireworks app.

### Account ID — DO NOT OVERWRITE IF PRE-FILLED
Fireworks limits Account ID to 20 characters. As of 2026-06, Fireworks pre-fills the field with a unique suggestion like `phantom-tiger-557-7q`. If we overwrite with `browser_type`, it APPENDS to existing text → exceeds 20-char limit → validation error → Continue button disabled.

**V19.2 logic:** if `input[name=accountId].value` is non-empty → leave it alone. Only fill if empty.

## Key Decisions

### Why `browser_press("Enter")` instead of `browser_click_by_text("Next")` for signup/login submit?
The Fireworks page has a carousel "Next slide" button (disabled) that appears before the form's "Next" button in the DOM. `browser_click_by_text("Next", role="button")` matches the carousel button first. Enter key bypasses this entirely.
**CRITICAL:** Do NOT replace Enter key with JS dispatchEvent or `browser_click_by_text` — this was tried and broke the flow (s. tag `v19.1-working-revert`).

### Why Continue button uses EXACT match (no "Next" fallback)?
V19.2 bug: My JS query had `t.indexOf('Continue') !== -1 || t.indexOf('Next') !== -1` — the carousel "Next slide" button matched the "Next" fallback and stole the click. **Fix:** only match "Continue" exactly:
```javascript
if (t === 'Continue' || t.indexOf('Continue') !== -1) { ... }  // NO "Next"!
```

### Why aggressive Cookie-Banner removal?
The Fireworks cookie banner has a "Customise" mode that shows 1000+ partner toggles and COMPLETELY covers the onboarding form. Just clicking "Reject All" fails if the button is off-screen. V19.2 fix:
1. Scroll to top
2. Click "Reject All" (visible top button)
3. JS-Force-Remove all `cky-*` elements
4. Restore body overflow
5. Verify 0 cky elements remain

### Why wait 45s after Submit (not 15s)?
Fireworks server-side processing takes longer than 15s. V19.2 bumped from 15×1s to 45×1s wait loop for the redirect to /home. Also: force-navigate has an additional 15s wait window.

### Why 4-strategy checkbox clicker?
Fireworks uses custom React checkboxes. `browser_click_checkbox_by_text` (sin_browser_tools) tries 4 strategies: input[aria-label], [role=checkbox], label, :has-text. The fallbacks handle React's custom components that don't use standard `<input type="checkbox">`.

### Why `_playwright_onboarding` takes no parameters?
It operates on the currently active page in SIN-Browser-Tools manager. The page is already on `/onboarding` after login redirect.

### Why button text uses partial match (`indexOf`) not strict equality?
Fireworks button labels change over time (e.g., "Submit" → "Submit to get $5 Credits"). Strict `===` breaks silently. The old code used `'Submit' in txt` — restored in `v19.1-working-revert`.

## Flow Sequence
```
1. launch()           → Bot Chrome + SIN-Browser-Tools registration
2. signup_fireworks() → Email + password + Create Account
3. verify_account()   → Open OTP URL from GMX
4. login_fireworks()  → Email Login → email → password → Enter
5. _playwright_onboarding() → 
   a. AGGRESSIVELY remove cky-* cookie banner
   b. Account ID: leave pre-filled alone, only fill if empty
   c. First/Last Name via browser_type (delay=30ms)
   d. Terms checkbox via browser_click_checkbox_by_text (4-strategy)
   e. Continue: EXACT match (no "Next" fallback)
   f. Use-case checkboxes: 4-strategy clicker (Prototype, Flexible, Conversational, Search, Agentic)
   g. Submit: button click → form.requestSubmit() → Enter (5s sleeps)
   h. Wait 45×1s for redirect to /home
   i. Force-navigate to /settings/users/api-keys as fallback with 15s wait
6. create_api_key()   → Navigate to API keys → Create → Generate → poll for fw_ key
```

## Known Issues
- `browser_click_checkbox_by_text()` may not trigger React state updates for custom button-based checkboxes (e.g., Fireworks Terms). Fallback: `browser_console()` with direct DOM click.
- Onboarding redirect detection relies on URL containing `home`/`account`/`settings` — may break if Fireworks changes URL structure.
- Submit button in onboarding is often disabled (React validation pending). `browser_click_by_text("Submit")` + fallback texts fails silently. Fixed with `browser_press("Enter")` as final fallback — bypasses disabled state.
- The Enter key pattern matches login/signup flow (same reason: carousel "Next slide" button conflict).
- **NEVER match "Next" in Continue button search** — carousel "Next slide" button will steal the click (V19.2 bugfix).
- **NEVER overwrite pre-filled Account ID** — it triggers 20-char validation error (V19.2 bugfix).
- **NEVER skip cookie banner cleanup** — 1000+ cky-* elements will cover the form (V19.2 bugfix).
