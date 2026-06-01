"""
SINATOR — Fireworks Service V19 (SIN-Browser-Tools based, 2026-06-01)

Full Fireworks flow using SIN-Browser-Tools:
  signup → OTP (via rotate.py) → verify → login+onboarding → API key

Bot Chrome (BrowserManager) bleibt GEÖFFNET bis API Key generiert.
"""
import asyncio
import logging
import re
import weakref
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class _BrowserHandle:
    """Duck-type wrapper that looks like BrowserManager to SIN-Browser-Tools."""
    def __init__(self, page, context, browser, pw):
        self._page = page
        self._context = context
        self._browser = browser
        self._playwright = pw
        self._started = True
        self._dialog_queue = asyncio.Queue()
        self._pending_dialog = None
        self._dialog_pages = weakref.WeakSet()
        self._registry_stub = None
        self._browser_pid = None

    @property
    def page(self):
        return self._page

    @property
    def context(self):
        return self._context

    async def cleanup(self):
        try:
            await self._context.close()
        except Exception:
            pass
        try:
            await self._browser.close()
        except Exception:
            pass
        try:
            await self._playwright.stop()
        except Exception:
            pass

    def set_active_page(self, p):
        self._page = p
        self._context = p.context

    async def new_page(self):
        return await self._context.new_page()

    @property
    def active_page(self):
        return self._page

    def clear_active_page(self):
        self._page = None

    async def get_next_dialog(self, timeout=5.0, consume=True):
        return None

    def _setup_dialog_handler(self):
        pass


