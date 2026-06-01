"""
SINATOR — Fireworks Service V8 (Issue #22 Fixes, 2026-06-01)

Fixes from Issue #22:
  - F5: browser.new_page() -> _get_new_page() helper for CDP compatibility
  - O1: login_fireworks() detects logged-in state and skips to onboarding
  - O2: wait_for_spa_transition("verify") -> wait_for_url_change("/signup")
  - O3: create_api_key() uses _get_new_page() helper

Docs: fireworks_service.doc.md
"""
import logging
import re
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


async def _get_new_page(browser):
    """F5/O3 FIX: Get new page from browser (CDP-compatible).
    
    browser.new_page() throws "Please use browser.new_context()" on CDP.
    """
    if browser.contexts:
        return await browser.contexts[0].new_page()
    else:
        return await browser.new_page()


async def signup_fireworks(email: str, password: str, cdp_port: Optional[int] = None,
                           browser: Optional[Any] = None,
                           existing_page: Optional[Any] = None) -> Dict[str, Any]:
    """Create new Fireworks account via signup form + OTP verification.
    
    V8 Fixes:
      - F5: Uses _get_new_page() for CDP compatibility
      - O2: Uses wait_for_url_change() instead of wait_for_spa_transition("verify")
    """
    import asyncio
    from playwright.async_api import async_playwright
    
    steps = []
    own_playwright = None
    _page = None
    try:
        if browser is None:
            p = await async_playwright().start()
            own_playwright = p
            if cdp_port:
                browser = await p.chromium.connect_over_cdp(f"http://localhost:{cdp_port}")
            else:
                browser = await p.chromium.launch(headless=False)
        
        # F5 FIX: Use helper for CDP compatibility
        _page = await _get_new_page(browser)
        page = _page
        
        # Step 1: Signup form
        await page.goto("https://app.fireworks.ai/signup")
        await asyncio.sleep(2)
        
        # CookieYes via JS API
        try:
            from agent_toolbox.core.browser_utils import accept_cookieyes_via_js
            await accept_cookieyes_via_js(page)
        except Exception as e:
            logger.warning(f"CookieYes JS failed, trying button: {e}")
            try:
                await page.locator('button:has-text("Accept All")').first.click(force=True, timeout=5000)
            except:
                pass
        await asyncio.sleep(2)
        steps.append("cookie_handled")
        
        # React-kompatibles Input-Filling
        try:
            from agent_toolbox.core.browser_utils import fill_react_input
            filled = await fill_react_input(page, 'input[name="email"], input[type="email"]', email)
            if not filled:
                email_inp = page.locator('input[name="email"]').first
                if await email_inp.count() == 0:
                    email_inp = page.locator('input[type="email"]').first
                await email_inp.fill(email)
        except Exception:
            email_inp = page.locator('input[name="email"]').first
            if await email_inp.count() == 0:
                email_inp = page.locator('input[type="email"]').first
            await email_inp.fill(email)
        steps.append("email_filled")
        await asyncio.sleep(1)
        
        # Next button
        for btn in await page.locator('button[type="submit"]').all():
            if 'Next' in (await btn.text_content() or ''):
                await btn.click(force=True)
                await asyncio.sleep(2)
                break
        steps.append("next_clicked")
        
        # Fill BOTH passwords
        pws = await page.locator('input[type="password"]').all()
        if len(pws) >= 2:
            for pw in pws[:2]:
                await pw.click()
                await asyncio.sleep(0.2)
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
            
            # O2 FIX: Wait for URL change instead of specific text "verify"
            try:
                from agent_toolbox.core.browser_utils import wait_for_url_change
                await wait_for_url_change(page, "/signup", timeout=15)
            except Exception:
                # Fallback: poll URL
                for _ in range(10):
                    await asyncio.sleep(1)
                    if '/signup' not in page.url:
                        break
            
            steps.append("create_clicked")
        
        logger.info("Signup complete — OTP reading delegated to rotate.py")
        return {
            "status": "signup_done",
            "steps_completed": steps,
        }
    except Exception as e:
        logger.error(f"Signup error: {e}")
        return {"status": "error", "steps_completed": steps, "error": str(e)}
    finally:
        if _page:
            try:
                await _page.close()
            except:
                pass
        if own_playwright:
            await own_playwright.stop()


