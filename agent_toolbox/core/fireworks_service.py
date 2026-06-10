"""
SINATOR — Fireworks Service V6 (Playwright+CUA + Fallback, 2026-05-22)

Lightweight wrapper replacing the 3103-line CDP fireworks_service.py.
Uses Playwright for form interaction, CUA for React checkboxes.
"""
import logging
import re
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

from agent_toolbox.core.chrome_flags import CHROMIUM_GPU_FLAGS as _CHROMIUM_GPU_FLAGS


async def signup_fireworks(email: str, password: str, cdp_port: Optional[int] = None, page=None, browser=None) -> Dict[str, Any]:
    """Create new Fireworks account via signup form + OTP verification.
    
    Flow:
    1. /signup → fill email → Next → fill 2x password → Create Account
    2. Poll GMX for verification email (Playwright-native, Shadow-DOM + Multi-Frame Scan)
    3. Open verify URL to confirm account
    4. Returns {status, verify_url, steps_completed}
    
    If page provided, uses it (ONE Browser). Otherwise uses cdp_port or launches fresh Chromium.
    """
    import asyncio
    import sys
    from playwright.async_api import async_playwright
    from pathlib import Path as _Path
    
    steps = []
    own_browser = False
    own_page = False
    try:
        _sys_path = sys.path.copy()
        sys.path.insert(0, str(_Path(__file__).parent))
        
        if page is not None:
            # Use existing page (ONE Browser)
            pass
        elif cdp_port:
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(f"http://localhost:{cdp_port}")
                own_browser = True
                page = await browser.new_page()
                own_page = True
        else:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False, args=_CHROMIUM_GPU_FLAGS)
                own_browser = True
                page = await browser.new_page()
                own_page = True
        
        # Step 1: Signup form
        await page.goto("https://app.fireworks.ai/signup")
        await asyncio.sleep(2)
        
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
                await btn.click(force=True); await asyncio.sleep(2)
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
                    await btn.click(force=True)
                    logger.info("Create Account clicked")
                    break
            # Verify page advanced (wait for redirect away from /signup)
            for _ in range(10):
                await asyncio.sleep(1)
                if '/signup' not in page.url or 'verify' in page.url:
                    logger.info(f"Page advanced to: {page.url[:60]}")
                    break
            steps.append("create_clicked")
        
        # Step 2: Poll for OTP email via Playwright-native read_otp_via_playwright
        logger.info("Waiting for Fireworks verification email (Playwright-native)...")
        verify_url = None
        from agent_toolbox.core.gmx_service import GmxService
        svc = GmxService()
        
        for attempt in range(15):
            await asyncio.sleep(4)
            otp_result = await svc.read_otp_via_playwright(browser, sender_filter="fireworks", existing_page=page)
            if otp_result.get("status") == "success":
                verify_url = otp_result.get("otp_url")
                if verify_url:
                    logger.info(f"✅ OTP found (attempt {attempt+1})")
                    break
            logger.info(f"OTP poll {attempt+1}/15...")
        
        if not verify_url:
            steps.append("otp_not_found")
            return {"status": "partial", "steps_completed": steps, "error": "OTP email not found after 18 attempts"}
        
        steps.append("otp_found")
        
        # Step 3: Verify account — use ONE page/browser when available
        verified = await verify_account(verify_url, cdp_port=cdp_port, page=page, browser=browser)
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


