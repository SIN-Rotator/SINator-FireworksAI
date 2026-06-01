"""
SINATOR — Fireworks Service V19 (SIN-Browser-Tools based, 2026-06-01)

Full Fireworks flow using SIN-Browser-Tools:
  signup → OTP (via rotate.py) → verify → login+onboarding → API key

Bot Chrome (BrowserManager) bleibt GEÖFFNET bis API Key generiert.
"""
import asyncio
import logging
import re
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


async def launch() -> Dict[str, Any]:
    """Start Bot Chrome via SIN-Browser-Tools BrowserManager.

    Bot Chrome bleibt GEÖFFNET bis zur erfolgreichen API-Key-Generierung.
    Der Aufrufer MUSS cleanup_bot() am Ende aufrufen.
    """
    from sin_browser_tools.core.manager import BrowserManager, manager
    from sin_browser_tools.tools.navigation import browser_navigate
    from sin_browser_tools.tools.interaction import (
        browser_type, browser_click, browser_fill,
        browser_click_by_text, browser_snapshot,
    )

    fw_mgr = BrowserManager(headless=False, stealth=True)
    await fw_mgr.start_local()
    manager._set_instance(fw_mgr)
    logger.info("Bot Chrome launched (stays open until API key success)")
    return {"status": "launched", "browser_manager": fw_mgr}


async def cleanup_bot(browser_manager=None) -> None:
    """Cleanup Bot Chrome only if no API key was generated."""
    if browser_manager:
        try:
            from sin_browser_tools.core import manager as mgr
            await browser_manager.cleanup()
            mgr.manager._set_instance(None)
            logger.info("Bot Chrome cleaned up")
        except Exception as e:
            logger.warning(f"Bot Chrome cleanup error: {e}")


async def signup_fireworks(email: str, password: str, **kwargs) -> Dict[str, Any]:
    """Create new Fireworks account via signup form.
    Returns {status, steps_completed} — OTP reading delegated to rotate.py.
    """
    from sin_browser_tools.tools.navigation import browser_navigate
    from sin_browser_tools.tools.interaction import (
        browser_type, browser_click, browser_fill,
        browser_click_by_text, browser_wait_for_text,
    )
    from sin_browser_tools.tools.interaction import browser_click_checkbox_by_text

    steps = []

    # /signup
    await browser_navigate("https://app.fireworks.ai/signup")
    await asyncio.sleep(3)

    # Cookie banner
    try:
        await browser_click_by_text("Accept All", role="button")
        await asyncio.sleep(2)
    except:
        pass

    # Email
    await browser_fill("input[name='email']", email)
    steps.append("email_filled")
    await asyncio.sleep(1)

    # Next
    try:
        await browser_click_by_text("Next", role="button")
    except:
        for btn in await __page().locator('button[type="submit"]').all():
            if 'Next' in (await btn.text_content() or ''):
                await btn.click(force=True)
                break
    await asyncio.sleep(2)
    steps.append("next_clicked")

    # Passwords (React — type with delay)
    pws = await __page().locator('input[type="password"]').all()
    if len(pws) >= 2:
        for pw in pws[:2]:
            await pw.click()
            await asyncio.sleep(0.2)
            await pw.fill("")
            await pw.type(password, delay=40)
            await asyncio.sleep(0.3)
        await asyncio.sleep(1)
        steps.append("passwords_filled")

        # Create Account
        try:
            await browser_click_by_text("Create Account", role="button")
        except:
            for btn in await __page().locator('button[type="submit"]').all():
                if 'Create Account' in (await btn.text_content() or ''):
                    await btn.click(force=True)
                    break
        logger.info("Create Account clicked")

        # Wait for page to advance
        for _ in range(15):
            await asyncio.sleep(1)
            url = __page().url
            if '/signup' not in url or 'verify' in url:
                logger.info(f"Page advanced to: {url[:60]}")
                break
        steps.append("create_clicked")

    logger.info("Signup complete — OTP reading delegated to rotate.py")
    return {"status": "signup_done", "steps_completed": steps}


async def verify_account(verify_url: str, **kwargs) -> bool:
    """Open Fireworks verify URL to confirm account."""
    from sin_browser_tools.tools.navigation import browser_navigate

    try:
        await browser_navigate(verify_url)
        await asyncio.sleep(3)
        logger.info(f"Verify URL opened: {__page().url[:80]}")
        return True
    except Exception as e:
        logger.error(f"Verify error: {e}")
        return False