async def login_fireworks(email: str, password: str, cdp_port: Optional[int] = None,
                          browser: Optional[Any] = None,
                          skip_if_logged_in: bool = True) -> Dict[str, Any]:
    """Login to Fireworks via Playwright + React-kompatibles Onboarding.
    
    V8 Fixes:
      - F5: Uses _get_new_page() for CDP compatibility
      - O1: Detects logged-in state and skips login form (post-verify flow)
    """
    import asyncio
    from playwright.async_api import async_playwright

    steps = []
    own_playwright = None
    _page = None
    try:
        if browser is None:
            p = await async_playwright().start()
            own_playwright = p
            if cdp_port:
                browser = await p.chromium.connect_over_cdp(f"http://localhost:{cdp_port}")
            else:
                browser = await p.chromium.launch(headless=False)
        
        # F5 FIX: Use helper for CDP compatibility
        _page = await _get_new_page(browser)
        page = _page

        await page.goto("https://app.fireworks.ai/login")
        await asyncio.sleep(2)

        # O1 FIX: Check if already logged in (post-verify redirect)
        current_url = page.url
        if skip_if_logged_in:
            # If redirected away from login, we're already authenticated
            if 'login' not in current_url.lower():
                logger.info(f"O1 FIX: Already logged in, URL: {current_url[:60]}")
                steps.append("already_logged_in")
                
                # Handle onboarding if present
                if 'onboarding' in current_url:
                    logger.info("Onboarding detected post-login redirect")
                    await _fireworks_react_onboarding(page)
                    steps.append("onboarding_complete")
                
                steps.append("login_success")
                return {"status": "success", "steps_completed": steps}

        # CookieYes via JS API
        try:
            from agent_toolbox.core.browser_utils import accept_cookieyes_via_js
            await accept_cookieyes_via_js(page)
        except Exception:
            try:
                await page.locator('button:has-text("Accept All")').first.click(force=True, timeout=5000)
            except:
                pass
        await asyncio.sleep(1)

        # O1 FIX: Check again after cookie handling (page may have redirected)
        current_url = page.url
        if skip_if_logged_in and 'login' not in current_url.lower():
            logger.info(f"O1 FIX: Logged in after cookie handling, URL: {current_url[:60]}")
            steps.append("already_logged_in")
            if 'onboarding' in current_url:
                await _fireworks_react_onboarding(page)
                steps.append("onboarding_complete")
            steps.append("login_success")
            return {"status": "success", "steps_completed": steps}

        # Email Login — retry wrapper
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
            except Exception as e:
                logger.warning(f"Login click failed (attempt {attempt+1}): {e}")
                await asyncio.sleep(2)
        steps.append("login_page")

        # Fill credentials
        email_input = page.locator('input[name="email"]').first
        if await email_input.count() == 0:
            # O1 FIX: No email input = already logged in
            logger.info("O1 FIX: No email input found, checking if logged in")
            current_url = page.url
            if any(x in current_url for x in ['home', 'account', 'settings', 'onboarding']):
                steps.append("already_logged_in")
                if 'onboarding' in current_url:
                    await _fireworks_react_onboarding(page)
                    steps.append("onboarding_complete")
                steps.append("login_success")
                return {"status": "success", "steps_completed": steps}
            return {"status": "error", "steps_completed": steps, "error": "No email input and not logged in"}
        
        await email_input.fill(email)
        await page.locator('input[name="password"]').first.fill(password)
        steps.append("credentials_filled")

        # Submit
        for btn in await page.locator('button[type="submit"]').all():
            if 'Next' in (await btn.text_content() or ''):
                await btn.click()
                await asyncio.sleep(2)
                break
        steps.append("form_submitted")

        # Onboarding via React-kompatiblem Playwright
        if 'onboarding' in page.url:
            logger.info("Onboarding via React-kompatiblem Playwright")
            await _fireworks_react_onboarding(page)
            steps.append("onboarding_complete")

        # Wait for redirect
        for attempt in range(8):
            await asyncio.sleep(2)
            try:
                if any(x in page.url for x in ['home', 'account', 'settings']) and 'login' not in page.url:
                    logger.info(f"Redirect detected ({page.url[:60]})")
                    steps.append("login_success")
                    return {"status": "success", "steps_completed": steps}
            except Exception:
                break

        # Force navigate
        for url in [
            "https://app.fireworks.ai/settings/users/api-keys",
            "https://app.fireworks.ai/",
        ]:
            try:
                # F5 FIX: Use helper
                fresh = await _get_new_page(browser)
                await fresh.goto(url, timeout=15000, wait_until='domcontentloaded')
                await asyncio.sleep(2)
                fresh_url = fresh.url
                if any(x in fresh_url for x in ['home', 'account', 'settings', 'api-keys']) and 'login' not in fresh_url:
                    steps.append("login_success")
                    return {"status": "success", "steps_completed": steps}
                await fresh.close()
            except Exception as e:
                logger.warning(f"Fresh page navigate failed: {e}")

        return {"status": "error", "steps_completed": steps, "error": "Login failed"}

    except Exception as e:
        logger.error(f"Fireworks login error: {e}")
        return {"status": "error", "steps_completed": steps, "error": str(e)}
    finally:
        if _page:
            try:
                await _page.close()
            except:
                pass
        if own_playwright:
            await own_playwright.stop()