async def login_fireworks(email: str, password: str, cdp_port: Optional[int] = None, page=None, browser=None) -> Dict[str, Any]:
    """Login to Fireworks via Playwright + CUA onboarding.
    Returns: {status, steps_completed, error}
    If page provided, uses it (ONE Browser). Otherwise uses cdp_port or launches fresh."""
    import asyncio
    import json
    import subprocess
    import re as _re
    from playwright.async_api import async_playwright

    steps = []
    own_browser = False
    _p = None
    try:
        if page is not None:
            pass
        elif cdp_port:
            _p = await async_playwright().start()
            browser = await _p.chromium.connect_over_cdp(f"http://localhost:{cdp_port}")
            own_browser = True
            page = await browser.new_page()
        else:
            _p = await async_playwright().start()
            browser = await _p.chromium.launch(headless=False, args=_CHROMIUM_GPU_FLAGS)
            own_browser = True
            page = await browser.new_page()

        await page.goto("https://app.fireworks.ai/login")
        await asyncio.sleep(2)

        # Cookie accept
        try:
            await page.locator('button:has-text("Accept All")').first.click(force=True, timeout=5000)
            await asyncio.sleep(1)
        except: pass

        # Email Login — retry wrapper for stale frame / navigation
        for attempt in range(3):
            try:
                em = page.locator('a:has-text("Email Login")').first
                if await em.count() > 0:
                    await em.click()
                else:
                    await page.goto("https://app.fireworks.ai/login?useEmail=true")
                await asyncio.sleep(2)
                if await page.locator('input[name="email"]').first.count() > 0:
                    break
                logger.warning(f"Login form not visible (attempt {attempt+1})")
            except Exception as e:
                logger.warning(f"Login click failed (attempt {attempt+1}): {e}")
                await asyncio.sleep(2)
        steps.append("login_page")

        # Fill credentials
        await page.locator('input[name="email"]').first.fill(email)
        await page.locator('input[name="password"]').first.fill(password)
        steps.append("credentials_filled")

        # Submit
        for btn in await page.locator('button[type="submit"]').all():
            if 'Next' in (await btn.text_content() or ''):
                await btn.click()
                await asyncio.sleep(2)
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
                
                for name, target in [("Super", "First"), ("Cheetah", "Last")]:
                    el = _find_element(target, "AXTextField")
                    if el:
                        _cua_click(el); await asyncio.sleep(0.3)
                        _cua_type(name); await asyncio.sleep(0.3)
                
                el = _find_element("agree", "AXCheckBox")
                if el: _cua_click(el); await asyncio.sleep(0.3)
                
                el = _find_element("Continue")
                if el: _cua_click(el); await asyncio.sleep(2)

                for uc_text in ["Prototype", "Flexible", "Conversational", "Search"]:
                    el = _find_element(uc_text, "AXCheckBox")
                    if el:
                        _cua_click(el); await asyncio.sleep(0.2)
                
                el = _find_element("Submit")
                if el:
                    _cua_click(el)
                    for attempt in range(8):
                        await asyncio.sleep(2)
                        if any(x in page.url for x in ['home', 'account', 'settings']):
                            logger.info(f"Redirect detected (attempt {attempt+1})")
                            break
                    else:
                        logger.warning("CUA Submit — kein Redirect, force navigate check")
                        redirected = False
                        for url in [
                            "https://app.fireworks.ai/settings/users/api-keys",
                            "https://app.fireworks.ai/",
                        ]:
                            try:
                                fresh = await browser.contexts[0].new_page()
                                await fresh.goto(url, timeout=15000, wait_until='domcontentloaded')
                                await asyncio.sleep(2)
                                if any(x in fresh.url for x in ['home', 'account', 'settings', 'api-keys']):
                                    redirected = True
                                    await fresh.close()
                                    logger.info("CUA Submit — logged in (verified via fresh page)")
                                    break
                                await fresh.close()
                            except Exception:
                                pass
                        
                        if not redirected:
                            logger.warning("CUA Submit — force navigate failed, Playwright-Fallback")
                            try:
                                await _fireworks_playwright_onboarding(page)
                            except Exception as e:
                                logger.warning(f"Playwright-Fallback failed: {e}")
                else:
                    logger.warning("CUA Submit nicht gefunden — Playwright-Fallback")
                    try:
                        await _fireworks_playwright_onboarding(page)
                    except Exception as e:
                        logger.warning(f"Playwright-Fallback failed: {e}")
            else:
                logger.warning("CUA window not found — Playwright-Fallback")
                try:
                    await _fireworks_playwright_onboarding(page)
                except Exception as e:
                    logger.warning(f"Playwright-Fallback failed: {e}")
            steps.append("onboarding_complete")

        # Wait for redirect after onboarding (poll up to 15s)
        for attempt in range(8):
            await asyncio.sleep(2)
            try:
                if any(x in page.url for x in ['home', 'account', 'settings']):
                    logger.info(f"Redirect detected ({page.url[:60]})")
                    steps.append("login_success")
                    return {"status": "success", "steps_completed": steps}
            except Exception:
                logger.warning("Page URL check failed — page may be stale")
                break

        # Force navigate (page may be stale after CUA Submit)
        for url in [
            "https://app.fireworks.ai/settings/users/api-keys",
            "https://app.fireworks.ai/",
        ]:
            try:
                fresh = await browser.contexts[0].new_page()
                await fresh.goto(url, timeout=15000, wait_until='domcontentloaded')
                await asyncio.sleep(2)
                fresh_url = fresh.url
                if any(x in fresh_url for x in ['home', 'account', 'settings', 'api-keys']):
                    steps.append("login_success")
                    return {"status": "success", "steps_completed": steps}
                logger.warning(f"Fresh page landed on: {fresh_url[:60]}")
                await fresh.close()
            except Exception as e:
                logger.warning(f"Fresh page navigate failed: {e}")

        return {"status": "error", "steps_completed": steps, "error": f"Login failed: could not reach home/settings"}

    except Exception as e:
        logger.error(f"Fireworks login error: {e}")
        return {"status": "error", "steps_completed": steps, "error": str(e)}