async def login_fireworks(email: str, password: str, **kwargs) -> Dict[str, Any]:
    """Login to Fireworks + handle onboarding (Playwright-native, kein CUA).

    Bot Chrome Seite bleibt erhalten — keine neue Page.
    Onboarding wird via Playwright-Locators gemacht (checkbox click, type, etc.).
    """
    from sin_browser_tools.tools.navigation import browser_navigate
    from sin_browser_tools.tools.interaction import (
        browser_type, browser_fill, browser_click_by_text,
    )

    steps = []

    # Login page
    await browser_navigate("https://app.fireworks.ai/login")
    await asyncio.sleep(2)

    # Cookie
    try:
        await browser_click_by_text("Accept All", role="button")
        await asyncio.sleep(1)
    except:
        pass

    # Email Login link
    for attempt in range(3):
        try:
            em = __page().locator('a:has-text("Email Login")').first
            if await em.count() > 0:
                await em.click()
            else:
                await browser_navigate("https://app.fireworks.ai/login?useEmail=true")
            await asyncio.sleep(2)
            if await __page().locator('input[name="email"]').first.count() > 0:
                break
        except:
            await asyncio.sleep(2)
    steps.append("login_page")

    # Fill credentials
    await __page().locator('input[name="email"]').first.fill(email)
    await __page().locator('input[name="password"]').first.fill(password)
    steps.append("credentials_filled")

    # Submit
    try:
        await browser_click_by_text("Next", role="button")
    except:
        for btn in await __page().locator('button[type="submit"]').all():
            if 'Next' in (await btn.text_content() or ''):
                await btn.click(force=True)
                break
    await asyncio.sleep(2)
    steps.append("form_submitted")

    # Onboarding
    if 'onboarding' in __page().url:
        logger.info("Onboarding via Playwright (no CUA)")
        await _playwright_onboarding(__page())
        steps.append("onboarding_complete")

    # Wait for redirect after login
    for _ in range(12):
        await asyncio.sleep(2)
        url = __page().url
        if any(x in url for x in ['home', 'account', 'settings', 'api-keys', 'models']):
            logger.info(f"Redirect detected: {url[:60]}")
            steps.append("login_success")
            return {"status": "success", "steps_completed": steps}

    # Force navigate to check login state
    for url in [
        "https://app.fireworks.ai/settings/users/api-keys",
        "https://app.fireworks.ai/",
    ]:
        try:
            await browser_navigate(url)
            await asyncio.sleep(2)
            if 'login' not in __page().url.lower():
                steps.append("login_success")
                return {"status": "success", "steps_completed": steps}
        except:
            pass

    return {"status": "error", "steps_completed": steps, "error": "could not reach home/settings"}


async def _playwright_onboarding(page) -> None:
    """Playwright-native onboarding — fill names, terms, use-cases, submit."""
    from sin_browser_tools.tools.interaction import browser_click_checkbox_by_text

    # First Name
    fn = page.locator('input[name="firstName"]').first
    if await fn.count() == 0:
        fn = page.locator('input[name="first"]').first
    if await fn.count() > 0:
        await fn.click()
        await asyncio.sleep(0.2)
        await fn.type("Super", delay=50)
        await asyncio.sleep(0.5)

    # Last Name
    ln = page.locator('input[name="lastName"]').first
    if await ln.count() == 0:
        ln = page.locator('input[name="last"]').first
    if await ln.count() > 0:
        await ln.click()
        await asyncio.sleep(0.2)
        await ln.type("Cheetah", delay=50)
        await asyncio.sleep(0.5)

    # Terms
    for cb in await page.locator('input[type="checkbox"]').all():
        lbl = (await cb.get_attribute('aria-label') or '').lower()
        n_id = (await cb.get_attribute('id') or '').lower()
        if 'terms' in lbl or 'agree' in lbl or 'terms' in n_id:
            await cb.click(force=True)
            await asyncio.sleep(0.5)
            break
    else:
        terms = page.locator('label:has-text("Terms")').first
        if await terms.count() > 0:
            await terms.click(force=True)
            await asyncio.sleep(0.5)

    # Continue
    for btn in await page.locator('button').all():
        txt = (await btn.text_content() or '').strip()
        if 'Continue' in txt or 'Next' in txt:
            await btn.click(force=True)
            await asyncio.sleep(2)
            break

    # Use-cases
    for uc in ["Prototype", "Flexible capacity", "Conversational", "Search"]:
        for inp in await page.locator('input[type="checkbox"]').all():
            i_id = (await inp.get_attribute('id') or '').lower()
            if 'cky' in i_id:
                continue
            label = await inp.get_attribute('aria-label') or ''
            if uc.lower() in label.lower():
                await inp.click(force=True)
                await asyncio.sleep(0.3)
                break

    # Submit
    for btn in await page.locator('button').all():
        txt = (await btn.text_content() or '').strip()
        if 'Submit' in txt or 'Get $5' in txt:
            await btn.click(force=True)
            await asyncio.sleep(4)
            break

    # Wait for redirect
    for _ in range(10):
        await asyncio.sleep(2)
        if any(x in page.url for x in ['home', 'account', 'settings', 'models']):
            logger.info("Playwright onboarding complete")
            return

    logger.warning("Playwright onboarding — kein Redirect, force navigate")
    try:
        await page.goto("https://app.fireworks.ai/settings/users/api-keys",
                        timeout=20000, wait_until='domcontentloaded')
        await asyncio.sleep(2)
    except:
        pass


