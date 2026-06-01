"""Fireworks AI E2E flow — signup, verify, login, onboarding, API key.

Uses 100% SIN-Browser-Tools (zero raw page.evaluate calls).
Bot Chrome stays open until API key is generated.

Docs: fireworks_service.doc.md
"""
import asyncio
import logging
import re
import weakref
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


# ── Browser Handle ──────────────────────────────────────────────────────────

class _BrowserHandle:
    """Duck-type wrapper satisfying SIN-Browser-Tools manager._set_instance().

    SIN-Browser-Tools expects a BrowserManager with _page, _context, _browser,
    _playwright attributes. This class provides those from a raw Playwright
    launch, bypassing BrowserManager which hardcodes --start-maximized.
    """

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
        """Active Playwright page — used by SIN-Browser-Tools for all operations."""
        return self._page

    @property
    def context(self):
        """Browser context — holds cookies, storage, and page references."""
        return self._context

    async def cleanup(self):
        """Close context, browser, and Playwright instance. Idempotent."""
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
        """Update active page reference (called by SIN-Browser-Tools on tab switch)."""
        self._page = p
        self._context = p.context

    async def new_page(self):
        """Create a new page in the browser context."""
        return await self._context.new_page()

    @property
    def active_page(self):
        """Alias for page — backward compatibility with BrowserManager API."""
        return self._page

    def clear_active_page(self):
        """Set active page to None (used during cleanup)."""
        self._page = None

    async def get_next_dialog(self, timeout=5.0, consume=True):
        """No-op — dialogs are not handled in Bot Chrome."""
        return None

    def _setup_dialog_handler(self):
        """No-op — dialog handler not needed for Fireworks flow."""
        pass


# ── Launch / Cleanup ────────────────────────────────────────────────────────

async def launch() -> Dict[str, Any]:
    """Launch Bot Chrome with stealth patches and register with SIN-Browser-Tools.

    Creates an ephemeral Chromium instance with:
    - Window size 1200x800 (not maximized — avoids layout detection)
    - German locale/timezone (matches GMX account region)
    - Anti-detection: webdriver, plugins, languages, chrome.runtime

    Returns:
        Dict with 'browser_manager' (_BrowserHandle) for caller to cleanup.
    """
    from playwright.async_api import async_playwright
    from sin_browser_tools.core.manager import manager

    pw = await async_playwright().start()
    # Window size 1200x800 — NOT --start-maximized (which BrowserManager hardcodes)
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
    """Close Bot Chrome and deregister from SIN-Browser-Tools.

    Called after API key is generated (success) or on rotation failure.
    Safe to call multiple times — all close() calls are idempotent.
    """
    if browser_manager:
        try:
            from sin_browser_tools.core import manager
            await browser_manager.cleanup()
            manager._set_instance(None)
            logger.info("Bot Chrome cleaned up")
        except Exception as e:
            logger.warning(f"Bot Chrome cleanup error: {e}")


# ── Signup ──────────────────────────────────────────────────────────────────