async def _fireworks_playwright_onboarding(page) -> None:
    """Playwright-based onboarding fallback (type() with delay for React, click() for checkboxes)."""
    import asyncio
    
    fn = page.locator('input[name="firstName"]').first
    if await fn.count() == 0:
        fn = page.locator('input[name="first"]').first
    if await fn.count() > 0:
        await fn.click(); await asyncio.sleep(0.2)
        await fn.type("Super", delay=50); await asyncio.sleep(0.5)
    
    ln = page.locator('input[name="lastName"]').first
    if await ln.count() == 0:
        ln = page.locator('input[name="last"]').first
    if await ln.count() > 0:
        await ln.click(); await asyncio.sleep(0.2)
        await ln.type("Cheetah", delay=50); await asyncio.sleep(0.5)
    
    terms = None
    for cb in await page.locator('input[type="checkbox"]').all():
        lbl = (await cb.get_attribute('aria-label') or '').lower()
        n_id = (await cb.get_attribute('id') or '').lower()
        if 'terms' in lbl or 'agree' in lbl or 'terms' in n_id:
            terms = cb
            break
    if not terms:
        terms = page.locator('label:has-text("Terms")').first
    if await terms.count() > 0:
        await terms.click(force=True); await asyncio.sleep(0.5)
    
    for btn in await page.locator('button').all():
        txt = (await btn.text_content() or '').strip()
        if 'Continue' in txt or 'Next' in txt:
            await btn.click(force=True); await asyncio.sleep(2)
            break
    
    for uc in ["Prototype", "Flexible capacity", "Conversational", "Search"]:
        for inp in await page.locator('input[type="checkbox"]').all():
            i_id = (await inp.get_attribute('id') or '').lower()
            if 'cky' in i_id:
                continue
            label = await inp.get_attribute('aria-label') or ''
            if uc.lower() in label.lower():
                await inp.click(force=True); await asyncio.sleep(0.3)
                break
    
    for btn in await page.locator('button').all():
        txt = (await btn.text_content() or '').strip()
        if 'Submit' in txt or 'Get $5' in txt:
            await btn.click(force=True); await asyncio.sleep(4)
            break
    
    for _ in range(10):
        await asyncio.sleep(2)
        if any(x in page.url for x in ['home', 'account', 'settings']):
            logger.info("Playwright onboarding complete")
            return
    logger.warning("Playwright onboarding — kein Redirect, force navigate")
    try:
        await page.goto("https://app.fireworks.ai/settings/users/api-keys", timeout=15000, wait_until='domcontentloaded')
        await asyncio.sleep(2)
    except:
        try:
            await page.goto("https://app.fireworks.ai/settings/users/api-keys", timeout=20000)
            await asyncio.sleep(2)
        except:
            logger.error("Force navigate failed")


