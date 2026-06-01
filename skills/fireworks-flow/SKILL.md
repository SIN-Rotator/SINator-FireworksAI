---
name: sinator-fireworks-flow
description: Fireworks AI Account-Generierung — Signup, OTP Verify, Login, Onboarding, API Key. 100% SIN-Browser-Tools, Bot Chrome via Playwright.
license: MIT
---

# SINator Fireworks Flow

## Bot Chrome (ephemeral, per-rotation)
- **Window:** 1200×800 (`--window-size=1200,800` — NIEMALS maximized)
- **Stealth:** webdriver undefined, plugins, de-DE locale, chrome.runtime
- **Anti-Detection:** `add_init_script` vor jeder Page-Navigation

## CRITICAL PATTERNS (NIEMALS ÄNDERN)

### 1. Enter Key für Signup/Login Form-Submit
```python
await browser_press("Enter")
```
**NIEMALS** `browser_click_by_text("Next", role="button")` — Fireworks Carousel "Next slide" Button (disabled) steht vor dem echten Form-Button im DOM und matched zuerst. Enter-Key ist der einzig reliable Weg.

### 2. Partial Match für Button-Text
```python
t.indexOf('Submit') !== -1  # NICHT t === 'Submit'
```
Fireworks ändert Button-Texte ("Submit" → "Submit to get $5 Credits"). Strict equality `===` bricht. Nutze `.indexOf()` / `.includes()` für Button-Labels.

### 3. Disabled-Button Bypass (Onboarding)
Wenn `browser_click_by_text("Submit")` fehlschlägt (disabled wegen React validation pending):
1. JS dispatchEvent als erster Fallback
2. `browser_press("Enter")` als letzter Fallback (native Form-Submit bypassed disabled)

### 4. React Native Value Setter
```python
await browser_console(f"""(() => {{
    var inp = document.querySelector('input[name="field"]');
    var setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    setter.call(inp, '{value}');
    inp.dispatchEvent(new Event('input', {{bubbles: true}}));
    inp.dispatchEvent(new Event('change', {{bubbles: true}}));
}})()""")
```
`browser_fill()` (→ `page.type()`) cleared nicht React state. Native Setter + synthetische Events aktualisieren React korrekt.

## Flow Sequence
```
1. launch()           → Bot Chrome + SIN-Browser-Tools registration
2. signup_fireworks() → Email → Enter → passwords → Create Account
3. verify_account()   → Open OTP-URL from GMX
4. login_fireworks()  → Email Login → email → Enter → onboarding detect
5. _playwright_onboarding() → Account ID + Name + Terms → use cases → Submit
6. create_api_key()   → /settings/users/api-keys → Create → Generate → fw_ key
```

## Bekannte Fallstricke
| Problem | Lösung |
|---------|--------|
| "Next" klickt carousel Button | `browser_press("Enter")` statt click |
| Submit disabled (React) | Enter-Key als Fallback |
| Button-Text geändert | `indexOf()` statt `===` |
| API-Key Page → /onboarding | Submit hat nicht geklickt (disabled) |
| CAPTCHA nach Signup | Neuen Alias, neuen Versuch |
| Verify-Email 180s Verzögerung | Polling bis 200s (25×8s) |

## Proven Working Tags
- `v19.1-fix-signup-enter` — Enter key fix (baseline, NIEMALS unterschreiten)
- `v19.1-fix-onboarding-enter` — Enter key fallback für onboarding Submit
- `v19.1-working-revert` — HEAD nach Revert auf v19.1-fix-signup-enter

## Referenzen
- `agent_toolbox/core/fireworks_service.py` — E2E Flow (V19.1, 100% SIN-Tools)
- `agent_toolbox/core/pool_manager.py` — Pool CRUD + Keychain
- `tools/rotate.py` — Rotation Orchestrator
- `proxy/server.py` — Pool Proxy (deepseek-v4-flash für verify)
