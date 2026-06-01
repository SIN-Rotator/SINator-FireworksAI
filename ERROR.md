# ERROR: Fireworks Onboarding — 2-Step SPA Flow Broken

## Symptom
After signup + verify + login, the onboarding page (`/onboarding`) shows step 1 (auth/welcome) but clicking Continue does NOT advance to step 2 (checkboxes). The rotation fails at API Key step because the account onboarding was never completed.

## Current State (2026-06-01, V18.4)

### What Works
- GMX Login + Alias creation/deletion
- Fireworks Signup + OTP polling + email verify
- Login (enters credentials, reaches `/onboarding`)
- Cookie consent dismissal (CookieYes preference center removed via DOM)
- Step 1 fields filled (Account ID, First Name, Last Name, Terms checkbox clicked)
- Continue button clicked

### What Breaks
- After clicking Continue, step 2 (checkboxes) does NOT appear
- 15s poll for "Prototype"/"Flexible"/"Conversational" text returns nothing
- Fallback force-navigate fails (session not authenticated)

## Root Cause Analysis

### The 2-Step SPA
The onboarding is a React SPA with 2 steps:
- **Step 1** (URL: `https://app.fireworks.ai/onboarding`): Authentication
  - Account ID (`input[name="accountId"]`)
  - First Name (`input[name="firstName"]`)
  - Last Name (`input[name="lastName"]`)
  - "I agree to the Terms of Service and Privacy Policy" checkbox (label with `<a>` links)
  - Continue button
- **Step 2** (same URL, React transition): Checkboxes
  - "What are your goals for using Fireworks?" (9 options: "Prototype with open models", "Flexible capacity for experimentation", "Flexible capacity for production", "Faster speeds or lower costs", "Fine-tune models for quality", "High reliability inference for production", "Migrate from closed to open models", "Migrate from self-hosting to third-party", "Other")
  - "What are your primary use cases?" (6 options: "Code Assistance", "Conversational AI", "Agentic AI", "Search", "Multimedia RAG", "Other")
  - "Submit to get $5 Credits" button
- No URL change between steps — must poll DOM for step 2 content

### CookieYes Overlay
CookieYes cookie consent renders a preference center on the onboarding page. `element.remove()` removes DOM elements but does NOT actually accept cookies — React does not re-render onboarding content when CookieYes DOM elements are removed because the cookie consent state is NOT persisted.

**Fix needed**: Accept CookieYes properly via their JS API (`CookieYes.acceptAll()`), or mock the consent response in localStorage/cookies before removing the overlay.

### Checkbox DOM Structure
Step 2 checkboxes are NOT standard `<input type="checkbox">` or `<label>` elements when the cookie overlay is active. They appear to be custom React `<div>`/`<span>` elements with click handlers (`onClick`). The `document.querySelectorAll('input[type="checkbox"], [role="checkbox"], label')` search fails because:
- Checkboxes are not yet in React render tree (step 2 not shown)
- When rendered, they use custom elements (no native checkbox semantics)

### Account ID Field
Step 1 has an Account ID field (`input[name="accountId"]`). This was ADDED by Fireworks after the old working code (V14/V15) was written. The old code only filled First/Last Name. Account ID must be filled AND unique (validation fires if taken).

### What We Tried (Failed Approaches)

| Approach | Result |
|----------|--------|
| `button.cky-btn-accept` click with `force=True` | Click succeeds but cookie consent NOT actually accepted (JS events not triggered by `force=True`) |
| `element.remove()` of all `[class*="cky"]` | Removes overlay but React state is unchanged → step 2 still not rendered |
| `body.style.overflow = 'auto'` after removal | No effect — body wasn't locked |
| Searching for checkboxes via `querySelectorAll` | Step 2 not rendered → nothing found |
| `fill(delay=50)` on Account ID | TypeError: `fill()` doesn't accept `delay` kwarg |
| Try `fill()` without `delay` | Might work but not tested yet with all fixes combined |
| `fill()` might not work for React fields | Use `type()` with `delay=50` instead |

## Required Fixes

### 1. CookieYes Proper Acceptance
Use CookieYes JS API before DOM removal:
```javascript
// Option A: Accept via API
if (window.CookieYes && CookieYes.acceptAll) {
    CookieYes.acceptAll();
} else {
    // Option B: Set consent in localStorage before removing
    localStorage.setItem('cookieyes-consent', JSON.stringify({
        necessary: true, functional: true, analytics: true, performance: true, advertisement: true
    }));
    document.querySelectorAll('[class*="cky"]').forEach(e => e.remove());
}
```

### 2. Checkbox Detection (Step 2)
After clicking Continue, poll for step 2 elements. Checkboxes are NOT standard HTML — use a broader search:
```javascript
// Find elements with matching text that look/act like checkboxes
var items = document.querySelectorAll('div, span, label');
for (var item of items) {
    var txt = (item.textContent || '').trim();
    if (txt === 'Prototype with open models' && item.offsetParent !== null) {
        item.click();
        break;
    }
}
```

### 3. Account ID Field
Fill with a unique value (use random suffix):
```python
acct_id = f"user{random.randint(10000, 99999)}"
await page.locator('input[name="accountId"]').first.fill(acct_id)
```

### 4. Terms Checkbox Click
The Terms label contains `<a>` links. DO NOT click the label directly (clicks the link!). Use `for`-attribute lookup or JS programmatic click:
```javascript
var label = document.querySelector('label:has-text("Terms")');
var forId = label.getAttribute('for');
if (forId) {
    var cb = document.getElementById(forId);
    if (cb && !cb.checked) cb.click();
}
```

### 5. SPA Step Detection
Don't wait for URL change. Poll DOM for step 2 text:
```python
for _ in range(15):
    has_step2 = await page.evaluate(
        'document.body.innerText.includes("Prototype") || '
        'document.body.innerText.includes("Flexible")'
    )
    if has_step2: break
    await asyncio.sleep(1)
```

## Missing SIN-Browser-Tools

| Issue | Tool | Description |
|-------|------|-------------|
| #21 | `browser_click_checkbox_by_text(text)` | Find + click checkbox by label text, handles custom React elements, Shadow DOM, SPA transitions |
| Not created | `browser_wait_for_text(text, timeout)` | Wait for text to appear in DOM (SPA-safe, polls `body.innerText`) |

## How to Reproduce

```bash
python3 tools/rotate.py --cdp-port 9222 --debug
```

Watch for:
```
Visible leaf text (26): ... BUTTON:Continue
Continue clicked (→ step 2)
Checkboxes did not appear after 15s
```

The checkboxes never appear because CookieYes consent wasn't properly accepted.