async def signup_fireworks(email: str, password: str, **kwargs) -> Dict[str, Any]:
    """Create a new Fireworks account with the given email and password.

    Flow: navigate → remove CookieYes → fill email → Next → fill passwords → Create Account.
    Detects CAPTCHA and missing password fields as errors.

    Args:
        email: GMX alias email (e.g., pulse-runner-931@gmx.de)
        password: Fireworks account password

    Returns:
        Dict with 'status' ('signup_done'|'error') and 'steps_completed' list.
    """
    from sin_browser_tools.tools.navigation import browser_navigate, browser_get_url
    from sin_browser_tools.tools.interaction import browser_click_by_text, browser_fill
    from sin_browser_tools.tools.extraction import browser_console
    from sin_browser_tools.tools.vision import browser_get_text

    steps = []

    await browser_navigate("https://app.fireworks.ai/signup")
    await asyncio.sleep(3)
    logger.info(f"Signup page loaded")

    await browser_console("""document.querySelectorAll('.cky-overlay, .cky-consent-container, .cky-modal, .cky-preference-center').forEach(el => el.remove()); document.body.style.overflow = 'visible';""")
    await asyncio.sleep(1)

    r = await browser_fill('input[name="email"]', email)
    if r.get("status") != "typed":
        logger.error("Email fill failed")
        return {"status": "error", "error": "email_fill_failed", "steps_completed": steps}
    steps.append("email_filled")
    await asyncio.sleep(1)

    # Enter key — avoids carousel "Next slide" button conflict
    from sin_browser_tools.tools.navigation import browser_press
    await browser_press("Enter")
    logger.info("Email submitted via Enter key")

    for _ in range(12):
        await asyncio.sleep(1)
        pw_count = int((await browser_console("document.querySelectorAll('input[type=password]').length"))["result"])
        if pw_count >= 2:
            break
        body = (await browser_get_text("body")).get("text", "")
        if 'captcha' in body.lower() or 'verify you are human' in body.lower():
            logger.error("CAPTCHA detected")
            return {"status": "error", "error": "captcha", "steps_completed": steps}
    else:
        body = (await browser_get_text("body")).get("text", "")
        logger.error(f"Password fields not found. Page text: {body[:300]}")
        return {"status": "error", "error": "no_password_fields", "steps_completed": steps}
    steps.append("next_clicked")

    await browser_fill('input[name="password"]', password)
    await browser_fill('input[name="confirmPassword"]', password)
    steps.append("passwords_filled")

    await browser_click_by_text("Create Account", role="button")
    logger.info("Create Account clicked via browser_click_by_text")

    for _ in range(25):
        await asyncio.sleep(1)
        url = (await browser_get_url())["url"]
        if 'verify' in url.lower() or 'confirm' in url.lower():
            logger.info(f"Verify page detected: {url[:60]}")
            break
        body = (await browser_get_text("body")).get("text", "")
        if 'verify' in body.lower() or 'check your email' in body.lower():
            logger.info("Verify text detected")
            break
    else:
        logger.warning(f"No verify detected after signup")
    steps.append("create_clicked")

    return {"status": "signup_done", "steps_completed": steps}


# ── Verify ──────────────────────────────────────────────────────────────────

async def verify_account(verify_url: str, **kwargs) -> bool:
    """Open the Fireworks verification URL to confirm the email address.

    Navigates to the URL (which contains the OTP token) and waits for
    redirect to onboarding/home. The URL is typically extracted from
    the GMX inbox by rotate.py.

    Args:
        verify_url: Full verification URL from Fireworks email

    Returns:
        True if verification succeeded (redirect detected or page loaded).
    """
    from sin_browser_tools.tools.navigation import browser_navigate, browser_get_url

    try:
        await browser_navigate(verify_url)
        await asyncio.sleep(2)
        url = (await browser_get_url())["url"]
        logger.info(f"Verify URL opened: {url[:80]}")
        for _ in range(10):
            await asyncio.sleep(1)
            url = (await browser_get_url())["url"]
            if 'onboarding' in url.lower() or 'home' in url.lower() or 'account' in url.lower():
                return True
        return True
    except Exception as e:
        logger.error(f"Verify error: {e}")
        return False


# ── Login ───────────────────────────────────────────────────────────────────

