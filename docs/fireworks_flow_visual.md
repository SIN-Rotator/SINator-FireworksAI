# Fireworks AI — Kompletter Flow (Visual + CSS/Code)

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
# Cookie-Banner
page.locator('button:has-text("Accept All")').first.click(force=True, timeout=5000)

# Email-Feld (priority)
page.locator('input[name="email"]').first.fill(email)
# Fallback
page.locator('input[type="email"]').first.fill(email)

# Next-Button (priority)
page.locator('button:has-text("Next")').first.click(force=True)
# Fallback
for btn in page.locator('button[type="submit"]').all():
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
pws = page.locator('input[type="password"]').all()
for pw in pws[:2]:  # password + confirm
    pw.click()
    pw.fill("")
    pw.type(password, delay=40)  # delay=40ms für React controlled inputs

# Create Account Button
page.locator('button:has-text("Create Account")').first.click(force=True)
# Fallback
for btn in page.locator('button[type="submit"]').all():
    if 'Create Account' in (await btn.text_content() or ''):
        await btn.click(force=True)

# Warten auf Page-Weiterleitung (15×1s = max 15s)
for _ in range(15):
    sleep(1)
    if '/signup' not in page.url or 'verify' in page.url:
        break  # Seite hat sich weiterbewegt
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
page.goto(verify_url, wait_until='domcontentloaded')
sleep(3)
```

**Rückgabe:** True/False

---

## SCHRITT 3: `login_fireworks()` — Einloggen + Onboarding

### Screen 3.1 — Login
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
# Cookie-Banner
page.locator('button:has-text("Accept All")').first.click(force=True, timeout=5000)

# Email Login Link (3× retry)
for attempt in range(3):
    em = page.locator('a:has-text("Email Login")').first
    if em.count() > 0:
        em.click()
    else:
        page.goto("https://app.fireworks.ai/login?useEmail=true")
    sleep(2)
    if page.locator('input[name="email"]').first.count() > 0:
        break

# Login-Formular
page.locator('input[name="email"]').first.fill(email)
page.locator('input[name="password"]').first.fill(password)

# Submit-Button
page.locator('button:has-text("Next")').first.click()
# Fallback
for btn in page.locator('button[type="submit"]').all():
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
```

#### Sub-Step A: First Name
```python
fn = page.locator('input[name="firstName"]').first
if fn.count() == 0:
    fn = page.locator('input[name="first"]').first
if fn.count() > 0:
    fn.click()
    sleep(0.2)
    fn.type("Super", delay=50)   # 50ms delay für React
    sleep(0.5)
```

#### Sub-Step B: Last Name
```python
ln = page.locator('input[name="lastName"]').first
if ln.count() == 0:
    ln = page.locator('input[name="last"]').first
if ln.count() > 0:
    ln.click()
    sleep(0.2)
    ln.type("Cheetah", delay=50)
    sleep(0.5)
```

#### Sub-Step C: Terms Checkbox
```python
terms = None
for cb in page.locator('input[type="checkbox"]').all():
    lbl = (await cb.get_attribute('aria-label') or '').lower()
    n_id = (await cb.get_attribute('id') or '').lower()
    if 'terms' in lbl or 'agree' in lbl or 'terms' in n_id:
        terms = cb
        break
if not terms:
    terms = page.locator('label:has-text("Terms")').first
if terms.count() > 0:
    terms.click(force=True)
    sleep(0.5)
```

#### Sub-Step D: Continue Button
```python
for btn in page.locator('button').all():
    txt = (await btn.text_content() or '').strip()
    if 'Continue' in txt or 'Next' in txt:
        btn.click(force=True)
        sleep(2)
        break
```

#### Sub-Step E: Use-Case Checkboxes
```python
for uc in ["Prototype", "Flexible capacity", "Conversational", "Search"]:
    for inp in page.locator('input[type="checkbox"]').all():
        i_id = (await inp.get_attribute('id') or '').lower()
        if 'cky' in i_id:
            continue  # Cookie-Banner Checkbox überspringen
        label = (await inp.get_attribute('aria-label') or '')
        if uc.lower() in label.lower():
            inp.click(force=True)
            sleep(0.3)
            break
```