async def _fireworks_react_onboarding(page) -> None:
    """React-kompatibles Onboarding mit CEO-Fixes."""
    import asyncio
    
    try:
        from agent_toolbox.core.browser_utils import (
            fill_react_input, click_react_checkbox, wait_for_spa_transition
        )
        use_ceo_utils = True
    except ImportError:
        use_ceo_utils = False
    
    # Fill names
    if use_ceo_utils:
        await fill_react_input(page, 'input[name="firstName"], input[name="first"]', "Super")
        await fill_react_input(page, 'input[name="lastName"], input[name="last"]', "Cheetah")
    else:
        fn = page.locator('input[name="firstName"]').first
        if await fn.count() == 0:
            fn = page.locator('input[name="first"]').first
        if await fn.count() > 0:
            await fn.click()
            await asyncio.sleep(0.2)
            await fn.type("Super", delay=50)
            await asyncio.sleep(0.5)
        
        ln = page.locator('input[name="lastName"]').first
        if await ln.count() == 0:
            ln = page.locator('input[name="last"]').first
        if await ln.count() > 0:
            await ln.click()
            await asyncio.sleep(0.2)
            await ln.type("Cheetah", delay=50)
            await asyncio.sleep(0.5)
    
    # Terms checkbox
    if use_ceo_utils:
        await click_react_checkbox(page, "agree")
        if not await click_react_checkbox(page, "terms"):
            logger.warning("Terms checkbox not found via CEO utils")
    else:
        await _legacy_click_checkbox(page, "agree")
        await _legacy_click_checkbox(page, "terms")
    
    await asyncio.sleep(0.5)
    
    # Continue button
    for btn in await page.locator('button').all():
        txt = (await btn.text_content() or '').strip()
        if 'Continue' in txt or 'Next' in txt:
            await btn.click(force=True)
            await asyncio.sleep(2)
            break
    
    # SPA-Transition warten
    if use_ceo_utils:
        await wait_for_spa_transition(page, "Prototype with open models", timeout=10)
    else:
        await asyncio.sleep(3)
    
    # Use-case checkboxes
    for uc in ["Prototype", "Flexible capacity", "Conversational", "Search"]:
        if use_ceo_utils:
            await click_react_checkbox(page, uc)
        else:
            await _legacy_click_checkbox(page, uc)
        await asyncio.sleep(0.2)
    
    # Submit button
    for btn in await page.locator('button').all():
        txt = (await btn.text_content() or '').strip()
        if 'Submit' in txt or 'Get $5' in txt:
            await btn.click(force=True)
            await asyncio.sleep(4)
            break
    
    # Wait for redirect
    for _ in range(10):
        await asyncio.sleep(2)
        if any(x in page.url for x in ['home', 'account', 'settings']) and 'login' not in page.url:
            logger.info("React onboarding complete")
            return
    
    logger.warning("React onboarding — kein Redirect, force navigate")
    try:
        await page.goto("https://app.fireworks.ai/settings/users/api-keys", timeout=15000, wait_until='domcontentloaded')
        await asyncio.sleep(2)
    except:
        logger.error("Force navigate failed")


async def _legacy_click_checkbox(page, match_text: str) -> bool:
    """Legacy checkbox click (fallback)."""
    for inp in await page.locator('input[type="checkbox"]').all():
        lbl = (await inp.get_attribute('aria-label') or '').lower()
        if match_text.lower() in lbl:
            await inp.click(force=True)
            return True
    for el in await page.locator('[role="checkbox"]').all():
        lbl = (await el.get_attribute('aria-label') or '').lower()
        if match_text.lower() in lbl:
            await el.click(force=True)
            return True
    lbl = page.locator(f'label:has-text("{match_text}")').first
    if await lbl.count() > 0:
        cb = lbl.locator('input[type="checkbox"], [role="checkbox"]').first
        if await cb.count() > 0:
            await cb.click(force=True)
            return True
        await lbl.click(force=True)
        return True
    return False