async def _generate_and_poll_key(pg, key_name: str) -> Dict[str, Any]:
    """Click Generate, poll for key, handle Missing Name modal, retry."""
    import asyncio
    import re as _re

    for retry in range(3):
        suffix = f"-{retry}" if retry > 0 else ""
        name = key_name + suffix

        # On retry > 0: reload page and re-open dialog
        if retry > 0:
            logger.warning(f"API Key retry {retry+1}/3 — reloading page")
            try:
                for _ in range(3):
                    await pg.goto("https://app.fireworks.ai/settings/users/api-keys",
                                  timeout=15000, wait_until='domcontentloaded')
                    await asyncio.sleep(4)
                    if 'login' not in pg.url.lower():
                        break
                    await asyncio.sleep(2)

                # Dismiss cookie banner
                try:
                    for _ in range(3):
                        for btn in await pg.locator('button').all():
                            txt = (await btn.text_content() or '').strip()
                            if txt in ('Accept All', 'Reject All'):
                                await btn.click(force=True); await asyncio.sleep(1)
                                break
                        else:
                            break
                except Exception:
                    pass

                # Re-open dialog
                for btn in await pg.locator('button').all():
                    if 'Create API Key' in (await btn.text_content() or ''):
                        await btn.click(force=True); await asyncio.sleep(2); break

                menu = pg.locator('[role="menuitem"]:has-text("API Key")').first
                for _ in range(5):
                    if await menu.count() > 0:
                        break
                    await asyncio.sleep(1)
                await menu.click(force=True)
                await asyncio.sleep(2)
            except Exception as e:
                logger.warning(f"Reload failed: {e}")
                continue

        # Ensure name is filled
        await pg.locator(f'input[name="name"]').first.click()
        await asyncio.sleep(0.2)
        await pg.locator(f'input[name="name"]').first.type(name, delay=40)
        await asyncio.sleep(1)

        # Wait for Generate to be enabled (max 10s)
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
            logger.warning(f"Generate button not found (retry {retry})")
            # Log page state for debugging
            try:
                url = pg.url[:60]
                btns = [(await b.text_content() or '').strip()[:30] for b in await pg.locator('button').all()]
                logger.warning(f"Page: {url} | Buttons: {btns[:10]}")
            except: pass
            continue

        logger.info(f"Generate clicked (retry {retry})")
        await generate_btn.click(force=True)

        # Poll for key (15s)
        for _ in range(15):
            await asyncio.sleep(1)
            text = await pg.evaluate("() => document.body.innerText")
            keys = _re.findall(r'fw_[a-zA-Z0-9]{20,}', text)
            if keys:
                return {"status": "success", "api_key": keys[0]}

        # Check for Missing Name modal
        body = await pg.evaluate("() => document.body.innerText")
        if 'Missing' in body and 'Name' in body:
            logger.warning(f"Missing Name Modal — close + retry ({retry+1}/3)")
            for btn in await pg.locator('button').all():
                txt = (await btn.text_content() or '').strip()
                if txt in ['Close', 'Cancel', 'OK', '×']:
                    await btn.click(force=True)
                    await asyncio.sleep(1)
                    break
            continue

        # Other error — abort
        break

    return {"status": "error", "error": "API Key not found after retry"}