#### Sub-Step F: Submit Button
```python
for btn in page.locator('button').all():
    txt = (await btn.text_content() or '').strip()
    if 'Submit' in txt or 'Get $5' in txt:
        btn.click(force=True)
        sleep(4)
        break
```

#### Sub-Step G: Warten auf Redirect
```python
for _ in range(10):
    sleep(2)
    if any(x in page.url for x in ['home', 'account', 'settings', 'models']):
        break  # Onboarding erfolgreich

# Fallback: Force Navigate
if kein redirect:
    page.goto("https://app.fireworks.ai/settings/users/api-keys",
              timeout=20000, wait_until='domcontentloaded')
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
# 12×2s = max 24s warten
for _ in range(12):
    sleep(2)
    url = page.url
    if any(x in url for x in ['home', 'account', 'settings', 'api-keys', 'models']):
        return {"status": "success"}  # ✅ Eingeloggt

# Force Navigate Check
for url in [
    "https://app.fireworks.ai/settings/users/api-keys",
    "https://app.fireworks.ai/",
]:
    page.goto(url, wait_until='domcontentloaded')
    sleep(2)
    if 'login' not in page.url.lower():
        return {"status": "success"}  # ✅ Eingeloggt

return {"status": "error", "error": "could not reach home/settings"}
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
# Navigation zur API Keys Seite
page.goto("https://app.fireworks.ai/settings/users/api-keys",
          wait_until='domcontentloaded')
sleep(3)

# Retry bei Login-Redirect (3×)
for _ in range(3):
    if 'login' in page.url.lower():
        page.goto("https://app.fireworks.ai/settings/users/api-keys",
                  wait_until='domcontentloaded')
        sleep(3)
    else:
        break

# Cookie-Banner
for btn in page.locator('button').all():
    txt = (await btn.text_content() or '').strip()
    if txt in ('Accept All', 'Reject All'):
        btn.click(force=True)
        sleep(1)
        break
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
# Create API Key Button (3× retry)
for attempt in range(3):
    for btn in page.locator('button').all():
        if 'Create API Key' in (await btn.text_content() or ''):
            btn.click(force=True)
            sleep(2)
            break

    # API Key Menuitem
    menu = page.locator('[role="menuitem"]:has-text("API Key")').first
    for _ in range(5):
        if menu.count() > 0:
            break
        sleep(1)
    if menu.count() > 0:
        menu.click(force=True)
        sleep(2)

    # Prüfen ob Dialog erschienen ist
    inp = page.locator('input[name="name"]').first
    for _ in range(5):
        if inp.count() > 0:
            break
        sleep(1)
    if inp.count() > 0:
        break  # Dialog offen
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

    inp = page.locator('input[name="name"]').first
    inp.click()
    sleep(0.2)
    inp.fill("")
    inp.type(name, delay=40)
    sleep(1)

    # Auf Generate-Button warten (max 10s)
    for _ in range(10):
        for btn in page.locator('button').all():
            txt = (await btn.text_content() or '').strip()
            if 'Generate' in txt and not btn.is_disabled():
                generate_btn = btn
                break
        if generate_btn:
            break
        sleep(1)

    if not generate_btn:
        continue  # Retry

    generate_btn.click(force=True)

    # Polling auf API Key (15×1s = max 15s)
    for _ in range(15):
        sleep(1)
        text = page.evaluate("() => document.body.innerText")
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
body = page.evaluate("() => document.body.innerText")
if 'Missing' in body and 'Name' in body:
    for btn in page.locator('button').all():
        txt = (await btn.text_content() or '').strip()
        if txt in ['Close', 'Cancel', 'OK', '×']:
            btn.click(force=True)
            sleep(1)
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
