"""
SINATOR — Fireworks Service V6 (Playwright+CUA + Fallback, 2026-05-22)

Lightweight wrapper replacing the 3103-line CDP fireworks_service.py.
Uses Playwright for form interaction, CUA for React checkboxes.
"""
import logging
import re
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def signup_fireworks(email: str, password: str) -> Dict[str, Any]:
    """Create new Fireworks account via signup form + OTP verification.
    
    Flow:
    1. /signup → fill email → Next → fill 2x password → Create Account
    2. Poll GMX for verification email (via MailCheck extension)
    3. Open verify URL to confirm account
    4. Returns {status, verify_url, steps_completed}
    """
    import asyncio
    import sys
    from playwright.async_api import async_playwright
    from pathlib import Path as _Path
    
    steps = []
    try:
        _sys_path = sys.path.copy()
        sys.path.insert(0, str(_Path(__file__).parent))
        
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            page = await browser.contexts[0].new_page()
            
            # Step 1: Signup form
            await page.goto("https://app.fireworks.ai/signup")
            await asyncio.sleep(3)
            
            # Cookie
            try:
                await page.locator('button:has-text("Accept All")').first.click(force=True, timeout=5000)
                await asyncio.sleep(2)
            except: pass
            
            # Fill email
            email_inp = page.locator('input[name="email"]').first
            if await email_inp.count() == 0:
                email_inp = page.locator('input[type="email"]').first
            await email_inp.fill(email)
            steps.append("email_filled")
            await asyncio.sleep(1)
            
            # Next
            for btn in await page.locator('button[type="submit"]').all():
                if 'Next' in (await btn.text_content() or ''):
                    await btn.click(force=True); await asyncio.sleep(3)
                    break
            steps.append("next_clicked")
            
            # Fill BOTH passwords
            pws = await page.locator('input[type="password"]').all()
            if len(pws) >= 2:
                for pw in pws[:2]:
                    await pw.click(); await asyncio.sleep(0.2)
                    await pw.fill("")
                    await pw.type(password, delay=40)
                    await asyncio.sleep(0.3)
                steps.append("passwords_filled")
                await asyncio.sleep(1)
                
                # Create Account
                for btn in await page.locator('button[type="submit"]').all():
                    if 'Create Account' in (await btn.text_content() or ''):
                        await btn.click(force=True); await asyncio.sleep(4)
                        logger.info("Create Account clicked")
                        break
                steps.append("create_clicked")
            
            # Step 2: Poll for OTP email
            logger.info("Waiting for Fireworks verification email...")
            verify_url = None
            from gmx_service import GmxService
            svc = GmxService()
            
            for attempt in range(12):
                await asyncio.sleep(6)
                verify_url = await svc.read_fireworks_verification_email()
                if verify_url:
                    logger.info(f"✅ OTP found (attempt {attempt+1})")
                    break
                logger.info(f"OTP poll {attempt+1}/12...")
            
            if not verify_url:
                steps.append("otp_not_found")
                return {"status": "partial", "steps_completed": steps, "error": "OTP email not found after 10 attempts"}
            
            steps.append("otp_found")
            
            # Step 3: Verify account
            verified = await verify_account(verify_url)
            if verified:
                steps.append("account_verified")
                logger.info("✅ Account verified")
            else:
                steps.append("verify_failed")
            
            return {
                "status": "success",
                "verify_url": verify_url,
                "steps_completed": steps,
            }
            
    except Exception as e:
        logger.error(f"Signup error: {e}")
        return {"status": "error", "steps_completed": steps, "error": str(e)}