async def create_api_key(key_name: str = "sinator-key", **kwargs) -> Dict[str, Any]:
    """Create Fireworks API Key via Playwright with auto-retry.
    Bot Chrome bleibt GEÖFFNET — kein close() bis Erfolg.
    """
    from sin_browser_tools.tools.navigation import browser_navigate

    pg = __page()

    # Navigate to API keys page
    await browser_navigate("https://app.fireworks.ai/settings/users/api-keys")
    await asyncio.sleep(3)

    # Retry if redirected to login
    for _ in range(3):
        if 'login' in pg.url.lower():
            logger.warning(f"Redirected to login — retrying ({pg.url[:60]})")
            await browser_navigate("https://app.fireworks.ai/settings/users/api-keys")
            await asyncio.sleep(3)
        else:
            break

    if 'login' in pg.url.lower():
        logger.error("Cannot access API keys — still on login page")
        return {"status": "error", "error": "Not logged in"}

    logger.info(f"API Keys page loaded: {pg.url[:80]}")

    # Cookie banner
    try:
        for btn in await pg.locator('button').all():
            txt = (await btn.text_content() or '').strip()
            if txt in ('Accept All', 'Reject All'):
                await btn.click(force=True)
                await asyncio.sleep(1)
                break
    except:
        pass

    # Open Create API Key dialog
    for attempt_try in range(3):
        # Click Create API Key button
        btn_texts = []
        for btn in await pg.locator('button').all():
            txt = (await btn.text_content() or '').strip()
            btn_texts.append(txt)
            if 'Create API Key' in txt:
                await btn.click(force=True)
                await asyncio.sleep(2)
                break
        else:
            if attempt_try < 2:
                logger.warning("Create API Key button not found — retry")
                await asyncio.sleep(3)
                await browser_navigate("https://app.fireworks.ai/settings/users/api-keys")
                await asyncio.sleep(3)
                continue

        # Click API Key menuitem
        menu = pg.locator('[role="menuitem"]:has-text("API Key")').first
        for _ in range(5):
            if await menu.count() > 0:
                break
            await asyncio.sleep(1)
        if await menu.count() > 0:
            await menu.click(force=True)
            await asyncio.sleep(2)

        # Check dialog appeared
        inp = pg.locator('input[name="name"]').first
        for _ in range(5):
            if await inp.count() > 0:
                break
            await asyncio.sleep(1)
        if await inp.count() > 0:
            break
    else:
        logger.error("API Key dialog never appeared")
        return {"status": "error", "error": "Dialog not found"}

    # Generate key
    for retry in range(3):
        suffix = f"-{retry}" if retry > 0 else ""
        name = key_name + suffix

        # Fill name
        inp = pg.locator('input[name="name"]').first
        await inp.click()
        await asyncio.sleep(0.2)
        await inp.fill("")
        await inp.type(name, delay=40)
        await asyncio.sleep(1)

        # Wait for Generate to be enabled
        generate_btn = None
        for _ in range(10):
            for btn in await pg.locator('button').all():
                txt = (await btn.text_content() or '').strip()
                if 'Generate' in txt and not await btn.is_disabled():
                    generate_btn = btn
                    break
            if generate_btn:
                break
            await asyncio.sleep(1)

        if not generate_btn:
            logger.warning(f"Generate button not found (retry {retry})")
            continue

        await generate_btn.click(force=True)

        # Poll for key
        for _ in range(15):
            await asyncio.sleep(1)
            text = await pg.evaluate("() => document.body.innerText")
            keys = re.findall(r'fw_[a-zA-Z0-9]{20,}', text)
            if keys:
                return {"status": "success", "api_key": keys[0]}

        # Missing Name modal
        body = await pg.evaluate("() => document.body.innerText")
        if 'Missing' in body and 'Name' in body:
            for btn in await pg.locator('button').all():
                txt = (await btn.text_content() or '').strip()
                if txt in ['Close', 'Cancel', 'OK', '\u00d7']:
                    await btn.click(force=True)
                    await asyncio.sleep(1)
                    break
            continue

        break

    return {"status": "error", "error": "API Key not found after retry"}


class _PageAccessor:
    """Holt die aktive Page vom SIN-Browser-Tools Manager."""
    _instance = None

    def __call__(self):
        from sin_browser_tools.core import manager as mgr
        return mgr.manager.page


__page = _PageAccessor()