async def create_api_key(key_name: str = "sinator-key", cdp_port: Optional[int] = None, page=None, browser=None) -> Dict[str, Any]:
    """Create Fireworks API Key via Playwright with auto-retry. Returns {status, api_key, error}
    If page provided, uses it (ONE Browser). Otherwise uses cdp_port or launches fresh."""
    import asyncio
    from playwright.async_api import async_playwright

    own_browser = False
    _p = None
    try:
        if page is not None:
            pass
        elif cdp_port:
            _p = await async_playwright().start()
            browser = await _p.chromium.connect_over_cdp(f"http://localhost:{cdp_port}")
            own_browser = True
            page = await browser.new_page()
        else:
            _p = await async_playwright().start()
            browser = await _p.chromium.launch(headless=False, args=_CHROMIUM_GPU_FLAGS)
            own_browser = True
            page = await browser.new_page()

        # Use a fresh page for API key gen, or reuse the ONE page
        pg = page if page is not None else await browser.new_page()
        await pg.goto("https://app.fireworks.ai/settings/users/api-keys", wait_until='domcontentloaded')
        await asyncio.sleep(2)

        # Retry navigate if redirected to login
        for _ in range(3):
            if 'login' in pg.url.lower():
                logger.warning(f"Redirected to login — retrying ({pg.url[:60]})")
                await pg.goto("https://app.fireworks.ai/settings/users/api-keys", wait_until='domcontentloaded')
                await asyncio.sleep(2)
            else:
                break

        if 'login' in pg.url.lower():
            logger.error("Cannot access API keys — still on login page")
            return {"status": "error", "error": "Not logged in"}

        logger.info(f"API Keys page loaded: {pg.url[:80]}")

        # Dismiss cookie banner before interacting with dialogs
        try:
            for _ in range(3):
                for btn in await pg.locator('button').all():
                    txt = (await btn.text_content() or '').strip()
                    if txt in ('Accept All', 'Reject All'):
                        await btn.click(force=True); await asyncio.sleep(1)
                        break
                else:
                    break
        except Exception:
            pass

        _page_btns = [(await b.text_content() or '').strip()[:40] for b in await pg.locator('button').all()]
        logger.info(f"Page buttons: {[b for b in _page_btns if b][:5]}")

        # Open Create API Key dialog
        _found_create = False
        for btn in await pg.locator('button').all():
            if 'Create API Key' in (await btn.text_content() or ''):
                await btn.click(force=True)
                await asyncio.sleep(2)
                logger.info("Create API Key clicked")
                _found_create = True
                break
        if not _found_create:
            logger.warning("Create API Key button not found — trying after 5s")
            await asyncio.sleep(5)
            for btn in await pg.locator('button').all():
                if 'Create API Key' in (await btn.text_content() or ''):
                    await btn.click(force=True)
                    await asyncio.sleep(2)
                    _found_create = True
                    break
        if not _found_create:
            logger.error("Create API Key button never found — navigating fresh")
            await pg.goto("https://app.fireworks.ai/settings/users/api-keys")
            await asyncio.sleep(5)
            for btn in await pg.locator('button').all():
                if 'Create API Key' in (await btn.text_content() or ''):
                    await btn.click(force=True); await asyncio.sleep(2); break

        # Verify menu appeared before clicking menuitem
        menu = pg.locator('[role="menuitem"]:has-text("API Key")').first
        for _ in range(5):
            if await menu.count() > 0:
                break
            await asyncio.sleep(1)
        if await menu.count() == 0:
            logger.warning("API Key menuitem not found — navigating to fresh page")
            await pg.goto("https://app.fireworks.ai/settings/users/api-keys")
            await asyncio.sleep(5)
            for btn in await pg.locator('button').all():
                if 'Create API Key' in (await btn.text_content() or ''):
                    await btn.click(force=True); await asyncio.sleep(2); break
            for _ in range(5):
                if await menu.count() > 0:
                    break
                await asyncio.sleep(1)
        await menu.click(force=True)
        await asyncio.sleep(2)

        # Verify dialog actually appeared (should have input + buttons)
        _dialog_ok = False
        for _ in range(5):
            _inp = pg.locator('input[name="name"]').first
            if await _inp.count() > 0:
                _dialog_ok = True
                break
            await asyncio.sleep(1)
        if not _dialog_ok:
            logger.warning("API Key dialog not visible — retrying from fresh page")
            await pg.goto("https://app.fireworks.ai/settings/users/api-keys")
            await asyncio.sleep(5)
            for btn in await pg.locator('button').all():
                if 'Create API Key' in (await btn.text_content() or ''):
                    await btn.click(force=True); await asyncio.sleep(2); break
            for _ in range(5):
                if await menu.count() > 0:
                    break
                await asyncio.sleep(1)
            await menu.click(force=True)
            await asyncio.sleep(2)

        return await _generate_and_poll_key(pg, key_name)

    except Exception as e:
        logger.error(f"API Key error: {e}")
        return {"status": "error", "error": str(e)}


async def verify_account(verify_url: str, cdp_port: Optional[int] = None, page=None, browser=None) -> bool:
    """Open Fireworks verify URL to confirm account. Returns True if confirmed.
    If page provided, uses it (ONE Browser). Otherwise uses cdp_port or launches fresh."""
    import asyncio
    from playwright.async_api import async_playwright
    
    own_browser = False
    own_page = False
    try:
        if page is not None:
            pass
        elif cdp_port:
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(f"http://localhost:{cdp_port}")
                own_browser = True
                page = await browser.new_page()
                own_page = True
        else:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False, args=_CHROMIUM_GPU_FLAGS)
                own_browser = True
                page = await browser.new_page()
                own_page = True
        
        await page.goto(verify_url)
        await asyncio.sleep(2)
        logger.info(f"Verify URL opened: {page.url[:80]}")
        if own_page:
            await page.close()
        return True
    except Exception as e:
        logger.error(f"Verify error: {e}")
        return False