async def login_fireworks(email: str, password: str, **kwargs) -> Dict[str, Any]:
    """Log in to Fireworks AI and handle onboarding if redirected.

    Two-step login:
    1. Fill email → click Next (triggers email validation)
    2. Fill password → Enter key (submits form)

    After login, detects redirect:
    - /onboarding → runs _playwright_onboarding() then waits for home redirect
    - /home|/account|/settings → login success

    Uses Enter key instead of browser_click_by_text("Next") for password submit
    to avoid matching the carousel "Next slide" button (disabled, causes timeout).

    Args:
        email: GMX alias email
        password: Fireworks account password

    Returns:
        Dict with 'status' ('success'|'error') and 'steps_completed' list.
    """
    from sin_browser_tools.tools.navigation import browser_navigate, browser_get_url
    from sin_browser_tools.tools.interaction import browser_click_by_text, browser_fill
    from sin_browser_tools.tools.extraction import browser_console
    from sin_browser_tools.tools.vision import browser_get_text

    steps = []

    await browser_navigate("https://app.fireworks.ai/login")
    await asyncio.sleep(2)

    await browser_console("""document.querySelectorAll('.cky-overlay,.cky-consent-container,.cky-modal,[class*="cky-"]').forEach(e => e.remove()); document.body.style.overflow = 'visible';""")
    await asyncio.sleep(1)

    for attempt in range(3):
        try:
            r = await browser_click_by_text("Email Login", role="link")
            if r.get("status") == "clicked":
                break
        except Exception:
            pass
        try:
            await browser_navigate("https://app.fireworks.ai/login?useEmail=true")
        except Exception:
            pass
        await asyncio.sleep(2)
        email_count = int((await browser_console("document.querySelectorAll('input[name=email]').length"))["result"])
        if email_count > 0:
            break
    steps.append("login_page")

    await browser_fill('input[name="email"]', email)
    steps.append("email_filled")

    try:
        await browser_click_by_text("Next", role="button")
    except Exception:
        for txt in ("Next", "Continue", "Submit"):
            try:
                await browser_click_by_text(txt, role="button")
                break
            except Exception:
                continue
    await asyncio.sleep(2)

    pw_count = int((await browser_console("document.querySelectorAll('input[type=password]').length"))["result"])
    if pw_count > 0:
        await browser_fill('input[type="password"]', password)
        steps.append("password_filled")
    else:
        await browser_fill('input[name="password"]', password)
        steps.append("password_filled")

    from sin_browser_tools.tools.navigation import browser_press
    await browser_press("Enter")
    await asyncio.sleep(2)
    steps.append("form_submitted")

    for _ in range(15):
        await asyncio.sleep(2)
        url = (await browser_get_url())["url"]
        if 'login' not in url.lower():
            if 'onboarding' in url:
                logger.info("Onboarding detected, running workflow")
                await _playwright_onboarding()
                steps.append("onboarding_complete")
                await asyncio.sleep(3)
                break
            if any(x in url for x in ['home', 'account', 'settings', 'api-keys', 'models']):
                logger.info(f"Login redirect detected: {url[:60]}")
                steps.append("login_success")
                return {"status": "success", "steps_completed": steps}

    for _ in range(10):
        await asyncio.sleep(2)
        url = (await browser_get_url())["url"]
        if 'login' not in url.lower():
            if any(x in url for x in ['home', 'account', 'settings', 'api-keys', 'models']):
                logger.info(f"Final redirect: {url[:60]}")
                steps.append("login_success")
                return {"status": "success", "steps_completed": steps}

    for u in [
        "https://app.fireworks.ai/settings/users/api-keys",
        "https://app.fireworks.ai/",
    ]:
        try:
            await browser_navigate(u)
            await asyncio.sleep(2)
            url = (await browser_get_url())["url"]
            if 'login' not in url.lower():
                steps.append("login_success")
                return {"status": "success", "steps_completed": steps}
        except Exception:
            pass

    return {"status": "error", "steps_completed": steps, "error": "could not reach home/settings"}


# ── Onboarding ──────────────────────────────────────────────────────────────