async def login_fireworks(email: str, password: str) -> Dict[str, Any]:
    """Login to Fireworks via Playwright + CUA onboarding.
    Returns: {status, steps_completed, error}"""
    import asyncio
    import json
    import subprocess
    import re as _re
    from playwright.async_api import async_playwright

    steps = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            page = await browser.contexts[0].new_page()

            await page.goto("https://app.fireworks.ai/login")
            await asyncio.sleep(3)

            # Cookie accept
            try:
                await page.locator('button:has-text("Accept All")').first.click(force=True, timeout=5000)
                await asyncio.sleep(1)
            except: pass

            # Email Login
            await page.locator('a:has-text("Email Login")').first.click()
            await asyncio.sleep(3)
            steps.append("login_page")

            # Fill credentials
            await page.locator('input[name="email"]').first.fill(email)
            await page.locator('input[name="password"]').first.fill(password)
            steps.append("credentials_filled")

            # Submit
            for btn in await page.locator('button[type="submit"]').all():
                if 'Next' in (await btn.text_content() or ''):
                    await btn.click()
                    await asyncio.sleep(4)
                    break
            steps.append("form_submitted")

            # Onboarding via CUA with Playwright fallback
            if 'onboarding' in page.url:
                logger.info("Onboarding via CUA + Playwright")
                from cua_helper import find_cua_window
                cua = find_cua_window(title_keywords=["fireworks"])
                if cua:
                    pid, wid = cua
                    
                    def _cua_click(el):
                        subprocess.run(["cua-driver", "call", "click"],
                            capture_output=True, text=True, timeout=10,
                            input=json.dumps({"pid": pid, "window_id": wid, "element_index": el}))
                    
                    def _cua_type(text):
                        subprocess.run(["cua-driver", "call", "type_text"],
                            capture_output=True, text=True, timeout=5,
                            input=json.dumps({"pid": pid, "text": text}))
                    
                    def _cua_scan():
                        from cua_helper import cua_get_window_state
                        return cua_get_window_state(pid, wid)
                    
                    def _find_element(text, el_type="AXButton"):
                        for line in _cua_scan().split('\n'):
                            s = line.strip()
                            if text in s and el_type in s:
                                m = _re.search(r'\]?\s*-\s*\[(\d+)\]', s)
                                if m: return int(m.group(1))
                        return None
                    
                    # Fill names via CUA
                    for name, target in [("Super", "First"), ("Cheetah", "Last")]:
                        el = _find_element(target, "AXTextField")
                        if el:
                            _cua_click(el); await asyncio.sleep(0.3)
                            _cua_type(name); await asyncio.sleep(0.3)
                    
                    # Terms checkbox
                    el = _find_element("agree", "AXCheckBox")
                    if el: _cua_click(el); await asyncio.sleep(0.3)
                    
                    # Continue
                    el = _find_element("Continue")
                    if el: _cua_click(el); await asyncio.sleep(4)
                    
                    # Use-cases
                    for uc_text in ["Prototype", "Flexible", "Conversational", "Search"]:
                        el = _find_element(uc_text, "AXCheckBox")
                        if el:
                            _cua_click(el); await asyncio.sleep(0.2)
                    
                    # Submit — try CUA first
                    el = _find_element("Submit")
                    if el:
                        _cua_click(el)
                        for attempt in range(8):
                            await asyncio.sleep(2)
                            if 'home' in page.url or 'account' in page.url or 'settings' in page.url:
                                logger.info(f"Redirect detected (attempt {attempt+1})")
                                break
                        else:
                            logger.warning("CUA Submit — kein Redirect, Playwright-Fallback")
                            # Playwright fallback: fill form directly
                            await _fireworks_playwright_onboarding(page)
                    else:
                        logger.warning("CUA Submit nicht gefunden — Playwright-Fallback")
                        await _fireworks_playwright_onboarding(page)
                else:
                    logger.warning("CUA window not found — Playwright-Fallback")
                    await _fireworks_playwright_onboarding(page)
                steps.append("onboarding_complete")

            # Wait for redirect after onboarding (poll up to 15s)
            for attempt in range(8):
                await asyncio.sleep(2)
                if any(x in page.url for x in ['home', 'account', 'settings']):
                    logger.info(f"Redirect detected ({page.url[:60]})")
                    steps.append("login_success")
                    return {"status": "success", "steps_completed": steps}

            # Force navigate to API keys
            logger.warning(f"Kein Redirect — force navigate ({page.url[:60]})")
            try:
                await page.goto("https://app.fireworks.ai/settings/users/api-keys", timeout=15000, wait_until='domcontentloaded')
                await asyncio.sleep(3)
                if any(x in page.url for x in ['home', 'account', 'settings']):
                    steps.append("login_success")
                    return {"status": "success", "steps_completed": steps}
            except: pass

            # Still on onboarding? Try home page
            if 'onboarding' in page.url:
                logger.warning("Noch auf /onboarding — retry force navigate zu home")
                retries = 2
                for r in range(retries):
                    try:
                        await page.goto("https://app.fireworks.ai/", timeout=15000, wait_until='domcontentloaded')
                        await asyncio.sleep(4)
                        if any(x in page.url for x in ['home', 'account', 'settings', 'fireworks']):
                            steps.append("login_success")
                            return {"status": "success", "steps_completed": steps}
                    except: pass
                    if r < retries - 1:
                        logger.warning(f"Retry {r+1}/{retries}...")
                        await asyncio.sleep(3)

            return {"status": "error", "steps_completed": steps, "error": f"Login failed: {page.url[:80]}"}

    except Exception as e:
        logger.error(f"Fireworks login error: {e}")
        return {"status": "error", "steps_completed": steps, "error": str(e)}


