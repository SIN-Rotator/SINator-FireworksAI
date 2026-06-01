# Fireworks AI — Kompletter Flow (Visual + CSS/Code)

> **V18.0 Post-CEO-Fix** — Diese Doku reflektiert den Code-Stand nach Issue #22.
> Die folgenden Fixes sind in den Code-Beispielen eingearbeitet:
>
> | Fix | Beschreibung |
> |-----|--------------|
> | **F1** | `page.evaluate()` nutzt dict-args (`page.evaluate(JS, {"arg": val})`) statt f-string + positional args |
> | **F5** | `browser.new_page()` ersetzt durch `_get_new_page()` Helper (CDP-kompatibel) |
> | **O1** | `login_fireworks()` erkennt logged-in State (post-verify) und skippt zum Onboarding |
> | **O2** | `wait_for_url_change("/signup")` statt `wait_for_spa_transition("verify")` (kein 15s Timeout) |
> | **O3** | `create_api_key()` nutzt `_get_new_page()` Helper |

---

## CDP-Helper (F5 / O3)

> **WICHTIG:** Bei CDP-Verbindung (`connect_over_cdp`) wirft `browser.new_page()`
> den Fehler *"Please use browser.new_context()"*. Daher IMMER diesen Helper nutzen:

```python
async def _get_new_page(browser):
    """F5/O3 FIX: CDP-kompatibel neue Page holen."""
    if browser.contexts:
        return await browser.contexts[0].new_page()
    else:
        return await browser.new_page()
```

---

## SCHRITT 1: `signup_fireworks()` — Account erstellen

### Screen 1.1 — Signup Seite
```
┌─────────────────────────────────────────────┐
│                                             │
│  [ Accept All ]  ← Cookie-Banner           │
│                                             │
│  Email        [_____________________]       │
│                                             │
│  [ Next ]                                    │
└─────────────────────────────────────────────┘
```

**CSS-Selektoren:**
```python
# F5 FIX: CDP-kompatibel neue Page holen
page = await _get_new_page(browser)

# Cookie-Banner via JS API (React-kompatibel, NICHT element.remove())
from agent_toolbox.core.browser_utils import accept_cookieyes_via_js
await accept_cookieyes_via_js(page)
# Fallback: Button-Klick
# page.locator('button:has-text("Accept All")').first.click(force=True, timeout=5000)

# Email-Feld (React-kompatibel via fill_react_input)
from agent_toolbox.core.browser_utils import fill_react_input
await fill_react_input(page, 'input[name="email"], input[type="email"]', email)

# Next-Button
for btn in await page.locator('button[type="submit"]').all():
    if 'Next' in (await btn.text_content() or ''):
        await btn.click(force=True)
```

### Screen 1.2 — Passwort
```
┌─────────────────────────────────────────────┐
│                                             │
│  Password     [_____________________]       │
│  Confirm PW   [_____________________]       │
│                                             │
│  [ Create Account ]                         │
└─────────────────────────────────────────────┘
```

**CSS-Selektoren:**
```python
# Passwort-Felder (BEIDE)
pws = await page.locator('input[type="password"]').all()
for pw in pws[:2]:  # password + confirm
    await pw.click()
    await pw.fill("")
    await pw.type(password, delay=40)  # delay=40ms für React controlled inputs

# Create Account Button
for btn in await page.locator('button[type="submit"]').all():
    if 'Create Account' in (await btn.text_content() or ''):
        await btn.click(force=True)

# O2 FIX: Auf URL-Wechsel warten (NICHT auf Text "verify" — sonst 15s Timeout)
from agent_toolbox.core.browser_utils import wait_for_url_change
await wait_for_url_change(page, "/signup", timeout=15)
```

**Rückgabe:** `{status: "signup_done"}` — OTP wird von rotate.py (User Chrome) gelesen.

---

## SCHRITT 2: `verify_account(verify_url)` — Email bestätigen

```
┌─────────────────────────────────────────────┐
│                                             │
│  🔄 Page geht zu verify URL                 │
│  (z.B. /signup/confirm?client_id=...)       │
│                                             │
│  "Your account is verified!"                │
│                                             │
└─────────────────────────────────────────────┘
```

**CSS-Selektoren:**
```python
# F5 FIX: CDP-kompatibel neue Page holen
page = await _get_new_page(browser)
await page.goto(verify_url, wait_until='domcontentloaded')
await asyncio.sleep(2)
```

**Rückgabe:** True/False