async def _playwright_onboarding() -> None:
    """Complete the Fireworks onboarding form (2 pages).

    Page 1: Account ID (max 20 chars), First/Last Name, Terms checkbox → Continue
    Page 2: Use case checkboxes (Prototype, Flexible, Conversational, Search, Agentic) → Submit

    Uses native React value setter for controlled inputs (browser_fill doesn't
    clear existing React state for CSS selectors). Account ID is 'sin' + 8
    random chars = 11 chars (under 20-char limit).

    After submit, waits up to 15s for redirect to /home or /account.
    Falls back to force-navigate to API keys page if no redirect detected.
    """
    from sin_browser_tools.tools.interaction import (
        browser_fill, browser_click_by_text, browser_click_checkbox_by_text,
    )
    from sin_browser_tools.tools.navigation import browser_get_url, browser_navigate
    from sin_browser_tools.tools.extraction import browser_console

    await browser_console("""document.querySelectorAll('.cky-overlay,.cky-consent-container,.cky-modal,[class*="cky-"]').forEach(e => e.remove()); document.body.style.overflow = 'visible';""")
    await asyncio.sleep(1)

    has_aid = int((await browser_console("document.querySelectorAll('input[name=accountId]').length"))["result"])
    if has_aid > 0:
        import random, string
        aid = "sin" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        await browser_console(f"""(() => {{
            var inp = document.querySelector('input[name="accountId"]');
            var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            setter.call(inp, '{aid}');
            inp.dispatchEvent(new Event('input', {{bubbles: true}}));
            inp.dispatchEvent(new Event('change', {{bubbles: true}}));
        }})()""")
        await asyncio.sleep(0.3)

    has_fn = int((await browser_console("document.querySelectorAll('input[name=firstName]').length || document.querySelectorAll('input[name=first]').length"))["result"])
    if has_fn > 0:
        await browser_console("""(() => {
            var inp = document.querySelector('input[name="firstName"]') || document.querySelector('input[name="first"]');
            var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            setter.call(inp, 'Super');
            inp.dispatchEvent(new Event('input', {bubbles: true}));
            inp.dispatchEvent(new Event('change', {bubbles: true}));
        })()""")
        await asyncio.sleep(0.3)

    has_ln = int((await browser_console("document.querySelectorAll('input[name=lastName]').length || document.querySelectorAll('input[name=last]').length"))["result"])
    if has_ln > 0:
        await browser_console("""(() => {
            var inp = document.querySelector('input[name="lastName"]') || document.querySelector('input[name="last"]');
            var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            setter.call(inp, 'Cheetah');
            inp.dispatchEvent(new Event('input', {bubbles: true}));
            inp.dispatchEvent(new Event('change', {bubbles: true}));
        })()""")
        await asyncio.sleep(0.3)

    tc = await browser_click_checkbox_by_text("Terms of Service")
    if not tc.get("success"):
        tc2 = await browser_click_checkbox_by_text("I agree")
        if not tc2.get("success"):
            await browser_console("""var b=document.querySelectorAll('button'); for(var i=0;i<b.length;i++){var r=b[i].getAttribute('role')||'';var a=b[i].getAttribute('aria-checked');if(r==='checkbox'||a!==null){b[i].click();return;}}""")
            await asyncio.sleep(0.5)

    await browser_click_by_text("Continue", role="button")
    await asyncio.sleep(3)

    for uc in [
        "Prototype with open models",
        "Flexible capacity for experimentation",
        "Conversational AI",
        "Search",
        "Agentic AI",
    ]:
        r = await browser_click_checkbox_by_text(uc)
        if not r.get("success"):
            try:
                await browser_click_by_text(uc, role="checkbox")
            except Exception:
                pass
            await asyncio.sleep(0.2)
        await asyncio.sleep(0.2)

    try:
        await browser_click_by_text("Submit", role="button")
    except Exception:
        for txt in ("Get $5", "Finish", "Continue"):
            try:
                await browser_click_by_text(txt, role="button")
                break
            except Exception:
                continue
    await asyncio.sleep(4)

    for _ in range(15):
        await asyncio.sleep(1)
        url = (await browser_get_url())["url"]
        if any(x in url for x in ['home', 'account', 'settings', 'api-keys', 'models']):
            logger.info(f"Onboarding redirect: {url[:60]}")
            return
    else:
        logger.warning("Playwright onboarding — kein Redirect, force navigate")
        try:
            await browser_navigate("https://app.fireworks.ai/settings/users/api-keys")
            await asyncio.sleep(2)
        except Exception:
            pass


