# fireworks_service.py — Fireworks AI E2E Flow

## Purpose
Complete Fireworks AI lifecycle: signup → OTP verify → login → onboarding → API key generation. Uses 100% SIN-Browser-Tools (zero raw Playwright evaluate calls).

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

### React Controlled Inputs
Fireworks uses React controlled inputs. `browser_fill()` uses `page.type()` which doesn't clear existing values for CSS selectors. Fixed by using native React value setter:
```javascript
var setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
setter.call(input, newValue);
input.dispatchEvent(new Event('input', {bubbles: true}));
input.dispatchEvent(new Event('change', {bubbles: true}));
```

### Account ID Constraint
Fireworks limits Account ID to 20 characters. Generated as `sin` + 8 random alphanumeric = 11 chars.

## Key Decisions

### Why `browser_press("Enter")` instead of `browser_click_by_text("Next")` for signup/login submit?
The Fireworks page has a carousel "Next slide" button (disabled) that appears before the form's "Next" button in the DOM. `browser_click_by_text("Next", role="button")` matches the carousel button first. Enter key bypasses this entirely.
**CRITICAL:** Do NOT replace Enter key with JS dispatchEvent or `browser_click_by_text` — this was tried and broke the flow (s. tag `v19.1-working-revert`).

### Why native React setter instead of `browser_fill()`?
`browser_fill()` → `browser_type()` → `page.type()` for CSS selectors. `page.type()` doesn't clear existing React state. Native setter + synthetic events properly update React's internal state.

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
5. _playwright_onboarding() → Account ID + Name + Terms → use cases → Submit
6. create_api_key()   → Navigate to API keys → Create → Generate → poll for fw_ key
```

## Known Issues
- `browser_click_checkbox_by_text()` may not trigger React state updates for custom button-based checkboxes (e.g., Fireworks Terms). Fallback: `browser_console()` with direct DOM click.
- Onboarding redirect detection relies on URL containing `home`/`account`/`settings` — may break if Fireworks changes URL structure.
- Submit button in onboarding is often disabled (React validation pending). `browser_click_by_text("Submit")` + fallback texts fails silently. Fixed with `browser_press("Enter")` as final fallback — bypasses disabled state.
- The Enter key pattern matches login/signup flow (same reason: carousel "Next slide" button conflict).