async def launch() -> Dict[str, Any]:
    from playwright.async_api import async_playwright
    from sin_browser_tools.core.manager import manager

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--window-size=1200,800",
        ],
    )
    context = await browser.new_context(
        viewport={"width": 1200, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        locale="de-DE",
        timezone_id="Europe/Berlin",
        accept_downloads=True,
        bypass_csp=True,
        ignore_https_errors=True,
    )
    page = await context.new_page()

    # Stealth patches via add_init_script
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['de-DE', 'de', 'en-US', 'en'] });
        window.chrome = { runtime: {} };
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) =>
            parameters.name === 'notifications'
                ? Promise.resolve({ state: Notification.permission })
                : originalQuery(parameters);
    """)

    handle = _BrowserHandle(page, context, browser, pw)
    manager._set_instance(handle)
    logger.info("Bot Chrome launched (stays open until API key success)")
    return {"status": "launched", "browser_manager": handle}


async def cleanup_bot(browser_manager=None) -> None:
    """Cleanup Bot Chrome only if no API key was generated."""
    if browser_manager:
        try:
            from sin_browser_tools.core import manager
            await browser_manager.cleanup()
            manager._set_instance(None)
            logger.info("Bot Chrome cleaned up")
        except Exception as e:
            logger.warning(f"Bot Chrome cleanup error: {e}")


async def signup_fireworks(email: str, password: str, **kwargs) -> Dict[str, Any]:
    from sin_browser_tools.tools.navigation import browser_navigate
    from sin_browser_tools.tools.interaction import browser_click_by_text
    from agent_toolbox.core.browser_utils import (
        fill_react_input, wait_for_spa_transition,
    )

    steps = []

    await browser_navigate("https://app.fireworks.ai/signup")
    await asyncio.sleep(3)
    pg = __page()
    logger.info(f"Signup page loaded: {pg.url[:80]}")

    await pg.evaluate("""() => {
        document.querySelectorAll('.cky-overlay, .cky-consent-container, .cky-modal, .cky-preference-center')
            .forEach(el => el.remove());
        document.body.style.overflow = 'visible';
    }""")
    await asyncio.sleep(1)

    if not await fill_react_input(pg, 'input[name="email"]', email):
        logger.error("Email fill failed")
        return {"status": "error", "error": "email_fill_failed", "steps_completed": steps}
    steps.append("email_filled")
    await asyncio.sleep(1)

    await pg.evaluate("""() => {
        const next = Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === 'Next');
        if (next) next.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
    }""")
    logger.info("Next clicked via JS dispatchEvent")

    for _ in range(12):
        await asyncio.sleep(1)
        pws = await pg.locator('input[type="password"]').all()
        if len(pws) >= 2:
            break
        body = await pg.evaluate("() => document.body.innerText")
        if 'captcha' in body.lower() or 'verify you are human' in body.lower():
            logger.error("CAPTCHA detected")
            return {"status": "error", "error": "captcha", "steps_completed": steps}
    else:
        body = await pg.evaluate("() => document.body.innerText.substring(0, 1000)")
        logger.error(f"Password fields not found. Page text: {body[:300]}")
        return {"status": "error", "error": "no_password_fields", "steps_completed": steps}
    steps.append("next_clicked")

    pw_input = confirm_input = None
    for p in pws:
        name = (await p.get_attribute('name') or '')
        if name == 'password':
            pw_input = p
        elif name == 'confirmPassword':
            confirm_input = p

    for inp in [pw_input, confirm_input]:
        if inp:
            await inp.click()
            await asyncio.sleep(0.2)
            await inp.fill("")
            await inp.type(password, delay=40)
            await asyncio.sleep(0.3)
    steps.append("passwords_filled")

    await pg.evaluate("""() => {
        const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === 'Create Account');
        if (btn) btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
    }""")
    logger.info("Create Account clicked via JS dispatchEvent")

    if await wait_for_spa_transition(pg, "verify", timeout=25):
        logger.info("Verify page detected")
    else:
        pg = __page()
        if 'verify' in pg.url or 'confirm' in pg.url:
            logger.info(f"Verify URL: {pg.url[:60]}")
        else:
            text = await pg.evaluate("() => document.body.innerText")
            if 'verify' in text.lower() or 'check your email' in text.lower():
                logger.info("Verify text detected")
            else:
                logger.warning(f"No verify — URL: {pg.url[:60]}")
    steps.append("create_clicked")

    return {"status": "signup_done", "steps_completed": steps}


async def verify_account(verify_url: str, **kwargs) -> bool:
    from sin_browser_tools.tools.navigation import browser_navigate
    from agent_toolbox.core.browser_utils import wait_for_spa_transition

    try:
        await browser_navigate(verify_url)
        await asyncio.sleep(2)
        pg = __page()
        logger.info(f"Verify URL opened: {pg.url[:80]}")
        await wait_for_spa_transition(pg, "onboarding", timeout=10)
        return True
    except Exception as e:
        logger.error(f"Verify error: {e}")
        return False


async def login_fireworks(email: str, password: str, **kwargs) -> Dict[str, Any]:
    from sin_browser_tools.tools.navigation import browser_navigate
    from sin_browser_tools.tools.interaction import browser_click_by_text
    from agent_toolbox.core.browser_utils import (
        accept_cookieyes_via_js, fill_react_input, wait_for_spa_transition,
    )

    steps = []
    pg = __page()

    await browser_navigate("https://app.fireworks.ai/login")
    await asyncio.sleep(2)

    if not await accept_cookieyes_via_js(pg):
        try:
            for btn in await pg.locator('button').all():
                txt = (await btn.text_content() or '').strip()
                if txt in ('Accept All', 'Reject All'):
                    await btn.click(force=True)
                    break
            await asyncio.sleep(1)
        except:
            pass

    for attempt in range(3):
        try:
            em = pg.locator('a:has-text("Email Login")').first
            if await em.count() > 0:
                await em.click()
            else:
                await browser_navigate("https://app.fireworks.ai/login?useEmail=true")
            await asyncio.sleep(2)
            if await pg.locator('input[name="email"]').first.count() > 0:
                break
        except:
            await asyncio.sleep(2)
    steps.append("login_page")

    await fill_react_input(pg, 'input[name="email"]', email)
    await fill_react_input(pg, 'input[name="password"]', password)
    steps.append("credentials_filled")

    pg = __page()
    try:
        await browser_click_by_text("Next", role="button")
    except:
        for btn in await pg.locator('button[type="submit"]').all():
            if 'Next' in (await btn.text_content() or ''):
                await btn.click(force=True)
                break
    await asyncio.sleep(2)
    steps.append("form_submitted")

    if 'onboarding' in pg.url:
        logger.info("Onboarding via Playwright (no CUA)")
        await _playwright_onboarding(pg)
        steps.append("onboarding_complete")

    for _ in range(12):
        await asyncio.sleep(2)
        url = pg.url
        if any(x in url for x in ['home', 'account', 'settings', 'api-keys', 'models']):
            logger.info(f"Redirect detected: {url[:60]}")
            steps.append("login_success")
            return {"status": "success", "steps_completed": steps}

    for url in [
        "https://app.fireworks.ai/settings/users/api-keys",
        "https://app.fireworks.ai/",
    ]:
        try:
            await browser_navigate(url)
            await asyncio.sleep(2)
            if 'login' not in pg.url.lower():
                steps.append("login_success")
                return {"status": "success", "steps_completed": steps}
        except:
            pass

    return {"status": "error", "steps_completed": steps, "error": "could not reach home/settings"}


async def _playwright_onboarding(page) -> None:
    from agent_toolbox.core.browser_utils import (
        fill_react_input, click_react_checkbox, wait_for_spa_transition,
    )

    fn = page.locator('input[name="firstName"]').first
    if await fn.count() == 0:
        fn = page.locator('input[name="first"]').first
    if await fn.count() > 0:
        await fill_react_input(page, 'input[name="firstName"], input[name="first"]', "Super")
        await asyncio.sleep(0.5)

    ln = page.locator('input[name="lastName"]').first
    if await ln.count() == 0:
        ln = page.locator('input[name="last"]').first
    if await ln.count() > 0:
        await fill_react_input(page, 'input[name="lastName"], input[name="last"]', "Cheetah")
        await asyncio.sleep(0.5)

    if not await click_react_checkbox(page, "Terms"):
        for cb in await page.locator('input[type="checkbox"]').all():
            lbl = (await cb.get_attribute('aria-label') or '').lower()
            n_id = (await cb.get_attribute('id') or '').lower()
            if 'terms' in lbl or 'agree' in lbl or 'terms' in n_id:
                await cb.click(force=True)
                await asyncio.sleep(0.5)
                break

    for btn in await page.locator('button').all():
        txt = (await btn.text_content() or '').strip()
        if 'Continue' in txt or 'Next' in txt:
            await btn.click(force=True)
            await asyncio.sleep(2)
            break

    for uc in ["Prototype", "Flexible capacity", "Conversational", "Search"]:
        await click_react_checkbox(page, uc)
        await asyncio.sleep(0.3)

    for btn in await page.locator('button').all():
        txt = (await btn.text_content() or '').strip()
        if 'Submit' in txt or 'Get $5' in txt:
            await btn.click(force=True)
            await asyncio.sleep(4)
            break

    if await wait_for_spa_transition(page, "home", timeout=15):
        logger.info("Playwright onboarding complete")
        return
    if await wait_for_spa_transition(page, "account", timeout=15):
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

    from agent_toolbox.core.browser_utils import fill_react_input

    for retry in range(3):
        suffix = f"-{retry}" if retry > 0 else ""
        name = key_name + suffix

        inp = pg.locator('input[name="name"]').first
        if await inp.count() > 0:
            await inp.click()
            await asyncio.sleep(0.2)
        await fill_react_input(pg, 'input[name="name"]', name)
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
        from sin_browser_tools.core import manager
        return manager.page


__page = _PageAccessor()