# ── API Key ─────────────────────────────────────────────────────────────────

async def create_api_key(key_name: str = "sinator-key", **kwargs) -> Dict[str, Any]:
    """Generate a Fireworks API key via the web UI.

    Navigates to /settings/users/api-keys, clicks "Create API Key" → "API Key"
    menuitem, fills the key name, clicks Generate, then polls for the fw_ key
    pattern in page text (up to 15s).

    Bot Chrome stays open — caller must call cleanup_bot() after this.

    Args:
        key_name: Name for the API key (e.g., alias prefix like "pulse")

    Returns:
        Dict with 'status' ('success'|'error') and 'api_key' (fw_...) on success.
    """
    from sin_browser_tools.tools.navigation import browser_navigate, browser_get_url
    from sin_browser_tools.tools.interaction import browser_click_by_text, browser_fill
    from sin_browser_tools.tools.extraction import browser_console
    from sin_browser_tools.tools.vision import browser_get_text

    await browser_navigate("https://app.fireworks.ai/settings/users/api-keys")
    await asyncio.sleep(3)

    for _ in range(3):
        url = (await browser_get_url())["url"]
        if 'login' in url.lower():
            logger.warning(f"Redirected to login — retrying ({url[:60]})")
            await browser_navigate("https://app.fireworks.ai/settings/users/api-keys")
            await asyncio.sleep(3)
        else:
            break

    url = (await browser_get_url())["url"]
    if 'login' in url.lower():
        logger.error("Cannot access API keys — still on login page")
        return {"status": "error", "error": "Not logged in"}

    logger.info(f"API Keys page loaded: {url[:80]}")

    await browser_console("""document.querySelectorAll('.cky-overlay,.cky-consent-container,.cky-modal,[class*="cky-"]').forEach(e => e.remove()); document.body.style.overflow = 'visible';""")
    await asyncio.sleep(1)

    for attempt_try in range(3):
        try:
            await browser_click_by_text("Create API Key", role="button")
            await asyncio.sleep(2)
        except Exception:
            if attempt_try < 2:
                logger.warning("Create API Key button not found — retry")
                await browser_navigate("https://app.fireworks.ai/settings/users/api-keys")
                await asyncio.sleep(3)
                continue

        try:
            await browser_click_by_text("API Key", role="menuitem")
            await asyncio.sleep(2)
        except Exception:
            pass

        inp_count = int((await browser_console("document.querySelectorAll('input[name=name]').length"))["result"])
        if inp_count > 0:
            break
    else:
        logger.error("API Key dialog never appeared")
        return {"status": "error", "error": "Dialog not found"}

    for retry in range(3):
        suffix = f"-{retry}" if retry > 0 else ""
        name = key_name + suffix

        await browser_fill('input[name="name"]', name)
        await asyncio.sleep(1)

        try:
            await browser_click_by_text("Generate", role="button")
        except Exception:
            for kw in ("Generate API Key", "Generate", "Create"):
                try:
                    await browser_click_by_text(kw, role="button")
                    break
                except Exception:
                    continue

        for _ in range(15):
            await asyncio.sleep(1)
            text = (await browser_get_text("body")).get("text", "")
            keys = re.findall(r'fw_[a-zA-Z0-9]{20,}', text)
            if keys:
                return {"status": "success", "api_key": keys[0]}

        text = (await browser_get_text("body")).get("text", "")
        if 'Missing' in text and 'Name' in text:
            for kw in ('Close', 'Cancel', 'OK'):
                try:
                    await browser_click_by_text(kw, role="button")
                    await asyncio.sleep(1)
                    break
                except Exception:
                    continue
            continue
        break

    return {"status": "error", "error": "API Key not found after retry"}