> **O1 Kontext:** Nach `verify_account()` ist der Browser oft bereits eingeloggt.
> `login_fireworks()` erkennt das (siehe Schritt 3) und überspringt das Login-Formular.

---

## SCHRITT 3: `login_fireworks()` — Einloggen + Onboarding

### Screen 3.0 — O1 FIX: Already-Logged-In Erkennung (post-verify)

```
┌─────────────────────────────────────────────┐
│  page.goto("/login")                        │
│         │                                   │
│         ▼                                   │
│  URL enthält "login"?                       │
│    NEIN ──► Bereits eingeloggt!             │
│            └─► Onboarding falls nötig        │
│            └─► return {status: "success"}    │
│    JA   ──► Login-Formular ausfüllen        │
└─────────────────────────────────────────────┘
```

**CSS-Selektoren:**
```python
# F5 FIX: CDP-kompatibel neue Page holen
page = await _get_new_page(browser)
await page.goto("https://app.fireworks.ai/login")
await asyncio.sleep(2)

# O1 FIX: Prüfen ob bereits eingeloggt (post-verify Redirect)
current_url = page.url
if skip_if_logged_in and 'login' not in current_url.lower():
    # Bereits authentifiziert!
    if 'onboarding' in current_url:
        await _fireworks_react_onboarding(page)
    return {"status": "success", "steps_completed": ["already_logged_in", "login_success"]}
```

### Screen 3.1 — Login (nur wenn NICHT eingeloggt)
```
┌─────────────────────────────────────────────┐
│                                             │
│  [ Accept All ]  ← Cookie-Banner           │
│                                             │
│  "Email Login"  ← Link klicken             │
│  ODER: /login?useEmail=true                 │
│                                             │
│  Email        [_____________________]       │
│  Password     [_____________________]       │
│                                             │
│  [ Next ]                                    │
└─────────────────────────────────────────────┘
```

**CSS-Selektoren:**
```python
# Cookie-Banner via JS API
await accept_cookieyes_via_js(page)

# O1 FIX: Nach Cookie-Handling erneut prüfen (Seite kann redirected haben)
if skip_if_logged_in and 'login' not in page.url.lower():
    if 'onboarding' in page.url:
        await _fireworks_react_onboarding(page)
    return {"status": "success", "steps_completed": ["already_logged_in", "login_success"]}

# Email Login Link (3× retry)
for attempt in range(3):
    em = page.locator('a:has-text("Email Login")').first
    if await em.count() > 0:
        await em.click()
    else:
        await page.goto("https://app.fireworks.ai/login?useEmail=true")
    await asyncio.sleep(2)
    if await page.locator('input[name="email"]').first.count() > 0:
        break

# O1 FIX: Kein Email-Input gefunden = bereits eingeloggt
email_input = page.locator('input[name="email"]').first
if await email_input.count() == 0:
    if any(x in page.url for x in ['home', 'account', 'settings', 'onboarding']):
        if 'onboarding' in page.url:
            await _fireworks_react_onboarding(page)
        return {"status": "success", "steps_completed": ["already_logged_in"]}

# Login-Formular
await email_input.fill(email)
await page.locator('input[name="password"]').first.fill(password)

# Submit-Button
for btn in await page.locator('button[type="submit"]').all():
    if 'Next' in (await btn.text_content() or ''):
        await btn.click(force=True)
```

### Screen 3.2 — Onboarding (NUR wenn url `/onboarding`!)

```
┌─────────────────────────────────────────────┐
│  What should we call you?                   │
│                                             │
│  First name   [ Super            ]         │
│  Last name    [ Cheetah          ]         │
│                                             │
│  ☐ I agree to Terms of Service             │
│                                             │
│  [ Continue ]                               │
├─────────────────────────────────────────────┤
│  How will you use Fireworks AI?             │
│                                             │
│  ☐ Prototype an application                │
│  ☐ Flexible capacity / Dedicated           │
│  ☐ Conversational AI / Chat                │
│  ☐ Search / RAG                            │
│                                             │
│  [ Submit ]  oder  [ Get $5 ]               │
└─────────────────────────────────────────────┘
```

**CSS-Selektoren:**
```python
# Prüfung ob Onboarding nötig
if 'onboarding' in page.url:
    await _fireworks_react_onboarding(page)
```

#### Sub-Step A+B: First/Last Name (React-kompatibel)
```python
# F1 FIX-Kontext: fill_react_input nutzt intern page.evaluate(JS, {"selector":..., "value":...})
from agent_toolbox.core.browser_utils import fill_react_input
await fill_react_input(page, 'input[name="firstName"], input[name="first"]', "Super")
await fill_react_input(page, 'input[name="lastName"], input[name="last"]', "Cheetah")
```

