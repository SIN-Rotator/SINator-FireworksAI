# BUILDING PLAN — SINator Fireworks AI v3 (2026-05-12)

## Status Summary

| Flow | Name | Status | Issue |
|------|------|--------|-------|
| #0 | GMX Login | ✅ Working | Protected by hash |
| #1 | GMX Alias Rotate | ✅ 66% reliable | CUA delete-dialog flakes |
| #2 | Fireworks Signup | ⚠️ Partial | Create Account + OTP broken |
| #3 | Fireworks API Key | ❌ Untested | Depends on #2 |

## Current Architecture (v3, Ground Truth)

### What clicks work on which platform

| Page | Action | Method that works | Method that FAILS |
|------|--------|-------------------|-------------------|
| GMX 3c.gmx.net | Delete icon | CDP `Input.dispatchMouseEvent` | JS `.click()`, JS `dispatchEvent` |
| GMX 3c.gmx.net | OK button in dialog | CUA `click` element (AXButton) | — |
| GMX 3c.gmx.net | E-Mail-Adressen nav | JS `dispatchEvent(MouseEvent)` | CDP `Input.dispatchMouseEvent` |
| GMX 3c.gmx.net | Alias input fill | JS `nativeInputValueSetter` | CDP `Input.dispatchKeyEvent` |
| GMX | Navigation (Page load) | `client.navigate()` | CUA navigation (loses SID) |
| Fireworks | Cookie Accept All | JS `dispatchEvent(MouseEvent)` | CDP `Input.dispatchMouseEvent` |
| Fireworks | Signup form fill | JS `nativeInputValueSetter` | CDP `Input.dispatchKeyEvent` |
| Fireworks | Form buttons | `form.submit()` triggers IAC! | — |
| GMX API | mailbody fetch | `httpx` GET with cookies | HTTP 403 currently |

### What's BROKEN and needs fixing

#### 1. Flow #1: CUA delete-dialog flake (1/3 failures)

When: `_cua_click_ok_button` can't find the GMX Chrome window
Cause: GMX tab might not be the on-screen window, or window title doesn't contain "GMX"
Fix: Already has 3-retry logic, but the window search needs improvement
→ Add retry for CUA window search with broader matching

#### 2. Flow #2: "Create Account" button redirect

When: Clicking "Create Account" on Fireworks signup doesn't redirect to `/signup/verify`
Cause: Unknown — button IS found and clicked but form submission doesn't work
Hypothesis: Fireworks form needs `form.submit()` or specific event
Investigation needed: Check what exact event triggers the form

#### 3. Flow #2: OTP mailbody HTTP 403

When: `read_otp()` tries to fetch `mailbody/tmai{id}/true;jsessionid=...`
Cause: GMX API returns HTTP 403 for all email body fetches
Hypothesis: 
- JSESSIONID might be stale after webmailer navigation
- Additional cookie/header needed (iac_token expiry?)
- API endpoint changed
Investigation needed: Manually test mailbody URL in browser vs CDP

#### 4. Flow #3: Post-OTP flow (Login + Setup + API Key)

Not yet tested. Depends on OTP URL being extracted.
Steps:
- Navigate to confirm URL
- Login with email + password
- Fill firstname/lastname from alias
- Accept Terms checkbox
- Select use cases
- Submit for $5 credits
- Navigate to API keys page
- Create API key
- Extract key

## Protected Code (IMMUTABLE)

### Hash-locked (18 methods in gmx_service.py)
- `ensure_gmx_session` (Flow #0 — login)
- `_navigate_to_all_email_addresses` (v3 CDP/JS navigation)
- `_resolve_gmx_oopif` (v3 direct navigation)
- `_find_alias_coords_in_iframe` (JS evaluate)
- `_cdp_hover`, `_cdp_click`, `_js_click` (click methods)
- `_find_delete_icon_coords` (JS evaluate)
- `_cua_click_ok_button` (CUA + regex fix)
- `_find_alias_input_coords`, `_find_alias_input_via_cdp` (JS evaluate)
- `_find_hinzufuegen_button_coords` (form-scoped JS search)
- `_click_button_via_cdp` (CDP Input.dispatchMouseEvent)
- `_fill_alias_input_via_cdp` (nativeInputValueSetter)
- `_verify_alias_in_iframe` (JS innerText)
- `rotate_alias`, `create_alias`, `delete_existing_alias`

### Git Tags
- `v3-working` — commit `aa9b538`, known-good state

### Verification
```bash
python tools/verify_hashes.py          # 18 hashes must match
python tools/gmx_alias_tool.py rotate  # must succeed in <30s
```

## Next Steps (Priority Order)

### P0: Fix Flow #1 CUA window search flake
- File: `gmx_service.py` → `delete_existing_alias` around line 1010
- Change: broader window matching, add retries for window scan
- Time estimate: 1 hour

### P1: Fix Flow #2 "Create Account" redirect
- File: `fireworks_service.py` → Phase 5 click
- Approach: Test form.submit() vs CDP click vs dispatchEvent
- Need: Manual test of the Fireworks signup form behavior
- Time estimate: 1-2 hours

### P2: Fix Flow #2 OTP mailbody HTTP 403
- File: `gmx_service.py` → `read_otp()` method
- Approach: Test mailbody URL manually, check cookie freshness
- Alternative: GMX Chrome Extension (MailCheck) for email reading
- Time estimate: 2-3 hours

### P3: Flow #3 end-to-end test
- Depends on P1 + P2 being fixed
- Time estimate: 2-3 hours

## Dead Code Cleanup Status

- `agent_toolbox/core/fireworks_service.py`: Dead OTP methods removed ✅
- `agent_toolbox/core/gmx_service.py`: Dead code removed ✅
- `tools/diagnose_oopif.py`: Updated for v3 ✅
- `banned.md`: Updated with 16 anti-patterns ✅
- `AGENTS.md`: RED ZONE section added ✅
- `sinrules.md`: Regel 0 added ✅

## Files NOT to touch (unless P0-P3 bug fix)

- `agent_toolbox/core/gmx_service.py` (hash-protected methods)
- `tools/gmx_alias_tool.py` (verified tool)
- `protection/gmx_hashes.json` (chmod 444)
- `tools/verify_hashes.py` (verification tool)