async def _fireworks_playwright_onboarding(page) -> None:
    """Playwright-based onboarding fallback (fill names, checkboxes, submit)."""
    import asyncio
    
    # Fill First Name
    fn = page.locator('input[name="firstName"]').first
    if await fn.count() == 0:
        fn = page.locator('input[name="first"]').first
    if await fn.count() > 0:
        await fn.fill("Super"); await asyncio.sleep(0.5)
    
    # Fill Last Name
    ln = page.locator('input[name="lastName"]').first
    if await ln.count() == 0:
        ln = page.locator('input[name="last"]').first
    if await ln.count() > 0:
        await ln.fill("Cheetah"); await asyncio.sleep(0.5)
    
    # Terms checkbox
    terms = page.locator('input[type="checkbox"]').first
    if await terms.count() > 0:
        await terms.check(force=True); await asyncio.sleep(0.5)
    
    # Continue button
    for btn in await page.locator('button').all():
        txt = (await btn.text_content() or '').strip()
        if 'Continue' in txt or 'Next' in txt:
            await btn.click(force=True); await asyncio.sleep(3)
            break
    
    # Use-case checkboxes
    for uc in ["Prototype", "Flexible capacity", "Conversational", "Search"]:
        cb = page.locator(f'label:has-text("{uc}")').first
        if await cb.count() > 0:
            await cb.click(force=True); await asyncio.sleep(0.3)
        else:
            # Try direct checkbox
            for inp in await page.locator('input[type="checkbox"]').all():
                label = await inp.get_attribute('aria-label') or ''
                if uc.lower() in label.lower():
                    await inp.check(force=True); await asyncio.sleep(0.3)
                    break
    
    # Submit
    for btn in await page.locator('button').all():
        txt = (await btn.text_content() or '').strip()
        if 'Submit' in txt or 'Get $5' in txt:
            await btn.click(force=True); await asyncio.sleep(4)
            break
    
    # Poll for redirect (max 20s)
    for _ in range(10):
        await asyncio.sleep(2)
        if any(x in page.url for x in ['home', 'account', 'settings']):
            logger.info("Playwright onboarding complete")
            return
    logger.warning("Playwright onboarding — kein Redirect, force navigate")
    try:
        await page.goto("https://app.fireworks.ai/settings/users/api-keys", timeout=15000, wait_until='domcontentloaded')
        await asyncio.sleep(3)
    except:
        try:
            await page.goto("https://app.fireworks.ai/settings/users/api-keys", timeout=20000)
            await asyncio.sleep(3)
        except:
            logger.error("Force navigate failed")


async def create_api_key(key_name: str = "sinator-key") -> Dict[str, Any]:
    """Create Fireworks API Key via Playwright. Returns {status, api_key, error}"""
    import asyncio
    from playwright.async_api import async_playwright

    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            for pg in browser.contexts[0].pages:
                if 'fireworks' in pg.url and ('home' in pg.url or 'account' in pg.url):
                    await pg.goto("https://app.fireworks.ai/settings/users/api-keys")
                    await asyncio.sleep(3)

                    for btn in await pg.locator('button').all():
                        if 'Create API Key' == (await btn.text_content() or '').strip():
                            await btn.click(force=True); await asyncio.sleep(2)
                            break

                    await pg.locator('[role="menuitem"]:has-text("API Key")').first.click(force=True)
                    await asyncio.sleep(3)

                    for inp in await pg.locator('input').all():
                        if 'name' in (await inp.get_attribute('name') or '').lower():
                            await inp.fill(key_name)
                            await asyncio.sleep(1)
                            break

                    # Wait for Generate button to be enabled
                    generate_btn = None
                    for btn in await pg.locator('button').all():
                        if 'Generate' in (await btn.text_content() or '').strip():
                            generate_btn = btn
                            break
                    if generate_btn:
                        disabled = await generate_btn.get_attribute('disabled')
                        if disabled is not None:
                            logger.warning("Generate button disabled — waiting for enable")
                            for _ in range(5):
                                await asyncio.sleep(1)
                                disabled = await generate_btn.get_attribute('disabled')
                                if disabled is None:
                                    break
                        await generate_btn.click(force=True)

                    # Poll for API Key in DOM (max 10s, check alle 1s)
                    api_key = None
                    for _ in range(10):
                        await asyncio.sleep(1)
                        text = await pg.evaluate("() => document.body.innerText")
                        keys = re.findall(r'fw_[a-zA-Z0-9]{20,}', text)
                        if keys:
                            api_key = keys[0]
                            break

                    if api_key:
                        logger.info(f"API Key created: {api_key[:12]}...")
                        return {"status": "success", "api_key": api_key}

                    # Check for "Missing API Key Name!" error modal
                    body = await pg.evaluate("() => document.body.innerText")
                    if 'Missing' in body and 'Name' in body:
                        logger.warning("API Key error modal — close and retry")
                        for btn in await pg.locator('button').all():
                            txt = (await btn.text_content() or '').strip()
                            if txt in ['Close', 'Cancel', 'OK', '×']:
                                await btn.click(force=True); await asyncio.sleep(1)
                                break
                    return {"status": "error", "error": "API Key not found after polling"}

            return {"status": "error", "error": "No Fireworks page found"}

    except Exception as e:
        logger.error(f"API Key error: {e}")
        return {"status": "error", "error": str(e)}


async def verify_account(verify_url: str) -> bool:
    """Open Fireworks verify URL to confirm account. Returns True if confirmed."""
    import asyncio
    from playwright.async_api import async_playwright
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            page = await browser.contexts[0].new_page()
            await page.goto(verify_url)
            await asyncio.sleep(3)
            logger.info(f"Verify URL opened: {page.url[:80]}")
            await page.close()
            return True
    except Exception as e:
        logger.error(f"Verify error: {e}")
        return False