#### Sub-Step C: Terms Checkbox (TOS-Trap-safe)
```python
# click_react_checkbox erkennt <a>-Tags im Label (TOS-Trap) und klickt
# stattdessen das via for-Attribut referenzierte Element
from agent_toolbox.core.browser_utils import click_react_checkbox
await click_react_checkbox(page, "agree")
await click_react_checkbox(page, "terms")
```

#### Sub-Step D: Continue Button
```python
for btn in await page.locator('button').all():
    txt = (await btn.text_content() or '').strip()
    if 'Continue' in txt or 'Next' in txt:
        await btn.click(force=True)
        await asyncio.sleep(2)
        break
```

#### Sub-Step E: SPA-Transition warten (F1 FIX)
```python
# F1 FIX: wait_for_spa_transition nutzt intern dict-args:
#   page.evaluate(JS, {"targetText": ..., "timeoutMs": ...})
# NICHT mehr f-string-Interpolation + positional args!
from agent_toolbox.core.browser_utils import wait_for_spa_transition
await wait_for_spa_transition(page, "Prototype with open models", timeout=10)
```

#### Sub-Step F: Use-Case Checkboxes
```python
for uc in ["Prototype", "Flexible capacity", "Conversational", "Search"]:
    await click_react_checkbox(page, uc)
    await asyncio.sleep(0.2)
```

#### Sub-Step G: Submit Button
```python
for btn in await page.locator('button').all():
    txt = (await btn.text_content() or '').strip()
    if 'Submit' in txt or 'Get $5' in txt:
        await btn.click(force=True)
        await asyncio.sleep(4)
        break
```

#### Sub-Step H: Warten auf Redirect
```python
for _ in range(10):
    await asyncio.sleep(2)
    if any(x in page.url for x in ['home', 'account', 'settings', 'models']) and 'login' not in page.url:
        break  # Onboarding erfolgreich

# Fallback: Force Navigate
# page.goto("https://app.fireworks.ai/settings/users/api-keys",
#           timeout=15000, wait_until='domcontentloaded')
```

### Screen 3.3 — Model Library (nach erfolgreichem Login)
```
┌─────────────────────────────────────────────┐
│  🔄 Lädt Model Library Seite               │
│  url = /models  oder /home                  │
│                                             │
│  "Model Library - Fireworks AI"             │
└─────────────────────────────────────────────┘
```

**Prüfung:**
```python
# 8×2s = max 16s warten
for attempt in range(8):
    await asyncio.sleep(2)
    if any(x in page.url for x in ['home', 'account', 'settings']) and 'login' not in page.url:
        return {"status": "success"}  # Eingeloggt

# Force Navigate Check (F5 FIX: _get_new_page statt browser.new_page)
for url in [
    "https://app.fireworks.ai/settings/users/api-keys",
    "https://app.fireworks.ai/",
]:
    fresh = await _get_new_page(browser)  # F5 FIX
    await fresh.goto(url, timeout=15000, wait_until='domcontentloaded')
    await asyncio.sleep(2)
    if 'login' not in fresh.url.lower():
        return {"status": "success"}  # Eingeloggt
    await fresh.close()

return {"status": "error", "error": "Login failed"}
```

---

## SCHRITT 4: `create_api_key()` — Key generieren

### Screen 4.1 — API Keys Seite
```
┌─────────────────────────────────────────────┐
│  /settings/users/api-keys                   │
│                                             │
│  [ Accept All ]  ← Cookie-Banner           │
│                                             │
│  [ Create API Key ]  ← Button               │
└─────────────────────────────────────────────┘
```

**CSS-Selektoren:**
```python
# O3 FIX: CDP-kompatibel neue Page holen (NICHT browser.new_page())
pg = await _get_new_page(browser)
await pg.goto("https://app.fireworks.ai/settings/users/api-keys",
              wait_until='domcontentloaded')
await asyncio.sleep(2)

# Retry bei Login-Redirect (3×)
for _ in range(3):
    if 'login' in pg.url.lower():
        await pg.goto("https://app.fireworks.ai/settings/users/api-keys",
                      wait_until='domcontentloaded')
        await asyncio.sleep(2)
    else:
        break

# Cookie-Banner via JS API
await accept_cookieyes_via_js(pg)
```