async def _generate_and_poll_key(pg, key_name: str) -> Dict[str, Any]:
    """Click Generate, poll for key, handle Missing Name modal, retry."""
    import asyncio
    import re as _re

    for retry in range(3):
        suffix = f"-{retry}" if retry > 0 else ""
        name = key_name + suffix

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
                    from agent_toolbox.core.browser_utils import accept_cookieyes_via_js
                    await accept_cookieyes_via_js(pg)
                except Exception:
                    for btn in await pg.locator('button').all():
                        txt = (await btn.text_content() or '').strip()
                        if txt in ('Accept All', 'Reject All'):
                            await btn.click(force=True)
                            await asyncio.sleep(1)
                            break

                # Re-open dialog
                for btn in await pg.locator('button').all():
                    if 'Create API Key' in (await btn.text_content() or ''):
                        await btn.click(force=True)
                        await asyncio.sleep(2)
                        break

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
        await pg.locator('input[name="name"]').first.click()
        await asyncio.sleep(0.2)
        await pg.locator('input[name="name"]').first.type(name, delay=40)
        await asyncio.sleep(1)

        # Wait for Generate to be enabled
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
            continue

        logger.info(f"Generate clicked (retry {retry})")
        await generate_btn.click(force=True)

        # Poll for key
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

        break

    return {"status": "error", "error": "API Key not found after retry"}


async def create_api_key(key_name: str = "sinator-key", cdp_port: Optional[int] = None,
                         browser: Optional[Any] = None) -> Dict[str, Any]:
    """Create Fireworks API Key via Playwright with auto-retry.
    
    O3 FIX: Uses _get_new_page() for CDP compatibility.
    """
    import asyncio
    from playwright.async_api import async_playwright

    own_playwright = None
    pg = None
    try:
        if browser is None:
            p = await async_playwright().start()
            own_playwright = p
            if cdp_port:
                browser = await p.chromium.connect_over_cdp(f"http://localhost:{cdp_port}")
            else:
                browser = await p.chromium.launch(headless=False)

        # O3 FIX: Use helper for CDP compatibility
        pg = await _get_new_page(browser)
        await pg.goto("https://app.fireworks.ai/settings/users/api-keys", wait_until='domcontentloaded')
        await asyncio.sleep(2)

        # Retry navigate if redirected to login
        for _ in range(3):
            if 'login' in pg.url.lower():
                await pg.goto("https://app.fireworks.ai/settings/users/api-keys", wait_until='domcontentloaded')
                await asyncio.sleep(2)
            else:
                break

        if 'login' in pg.url.lower():
            return {"status": "error", "error": "Not logged in"}

        # CookieYes via JS API
        try:
            from agent_toolbox.core.browser_utils import accept_cookieyes_via_js
            await accept_cookieyes_via_js(pg)
        except Exception:
            for btn in await pg.locator('button').all():
                txt = (await btn.text_content() or '').strip()
                if txt in ('Accept All', 'Reject All'):
                    await btn.click(force=True)
                    await asyncio.sleep(1)
                    break

        # Open Create API Key dialog
        for btn in await pg.locator('button').all():
            if 'Create API Key' in (await btn.text_content() or ''):
                await btn.click(force=True)
                await asyncio.sleep(2)
                break

        menu = pg.locator('[role="menuitem"]:has-text("API Key")').first
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
    finally:
        if pg:
            try:
                await pg.close()
            except:
                pass
        if own_playwright:
            await own_playwright.stop()


async def verify_account(verify_url: str, cdp_port: Optional[int] = None,
                         browser: Optional[Any] = None) -> bool:
    """Open Fireworks verify URL to confirm account.
    
    F5 FIX: Uses _get_new_page() for CDP compatibility.
    """
    import asyncio
    from playwright.async_api import async_playwright
    
    own_playwright = None
    _page = None
    try:
        if browser is None:
            p = await async_playwright().start()
            own_playwright = p
            if cdp_port:
                browser = await p.chromium.connect_over_cdp(f"http://localhost:{cdp_port}")
            else:
                browser = await p.chromium.launch(headless=False)
        
        # F5 FIX: Use helper for CDP compatibility
        _page = await _get_new_page(browser)
        await _page.goto(verify_url)
        await asyncio.sleep(2)
        logger.info(f"Verify URL opened: {_page.url[:80]}")
        return True
    except Exception as e:
        logger.error(f"Verify error: {e}")
        return False
    finally:
        if _page:
            try:
                await _page.close()
            except:
                pass
        if own_playwright:
            await own_playwright.stop()
