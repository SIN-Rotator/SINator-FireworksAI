# V18.0 Post-CEO-Fix Bugs (2026-06-01)

## Summary

The "CEO fixes" (commit `e290c3b`) introduced 8 bugs in 3 files that broke the E2E rotation flow.
3/8 fixed during session, 5 still open.

---

## FIXED Bugs

### F1: browser_utils.py — `page.evaluate()` f-string + positional args

**File:** `agent_toolbox/core/browser_utils.py`
**Root Cause:** All `page.evaluate()` calls used f-strings AND passed the same variables as
positional arguments. Playwright Python `evaluate()` accepts max 2 positional args
(expression + arg). Pattern:
```python
page.evaluate(f"(x) => {{...}}", x, y)  # 3 positional args → CRASH
```
**Affected functions:**
- `wait_for_spa_transition()` — 3 args → TypeError
- `fill_react_input()` — 3 args → TypeError  
- `click_react_checkbox()` — 2 args (worked but redundant)
**Fix:** Converted to `page.evaluate(JS, {"arg": val})` pattern.
**Verification:** Syntax check, no f-string evaluate() calls remain.

### F2: gmx_service.py — `read_otp_main_frame_only` OUTSIDE class

**File:** `agent_toolbox/core/gmx_service.py` (L1507-L1596)
**Root Cause:** Method was defined AFTER module-level `get_gmx_service()` function
(L1500). Python treats the 4-space indented code after dedent to 0 as dangling
module-level code — NOT as a class method. Same bug as V15.5 (methods falling
out of class).
**Effect:** `gmx.read_otp_main_frame_only()` → AttributeError
**Fix:** Moved the method back inside the class, before module-level code.
**Verification:** `hasattr(GmxService(), 'read_otp_main_frame_only')` → True

### F3: gmx_service.py — `(() => { arguments[0] })` Arrow Function broken

**File:** `agent_toolbox/core/gmx_service.py`
**Affected methods:**
- `read_otp_main_frame_only()` — `scan_js`
- `read_otp_via_playwright()` — `scan_js` and `click_js`

**Root Cause:** JavaScript Arrow Functions `() => { arguments[0] }` do NOT have an
`arguments` object. Playwright wraps eval JS as `async function() { <code> }` and
calls it with the arg, but IIFE `(() => { ... })()` captures no arguments.
**Effect:** All `scan_js` calls received `undefined` as sender filter → 0 matches.
**Fix:** Changed to `(SENDER) => { ... }` / `(args) => { ... }` — function parameter
style that Playwright evaluates correctly.
**Verification:** `mail` frame scan now returns 30 items matching 'fireworks' (was 0).

### F4: gmx_service.py — OTP scanned email LIST, not opened email body

**File:** `agent_toolbox/core/gmx_service.py` — `read_otp_main_frame_only()`
**Root Cause:** After finding email items via Shadow DOM traversal, the code only
searched the email LIST preview text for the verify URL. The URL only appears in
the opened email BODY (loaded in `detail-body-iframe` frame).
**Effect:** Found 30 Fireworks emails but returned "No mail" (URL not in list text).
**Fix:** Added click (via evaluate) on first matching `list-mail-item` → wait 3s →
scan ALL frames for verify URL in `document.body.innerText`.
**Verification:** `URL found in frame 'detail-body-iframe' after 3.4s` ✅

### F5: fireworks_service.py — `browser.new_page()` on CDP connection

**File:** `agent_toolbox/core/fireworks_service.py`
**Affected:** `login_fireworks()` (L168), also `signup_fireworks()`, `create_api_key()`
**Root Cause:** `browser.new_page()` throws "Please use browser.new_context()" when
called on a CDP-connected browser. The correct call is `browser.contexts[0].new_page()`.
**Fix:** Changed to `browser.contexts[0].new_page() if browser.contexts else browser.new_page()`.
**Verification:** No more CDP new_page errors during rotation.

---

## STILL OPEN Bugs

### O1: Login nach Verify — falsche Page State

**File:** `agent_toolbox/core/fireworks_service.py` — `login_fireworks()`
**Root Cause:** `login_fireworks()` navigates to `https://app.fireworks.ai/login` and
then waits for `input[name="email"]`. But after `verify_account()` opens the verify URL,
the user is already authenticated. Navigating to `/login` may redirect to dashboard or
onboarding — no email input exists.
**Effect:** `Locator.fill: Timeout 30000ms exceeded. Waiting for locator("input[name=\"email\"]").first`
**Fix needed:** Either:
(a) Reuse post-verify page for onboarding directly (skip login)
(b) Detect logged-in state in `login_fireworks()` and skip to onboarding
(c) Clear session/cookies before navigating to login

### O2: browser_utils.py — `wait_for_spa_transition` waits for "verify"

**File:** `agent_toolbox/core/fireworks_service.py` (L114)
**Root Cause:** After signup, the code calls `wait_for_spa_transition(page, "verify", timeout=15)`.
The signup confirmation page may not contain "verify" in its visible text.
**Effect:** 15s timeout warning every rotation (benign — signup still completes).
**Fix:** Change to wait for URL change (`/signup` → redirect) or for a more reliable
indicator like "Check your email" or dashboard URL.

### O3: firewords_service.py — `create_api_key()` also CDP-new_page

**File:** `agent_toolbox/core/fireworks_service.py` (L504, L577)
**Root Cause:** Same issue as F5 — `browser.new_page()` in `create_api_key()` and
other functions. These are currently unreachable because O1 blocks them.
**Fix:** Apply same pattern as F5 fix.

### O4: Login-Onboarding Flow — React SPA checkbox interaction

**File:** `agent_toolbox/core/fireworks_service.py`
**Root Cause:** The Fireworks onboarding is a 2-step React SPA (no URL change between
steps). Step 2 checkboxes are custom React `<div>`/`<span>` elements, not `<input type="checkbox">`.
CookieYes overlay blocks step 2 rendering.
**Previous fix (V17):** `click_react_checkbox()` helper + `accept_cookieyes_via_js()`.
**Status:** Never tested E2E because O1 blocks reaching this code. Need functional test
with post-verify flow.

### O5: Keine Testabdeckung für E2E Flow

**Root Cause:** No unit/integration tests exist for the rotation flow. All fixes are
tested by running the full rotation, which takes 2+ minutes and consumes real GMX/Fireworks
accounts.
**Fix needed:** Add Playwright-based integration tests with mocked OTP/email reading.

---

## Priority

1. **O1** (blocking — rotation can't complete)
2. **O2** (annoyance — 15s wait every time but non-blocking)
3. **O3** (latent — will break when O1 is fixed)
4. **O4** (latent — will break when O1+O3 are fixed)
5. **O5** (technical debt)