### Screen 4.2 — Dropdown-Menü
```
┌─────────────────────────────────────────────┐
│                                             │
│  Create API Key ▼                           │
│  ┌─────────────────────────┐               │
│  │ API Key                 │  ← menuitem    │
│  │ ...                     │               │
│  └─────────────────────────┘               │
└─────────────────────────────────────────────┘
```

**CSS-Selektoren:**
```python
# Create API Key Button
for btn in await pg.locator('button').all():
    if 'Create API Key' in (await btn.text_content() or ''):
        await btn.click(force=True)
        await asyncio.sleep(2)
        break

# API Key Menuitem
menu = pg.locator('[role="menuitem"]:has-text("API Key")').first
for _ in range(5):
    if await menu.count() > 0:
        break
    await asyncio.sleep(1)
await menu.click(force=True)
await asyncio.sleep(2)
```

### Screen 4.3 — Dialog "Create API Key"
```
┌─────────────────────────────────────────────┐
│  Create API Key                             │
│                                             │
│  Name  [ sinator-key               ]        │
│                                             │
│  [ Cancel ]     [ Generate ]               │
│                  ↑ disabled → enabled      │
└─────────────────────────────────────────────┘
```

**CSS-Selektoren:**
```python
# Key Name eintippen (3× retry bei Missing Name Fehler)
for retry in range(3):
    suffix = f"-{retry}" if retry > 0 else ""
    name = key_name + suffix

    await pg.locator('input[name="name"]').first.click()
    await pg.locator('input[name="name"]').first.type(name, delay=40)
    await asyncio.sleep(1)

    # Auf Generate-Button warten (max 10s)
    generate_btn = None
    for _ in range(10):
        for btn in await pg.locator('button').all():
            txt = (await btn.text_content() or '').strip()
            if 'Generate' in txt:
                generate_btn = btn
                break
        if generate_btn and not await generate_btn.is_disabled():
            break
        await asyncio.sleep(1)

    if not generate_btn:
        continue  # Retry

    await generate_btn.click(force=True)

    # Polling auf API Key (15×1s = max 15s)
    # F1 FIX: page.evaluate ohne args ist OK (kein Interpolation nötig)
    for _ in range(15):
        await asyncio.sleep(1)
        text = await pg.evaluate("() => document.body.innerText")
        keys = re.findall(r'fw_[a-zA-Z0-9]{20,}', text)
        if keys:
            return {"status": "success", "api_key": keys[0]}
```

### Screen 4.4 — Missing Name Modal (NUR bei Fehler)
```
┌─────────────────────────────────────────────┐
│  ⚠ Missing Name                             │
│  Please enter a name for your API key       │
│                                             │
│  [ OK ]                                     │
└─────────────────────────────────────────────┘
```

**CSS-Selektoren:**
```python
# Missing Name erkennen und schließen
body = await pg.evaluate("() => document.body.innerText")
if 'Missing' in body and 'Name' in body:
    for btn in await pg.locator('button').all():
        txt = (await btn.text_content() or '').strip()
        if txt in ['Close', 'Cancel', 'OK', '×']:
            await btn.click(force=True)
            await asyncio.sleep(1)
            break
    continue  # Nächster Retry mit sinator-key-1
```

---

## ENDE

```python
return {"status": "success", "api_key": "fw_XXXXXXXXXXXXXXXXXXXXXXXXXX"}
# → PoolManager.add_key(api_key, alias_email, key_name)
# → in fireworksai-pool.json gespeichert
```

---

## Anhang: browser_utils.py Helper-Übersicht (V18.0)

| Helper | Zweck | F1-Fix? |
|--------|-------|---------|
| `accept_cookieyes_via_js(page)` | CookieYes via JS API (kein DOM-remove) | — |
| `wait_for_spa_transition(page, text, timeout)` | MutationObserver auf Text | dict-args |
| `wait_for_url_change(page, fragment, timeout)` | Pollt URL-Wechsel (O2-Alternative) | — |
| `fill_react_input(page, selector, value)` | Native-Setter + input/change Events | dict-args |
| `click_react_checkbox(page, label)` | TOS-Trap-safe Checkbox-Klick | dict-args |
| `extract_jwt_from_localstorage(page, key)` | Token aus localStorage | dict-args |

> **F1-Regel:** Alle `page.evaluate()`-Aufrufe MIT Argumenten nutzen das dict-Pattern:
> ```python
> await page.evaluate("(args) => { ... args.foo ... }", {"foo": value})
> ```
> NIEMALS f-string-Interpolation in den JS-String oder positional args verwenden.
