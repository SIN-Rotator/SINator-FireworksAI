"""
SINATOR AGENT-TOOLBOX — GMX Service (Playwright-native v2026-05-28)

Kernfunktionen:
  - GMX Session-Management
  - Alias-Rotation (Löschen + Erstellen)
  - OTP/Confirm-URL Extraktion

Playwright-native für Alias-Rotation. OTP bleibt auf CDP (komplex, funktioniert).
"""
import time
import random
import logging
import re
import asyncio
import json
import html as html_module
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
import httpx

from playwright.async_api import async_playwright, Browser, Page, BrowserContext, Frame

from agent_toolbox.core.cdp_client import (
    CDPClient,
    OopifContext,
    get_browser_ws_endpoint,
    get_page_target,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setLevel(logging.DEBUG)
    _formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    _handler.setFormatter(_formatter)
    logger.addHandler(_handler)

GMX_HOME_URL = "https://www.gmx.net/"


class GmxService:
    def __init__(self):
        self._email: Optional[str] = None
        self._password: Optional[str] = None
        self.adjectives = [
            "elron", "dark", "swift", "iron", "silver", "golden", "crystal", "shadow",
            "storm", "frost", "blaze", "thunder", "cosmic", "neon", "cyber", "quantum",
            "alpha", "beta", "delta", "omega", "zenith", "nexus", "vortex", "pulse",
            "echo", "phantom", "spectra", "turbo", "hyper", "ultra", "mega", "super",
        ]
        self.nouns = [
            "vader", "runner", "hawk", "wolf", "fox", "tiger", "eagle", "shark",
            "dragon", "phoenix", "falcon", "panther", "cobra", "lynx", "raven", "jaguar",
            "bear", "lion", "whale", "dolphin", "puma", "cheetah", "otter", "badger",
            "wolverine", "raptor", "condor", "viper", "scorpion", "spider", "mantis", "beetle",
        ]

    def generate_alias_name(self) -> str:
        adj = random.choice(self.adjectives)
        noun = random.choice(self.nouns)
        num = random.randint(100, 999)
        return f"{adj}-{noun}-{num}"

    # ── Playwright Connection ────────────────────────────────────────────

    async def _pw_connect(self, cdp_port: int = 9222, page: Optional[Page] = None) -> Page:
        """ONE Browser: requires page. No fallback connect/new_page."""
        if page is None:
            raise ValueError("_pw_connect: page required (ONE Browser mode)")
        logger.debug("[_pw_connect] Using shared page")
        return page

    async def _login(self, page: Page, email: str, password: str) -> bool:
        """Login to GMX via Playwright. Two-step flow: Email → Weiter → Password → Login."""
        logger.info(f"[_login] Logging in to GMX as {email}")
        try:
            await page.goto("https://www.gmx.net/", wait_until="domcontentloaded")
            await asyncio.sleep(5)  # Wait for JS redirect
            
            url = page.url
            
            # Handle cookie consent if present
            if "consent" in url:
                logger.info("Cookie consent page detected, accepting")
                try:
                    # Click "Alle akzeptieren" or "Zustimmen" or similar
                    for selector in ['button:has-text("Alle akzeptieren")', 'button:has-text("Zustimmen")',
                                    'button:has-text("Akzeptieren")', 'button:has-text("OK")',
                                    'button[data-testid="uc-accept-all-button"]']:
                        btn = page.locator(selector).first
                        if await btn.is_visible(timeout=2000):
                            await btn.click()
                            logger.info(f"Clicked consent: {selector}")
                            await asyncio.sleep(3)
                            break
                except Exception as e:
                    logger.warning(f"Consent handling failed: {e}")
                url = page.url
                logger.info(f"After consent: {url[:80]}")
                # After consent, we're on consent-management page — navigate to real www.gmx.net
                if "consent" in url:
                    logger.info("Navigating to www.gmx.net after consent")
                    await page.goto("https://www.gmx.net/", wait_until="domcontentloaded")
                    await asyncio.sleep(3)
                    url = page.url
                    logger.info(f"After consent redirect: {url[:80]}")
                url = page.url
                logger.info(f"After consent: {url[:80]}")
            
            # Already logged in on www.gmx.net homepage with Zum Postfach?
            text = await page.evaluate("() => document.body.innerText")
            if "Sie sind eingeloggt" in text or "Zum Postfach" in text:
                logger.info("Detected logged-in state on homepage, clicking Zum Postfach")
                try:
                    postfach_link = page.locator('text=Zum Postfach').first
                    if await postfach_link.is_visible(timeout=3000):
                        await postfach_link.click()
                        await asyncio.sleep(5)
                        logger.info(f"Postfach URL: {page.url[:80]}")
                        if "navigator.gmx.net/mail?sid=" in page.url:
                            return True
                        if "navigator.gmx.net" in page.url:
                            # Might be bap redirect — extract SID
                            return True
                except Exception as e:
                    logger.warning(f"Zum Postfach click failed: {e}")
                
                # Try direct navigation to inbox
                logger.info("Trying direct navigator.gmx.net/mail")
                await page.goto("https://navigator.gmx.net/mail", wait_until="domcontentloaded")
                await asyncio.sleep(5)
                if "navigator.gmx.net/mail?sid=" in page.url:
                    return True
                if "navigator.gmx.net" in page.url:
                    return True
                
                logger.error("Could not establish GMX session from logged-in homepage")
                return False
            
            # On auth.gmx.net login page — step 1: fill email, click Weiter
            if "auth.gmx.net" in url or "login.gmx.net" in url:
                logger.info("Step 1: Filling email on auth.gmx.net")
                # The email input has name=username, id=email
                email_input = page.locator('input[id="email"], input[name="username"]').first
                if await email_input.is_visible(timeout=5000):
                    await email_input.fill(email)
                    logger.info("Email filled")
                
                # Click Weiter button
                await asyncio.sleep(0.5)
                weiter_btn = page.locator('button:has-text("Weiter")').first
                if await weiter_btn.is_visible(timeout=3000):
                    await weiter_btn.click()
                    logger.info("Clicked Weiter")
                    await asyncio.sleep(4)
                else:
                    # Fallback: find any button with "Weiter"
                    btns = await page.query_selector_all('button')
                    for b in btns:
                        t = (await b.text_content() or '').strip()
                        if 'Weiter' in t:
                            await b.click()
                            logger.info(f"Clicked button: {t}")
                            await asyncio.sleep(4)
                            break
                
                # Step 2: fill password, click Login
                url = page.url
                logger.info(f"After Weiter, URL: {url[:80]}")
                password_input = page.locator('input[type="password"]').first
                if await password_input.is_visible(timeout=5000):
                    await password_input.fill(password)
                    logger.info("Password filled")
                
                await asyncio.sleep(0.5)
                login_btn = page.locator('button:has-text("Login")').first
                if await login_btn.is_visible(timeout=3000):
                    await login_btn.click()
                    logger.info("Clicked Login")
                    await asyncio.sleep(5)
                else:
                    btns = await page.query_selector_all('button')
                    for b in btns:
                        t = (await b.text_content() or '').strip()
                        if 'Login' == t:
                            await b.click()
                            logger.info("Clicked Login button")
                            await asyncio.sleep(5)
                            break
                
                # Check result
                url = page.url
                logger.info(f"After login, URL: {url[:80]}")
                if "navigator.gmx.net/mail?sid=" in url:
                    logger.info("Login successful, got SID")
                    return True
                if "navigator.gmx.net" in url:
                    # Might be on bap, try extracting SID
                    return True
                
                logger.error("Login failed — unexpected URL after login")
                return False
            
            # Fallback: click Login button on homepage first
            logger.info("Homepage without login form — clicking Login button")
            try:
                login_btn = page.locator('button:has-text("Login")').first
                if await login_btn.is_visible(timeout=3000):
                    await login_btn.click()
                    logger.info("Clicked Login button on homepage")
                    await asyncio.sleep(5)
                    url = page.url
                    logger.info(f"After login click: {url[:80]}")
                    
                    # Now we should be on auth.gmx.net — proceed with two-step
                    if "auth.gmx.net" in url or "login.gmx.net" in url:
                        logger.info("On login page after clicking Login")
                        # Fill email (step 1)
                        email_input = page.locator('input[id="email"], input[name="username"]').first
                        if await email_input.is_visible(timeout=5000):
                            await email_input.fill(email)
                            logger.info("Email filled")
                        
                        await asyncio.sleep(0.5)
                        weiter_btn = page.locator('button:has-text("Weiter")').first
                        if await weiter_btn.is_visible(timeout=3000):
                            await weiter_btn.click()
                            logger.info("Clicked Weiter")
                            await asyncio.sleep(4)
                        
                        # Step 2: password
                        password_input = page.locator('input[type="password"]').first
                        if await password_input.is_visible(timeout=5000):
                            await password_input.fill(password)
                            logger.info("Password filled")
                        
                        await asyncio.sleep(0.5)
                        login_btn = page.locator('button:has-text("Login")').first
                        if await login_btn.is_visible(timeout=3000):
                            await login_btn.click()
                            logger.info("Clicked Login")
                            await asyncio.sleep(5)
                        
                        url = page.url
                        logger.info(f"After login: {url[:80]}")
                        if "navigator.gmx.net/mail?sid=" in url:
                            return True
                        if "navigator.gmx.net" in url:
                            return True
                else:
                    logger.warning("Login button not found on homepage")
            except Exception as e:
                logger.warning(f"Homepage login flow failed: {e}")
            
            # Legacy fallback
            logger.info("Trying legacy login flow")
            email_input = page.locator('input[name="email"]').first
            if await email_input.is_visible(timeout=5000):
                await email_input.fill(email)
            password_input = page.locator('input[type="password"]').first
            if await password_input.is_visible(timeout=5000):
                await password_input.fill(password)
            submit_btn = page.locator('button[type="submit"]').first
            if await submit_btn.is_visible(timeout=3000):
                await submit_btn.click()
            await asyncio.sleep(5)
            
            url = page.url
            logger.info(f"Legacy login result URL: {url[:80]}")
            return "navigator.gmx.net" in url
            
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False
    # ── Navigation ─────────────────────────────────────────────────────

    async def _navigate_to_all_email_addresses(self, page: Page) -> bool:
        """Navigate to GMX allEmailAddresses via direct 3c.gmx.net jump (v3 approach).
        
        Instead of navigating through the GMX shell (which keeps content in
        cross-origin iframes that break after any action), we use:
          1. Get SID from current session (or login)
          2. Navigate to navigator.gmx.net/navigator/jump/to/mail_settings?sid={sid}
             → redirects to 3c.gmx.net/mail/client/settings/signature/ (TOP FRAME!)
          3. JS dispatchEvent click on "E-Mail-Adressen"
             → navigates to allEmailAddresses (TOP FRAME!)
        
        This keeps all content in the top frame — no iframe fragility.
        """
        url = page.url
        
        # Already on allEmailAddresses in top frame?
        if "allEmailAddresses" in url and "settings" in url:
            logger.info("Already on allEmailAddresses (top frame)")
            return True
        
        # Step 0: Get SID — from current URL, other tabs, or login
        sid = None
        sid_match = re.search(r'[?&]sid=([a-f0-9]{50,})', url)
        if sid_match:
            sid = sid_match.group(1)
        
        if not sid:
            for ctx in page.context.browser.contexts:
                for pg in ctx.pages:
                    m = re.search(r'[?&]sid=([a-f0-9]{50,})', pg.url)
                    if m and "gmx.net" in pg.url:
                        sid = m.group(1)
                        logger.info(f"Got SID from other tab: {pg.url[:60]}")
                        break
                if sid:
                    break
        
        if not sid:
            logger.info("No SID found, logging in")
            if not self._email or not self._password:
                logger.error("No GMX credentials set — set gmx._email and gmx._password before calling rotate_alias")
                return False
            if not await self._login(page, self._email, self._password):
                return False
            sid_match = re.search(r'[?&]sid=([a-f0-9]{50,})', page.url)
            sid = sid_match.group(1) if sid_match else None
        
        if not sid:
            logger.error("Could not establish GMX session")
            return False
        
        logger.info(f"Got SID: {sid[:20]}...")
        
        # Step 1: Navigate to jump URL → redirects to 3c.gmx.net (top frame!)
        jump_url = f"https://navigator.gmx.net/navigator/jump/to/mail_settings?sid={sid}"
        logger.info(f"STEP 1: Navigating to jump URL")
        await page.goto(jump_url, wait_until="domcontentloaded")
        await asyncio.sleep(6)
        
        url = page.url
        logger.info(f"After jump: {url[:100]}")
        
        if "allEmailAddresses" in url:
            logger.info("Redirected directly to allEmailAddresses (top frame)")
            return True
        
        # Step 2: On settings/signature → click "E-Mail-Adressen"
        if "settings" in url and "3c.gmx.net" in url:
            logger.info("STEP 2: On 3c.gmx.net settings — clicking E-Mail-Adressen via JS")
            try:
                result = await page.evaluate("""(function() {
                    var allEls = document.querySelectorAll('a, span, li, div, p');
                    for (var i = 0; i < allEls.length; i++) {
                        var el = allEls[i];
                        if (el.children.length === 0 && el.textContent.trim() === 'E-Mail-Adressen') {
                            var rect = el.getBoundingClientRect();
                            var cx = rect.x + rect.width / 2;
                            var cy = rect.y + rect.height / 2;
                            ['mousedown', 'mouseup', 'click'].forEach(function(evtType) {
                                el.dispatchEvent(new MouseEvent(evtType, {
                                    bubbles: true, cancelable: true, view: window,
                                    clientX: cx, clientY: cy
                                }));
                            });
                            return {clicked: true};
                        }
                    }
                    return {clicked: false};
                })()""")
                if result.get("clicked"):
                    logger.info("E-Mail-Adressen clicked via JS dispatchEvent")
                    await asyncio.sleep(4)
                else:
                    logger.warning("E-Mail-Adressen element not found on settings page")
            except Exception as e:
                logger.warning(f"E-Mail-Adressen JS click failed: {e}")
        
        # Step 3: Verify we're on allEmailAddresses
        url = page.url
        logger.info(f"Final URL: {url[:100]}")
        if "allEmailAddresses" in url and "settings" in url:
            logger.info("Successfully navigated to allEmailAddresses (top frame)")
            return True
        
        # Fallback: poll for allEmailAddresses frame
        logger.info("STEP 3: Polling for allEmailAddresses")
        for poll in range(15):
            if "allEmailAddresses" in page.url and "settings" in page.url:
                return True
            await asyncio.sleep(1)
        
        logger.error("allEmailAddresses not found")
        return False

    # ── Alias Deletion ──────────────────────────────────────────────────

    async def _get_all_email_frame(self, page: Page) -> Optional[Frame]:
        """Find the allEmailAddresses iframe, or return main_frame if in top frame."""
        # If page itself is on allEmailAddresses (jump approach), use main frame
        if "allEmailAddresses" in page.url and "settings" in page.url:
            return page.main_frame
        # Fallback: search frames
        for frame in page.frames:
            if "allEmailAddresses" in frame.url and "settings" in frame.url and "iac/restart" not in frame.url:
                return frame
        return None

    async def _find_alias_row(self, page: Page) -> Optional[str]:
        """Find a non-opensin alias email in the allEmailAddresses iframe."""
        logger.info("[_find_alias_row] Searching for alias")
        try:
            frame = await self._get_all_email_frame(page)
            if not frame:
                logger.warning("allEmailAddresses iframe not found")
                return None
            
            text = await frame.evaluate("() => document.body.innerText")
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if '@gmx.' in line and 'nemotronv3@gmx.de' not in line and 'opensin@gmx.de' not in line:
                    parts = line.split()
                    for part in parts:
                        if '@gmx.' in part and part != 'nemotronv3@gmx.de' and part != 'opensin@gmx.de':
                            logger.info(f"Found alias: {part}")
                            return part
        except Exception as e:
            logger.warning(f"Error finding alias: {e}")
        return None

    async def _delete_alias(self, page: Page, alias_email: str) -> bool:
        """Delete an alias by hovering over its row and clicking the hidden delete icon.

        Wicket GMX UI: das Delete-Icon (a.table-hover_icon[title*="löschen"]) ist
        erst nach Hover über die Row sichtbar (display:none → sichtbar via :hover CSS).
        Playwright-Native `page.mouse.move()` triggert :hover zuverlässig, CDP
        `Input.dispatchMouseEvent` NICHT.

        Portiert aus v19.3-gmx-delete-fixed (siehe tag v19.3-gmx-delete-fixed-working
        im SINator-Fireworks-Rotator-v2 Repo).
        """
        logger.info(f"[_delete_alias] Deleting {alias_email}")
        try:
            frame = await self._get_all_email_frame(page)
            if not frame:
                logger.warning("allEmailAddresses iframe not found for delete")
                return False

            # 1) Spezifischste Row finden — GMX nutzt <div class="table_body-row table_row">
            row_data = await frame.evaluate(f"""() => {{
                var candidates = document.querySelectorAll('tr, li, [class*="row"], [class*="Row"]');
                var best = null;
                var bestArea = Infinity;
                for (var i=0; i<candidates.length; i++) {{
                    var el = candidates[i];
                    if (!(el.textContent || '').includes('{alias_email}')) continue;
                    var r = el.getBoundingClientRect();
                    if (r.width < 50 || r.height < 5) continue;
                    var area = r.width * r.height;
                    if (area < bestArea) {{
                        bestArea = area;
                        best = el;
                    }}
                }}
                if (best) {{
                    var r = best.getBoundingClientRect();
                    return {{
                        cx: Math.round(r.x + r.width/2),
                        cy: Math.round(r.y + r.height/2)
                    }};
                }}
                return null;
            }}""")
            if not row_data:
                logger.warning(f"Alias row not found: {alias_email}")
                return False

            # 2) Hover via Playwright native mouse — triggert Wicket :hover CSS korrekt.
            #    Erst (0,0) → Target für sauberen Hover-Reset, dann 3x retry.
            delete_pos = None
            for _ in range(3):
                await page.mouse.move(0, 0)
                await asyncio.sleep(0.3)
                await page.mouse.move(row_data['cx'], row_data['cy'])
                await asyncio.sleep(0.8)
                delete_pos = await frame.evaluate("""() => {
                    for (const el of document.querySelectorAll('a.table-hover_icon[title*="lösch"], a.table-hover_icon[title*="Löschen"]')) {
                        const r = el.getBoundingClientRect();
                        if (r.width > 5 && r.height > 5) {
                            return {x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2),
                                    title: el.getAttribute('title') || ''};
                        }
                    }
                    return null;
                }""")
                if delete_pos:
                    break
            if not delete_pos:
                logger.warning("Delete icon not found via .table-hover_icon selector — retrying with broader search")
                delete_pos = await frame.evaluate("""() => {
                    for (const el of document.querySelectorAll('a')) {
                        const t = (el.getAttribute('title') || '').toLowerCase();
                        const a = (el.getAttribute('aria-label') || '').toLowerCase();
                        if (t.includes('lösch') || a.includes('lösch')) {
                            const r = el.getBoundingClientRect();
                            if (r.width > 5 && r.height > 5) {
                                return {x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2),
                                        title: el.getAttribute('title') || ''};
                            }
                        }
                    }
                    return null;
                }""")
                if not delete_pos:
                    logger.warning("Delete icon not found globally either")
                    return False

            logger.info(f"Delete '{delete_pos.get('title', '')}' at ({delete_pos['x']}, {delete_pos['y']})")

            # 3) Klicken via Playwright native mouse
            await page.mouse.move(delete_pos['x'], delete_pos['y'])
            await asyncio.sleep(0.2)
            await page.mouse.click(delete_pos['x'], delete_pos['y'])
            await asyncio.sleep(3)

            # 4) Confirm-Dialog (OK)
            ok_pos = await frame.evaluate("""() => {
                for (const el of document.querySelectorAll('button, a, span')) {
                    if (el.textContent && el.textContent.trim() === 'OK') {
                        const r = el.getBoundingClientRect();
                        if (r.width > 5 && r.height > 5) {
                            return {x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)};
                        }
                    }
                }
                return null;
            }""")
            if ok_pos:
                logger.info(f"OK confirm at ({ok_pos['x']}, {ok_pos['y']})")
                await page.mouse.move(ok_pos['x'], ok_pos['y'])
                await asyncio.sleep(0.2)
                await page.mouse.click(ok_pos['x'], ok_pos['y'])
                await asyncio.sleep(2)

            # 5) Verifikation
            for _ in range(10):
                text = await frame.evaluate("() => document.body.innerText")
                if alias_email not in text:
                    logger.info("Alias deleted successfully")
                    return True
                await asyncio.sleep(1)

            logger.warning("Alias still present after delete attempt")
            return False
        except Exception as e:
            logger.error(f"Error deleting alias: {e}")
            return False

    # ── Alias Creation ──────────────────────────────────────────────────

    async def _fill_alias_input(self, page: Page, alias_name: str) -> bool:
        """Fill the alias input field in the allEmailAddresses iframe."""
        logger.info(f"[_fill_alias_input] Filling with {alias_name}")
        try:
            frame = await self._get_all_email_frame(page)
            if not frame:
                logger.warning("allEmailAddresses iframe not found")
                return False
            
            # Try input[name*="localPart"]
            inp = frame.locator('input[name*="localPart"]').first
            if not await inp.is_visible(timeout=3000):
                # Try any text input
                inp = frame.locator('input[type="text"]').first

            if await inp.is_visible(timeout=3000):
                await inp.fill(alias_name)
                # Trigger events for React
                await inp.evaluate("el => el.dispatchEvent(new Event('input', {bubbles: true, composed: true}))")
                await inp.evaluate("el => el.dispatchEvent(new Event('change', {bubbles: true}))")
                value = await inp.input_value()
                if value == alias_name:
                    logger.info("Alias input filled successfully")
                    return True
            logger.warning("Alias input not found")
            return False
        except Exception as e:
            logger.error(f"Error filling alias input: {e}")
            return False

    async def _click_add_button(self, page: Page) -> bool:
        """Click the add alias button. Playwright native click for real browser events."""
        logger.info("[_click_add_button] Looking for add button")
        try:
            frame = await self._get_all_email_frame(page)
            if not frame:
                logger.warning("allEmailAddresses frame not found")
                return False

            # Playwright native click (triggers real browser events, works with Wicket)
            btn = frame.locator('button:has-text("Hinzufügen")').first
            for _ in range(5):
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click(force=True)
                    logger.info("Hinzufügen clicked via Playwright")
                    await asyncio.sleep(3)
                    return True
                await asyncio.sleep(1)

            logger.warning("Hinzufügen button not found via Playwright locator")
            return False
        except Exception as e:
            logger.error(f"Error clicking add button: {e}")
            return False

    async def _verify_alias(self, page: Page, alias_email: str, present: bool = True, max_wait: float = 15.0) -> bool:
        """Verify alias is present/absent in the allEmailAddresses page."""
        logger.info(f"[_verify_alias] Checking {alias_email} present={present}")
        reloaded = False
        try:
            deadline = time.time() + max_wait
            while time.time() < deadline:
                # Check page URL first (top frame approach)
                if "allEmailAddresses" in page.url and "settings" in page.url:
                    text = await page.evaluate("() => document.body.innerText")
                    found = alias_email in text
                    if present and found:
                        return True
                    if not present and not found:
                        return True
                    # Not found yet — if checking present, reload once after 5s
                    if present and not found and not reloaded and (time.time() + 5 > deadline):
                        logger.info("[_verify_alias] Reloading page to refresh alias list")
                        await page.reload(wait_until="domcontentloaded")
                        await asyncio.sleep(5)
                        reloaded = True
                        continue
                else:
                    # Search across all frames (fallback)
                    for frame in page.frames:
                        if "allEmailAddresses" in frame.url and "settings" in frame.url:
                            text = await frame.evaluate("() => document.body.innerText")
                            found = alias_email in text
                            if present and found:
                                return True
                            if not present and not found:
                                return True
                            break
                await asyncio.sleep(1)
            return False
        except Exception as e:
            logger.error(f"Error verifying alias: {e}")
            return False

    async def create_alias(self, alias_name: Optional[str] = None, cdp_port: int = 9222, page: Optional[Page] = None) -> Dict[str, Any]:
        if not alias_name:
            alias_name = self.generate_alias_name()
        try:
            page = await self._pw_connect(cdp_port, page=page)
            if not await self._navigate_to_all_email_addresses(page):
                return {"status": "not_logged_in", "alias_email": None, "error": "Navigation fehlgeschlagen"}

            for attempt in range(3):
                current_alias = alias_name if attempt == 0 else self.generate_alias_name()
                alias_email = f"{current_alias}@gmx.de"
                logger.info(f"Erstelle Alias (Versuch {attempt+1}/3): {alias_email}")

                if not await self._fill_alias_input(page, current_alias):
                    return {"status": "error", "alias_email": None, "error": "Input-Fill fehlgeschlagen"}
                await asyncio.sleep(1)

                if not await self._click_add_button(page):
                    return {"status": "error", "alias_email": None, "error": "Hinzufügen-Button nicht gefunden"}
                await asyncio.sleep(3)

                if await self._verify_alias(page, alias_email, present=True):
                    return {"status": "success", "alias_email": alias_email}
                await asyncio.sleep(1)

            return {"status": "failed", "alias_email": None, "error": "Alle Versuche fehlgeschlagen"}
        except Exception as e:
            logger.error(f"Alias-Erstellung fehlgeschlagen: {e}")
            return {"status": "error", "alias_email": None, "error": str(e)}

    # ── Alias Rotation ────────────────────────────────────────────────────

    async def rotate_alias(self, new_alias_name: Optional[str] = None, cdp_port: int = 9222, page: Optional[Page] = None, email: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
        start_time = time.time()
        steps = []
        deleted_alias = None
        created_alias = None
        try:
            if email:
                self._email = email
            if password:
                self._password = password
            page = await self._pw_connect(cdp_port, page=page)
            if not await self._navigate_to_all_email_addresses(page):
                return {"status": "failed", "deleted_alias": None, "created_alias": None,
                        "error": "Navigation fehlgeschlagen", "execution_time": f"{time.time()-start_time:.2f}s"}
            steps.append("navigated")

            # Try to delete existing alias
            alias_email = await self._find_alias_row(page)
            if alias_email:
                logger.info(f"Found alias to delete: {alias_email}")
                if await self._delete_alias(page, alias_email):
                    deleted_alias = alias_email
                    steps.append("deleted")
                    # Don't reload — it breaks session. Just wait for DOM to settle.
                    await asyncio.sleep(3)
                else:
                    logger.warning("Failed to delete alias, continuing")
            else:
                steps.append("no_alias_to_delete")

            # Create new alias
            if not new_alias_name:
                new_alias_name = self.generate_alias_name()
            for attempt in range(3):
                current_alias = new_alias_name if attempt == 0 else self.generate_alias_name()
                alias_email = f"{current_alias}@gmx.de"
                logger.info(f"Creating alias (attempt {attempt+1}/3): {alias_email}")

                if attempt > 0:
                    # Reload page between attempts to reset Wicket state
                    sid_match = re.search(r'[?&]sid=([a-f0-9]{50,})', page.url)
                    if sid_match:
                        await page.goto(f"https://navigator.gmx.net/navigator/jump/to/mail_settings?sid={sid_match.group(1)}", wait_until="domcontentloaded")
                        await asyncio.sleep(6)
                    else:
                        await page.reload(wait_until="domcontentloaded")
                        await asyncio.sleep(5)
                    # Re-navigate to allEmailAddresses
                    await self._navigate_to_all_email_addresses(page)

                if await self._fill_alias_input(page, current_alias):
                    await asyncio.sleep(1)
                    if await self._click_add_button(page):
                        await asyncio.sleep(3)
                        if await self._verify_alias(page, alias_email, present=True):
                            created_alias = alias_email
                            steps.append("created")
                            break
                await asyncio.sleep(1)

            if created_alias:
                return {"status": "success", "deleted_alias": deleted_alias, "created_alias": created_alias,
                        "steps": steps, "execution_time": f"{time.time()-start_time:.2f}s"}
            return {"status": "failed", "deleted_alias": deleted_alias, "created_alias": None,
                    "error": "Erstellung fehlgeschlagen", "steps": steps, "execution_time": f"{time.time()-start_time:.2f}s"}
        except Exception as e:
            logger.error(f"Rotation fehlgeschlagen: {e}")
            return {"status": "failed", "error": str(e), "steps": steps, "execution_time": f"{time.time()-start_time:.2f}s"}

    # ── OTP / Confirm URL ───────────────────────────────────────────────────
    # PLAYWRIGHT-NATIVE (V19.23) — Shadow-DOM + Multi-Frame Scan
    # KEIN CDP, KEINE MailCheck Extension, KEIN User-Chrome nötig!
    # Nutzt den bereits geloggten Playwright-Page (Bot-Chrome, Port 59230)

    async def read_otp_via_playwright(self, browser, sender_filter: str = "fireworks",
                                       max_retries: int = 15, retry_delay: int = 6,
                                       existing_page: Optional[Page] = None) -> Dict[str, Any]:
        """Read OTP via Playwright. ONLY uses existing_page — no new_page() anywhere.
        Navigates existing_page to GMX mail, scans, returns. Caller navigates back."""
        start_time = time.time()
        pattern = re.compile(r'https://app\.fireworks\.ai/(?:signup/(?:confirm|verify)|confirm|verify|accounts/confirm)\S+')
        for attempt in range(max_retries):
            pw_page = existing_page
            if pw_page is None:
                logger.error("[otp] No existing_page provided — cannot check OTP")
                return {"status": "error", "otp_url": None, "error": "No page provided"}
            try:
                await pw_page.goto("https://navigator.gmx.net/mail", wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(5)

                body = await pw_page.evaluate("() => document.body.innerText")
                if "Nicht eingeloggt" in body or ("anmelden" in body.lower()[:300] and "E-Mail" not in body):
                    logger.warning(f"GMX session verloren (attempt {attempt+1})")
                    return {"status": "error", "otp_url": None, "error": "Nicht eingeloggt"}

                # Shadow-DOM + Multi-Frame Scan: Mail kann in OOPIF (z.B. bap.navigator.gmx.net) liegen,
                # nicht nur im Hauptframe. Wir scannen daher ALLE Frames der Page.
                scan_js = r"""
                (SENDER) => {
                    let out = [];
                    function walk(root) {
                        let nodes;
                        try { nodes = root.querySelectorAll('*'); } catch (e) { return; }
                        for (const el of nodes) {
                            if (el.tagName && el.tagName.toLowerCase() === 'list-mail-item') {
                                const txt = (el.innerText || el.textContent || '');
                                if (txt.toLowerCase().includes(SENDER.toLowerCase())) {
                                    const id = (el.getAttribute('id') || '').replace(/^id/, '') || null;
                                    out.push({mailId: id, text: txt.trim().slice(0, 400)});
                                }
                            }
                            if (el.shadowRoot) walk(el.shadowRoot);
                        }
                    }
                    if (document.body) walk(document.body);
                    return out;
                }
                """
                click_js = r"""
                (args) => {
                    const targetId = (args[0] || '');
                    const targetText = (args[1] || '');
                    function walk(root) {
                        let nodes;
                        try { nodes = root.querySelectorAll('*'); } catch (e) { return false; }
                        for (const el of nodes) {
                            if (el.tagName && el.tagName.toLowerCase() === 'list-mail-item') {
                                const eid = (el.getAttribute('id') || '').replace(/^id/, '');
                                const txt = (el.innerText || el.textContent || '').trim().slice(0, 400);
                                if ((targetId && eid === targetId) || (!targetId && txt === targetText)) {
                                    el.click(); return true;
                                }
                            }
                            if (el.shadowRoot && walk(el.shadowRoot)) return true;
                        }
                        return false;
                    }
                    return walk(document.body);
                }
                """
                items = []
                matched_frame = None
                frames = list(pw_page.frames)
                logger.debug(f"[otp] scanning {len(frames)} frame(s): {[f.url[:50] for f in frames]}")
                for frame in frames:
                    try:
                        found = await frame.evaluate(scan_js, sender_filter.lower())
                    except Exception:
                        found = []
                    if found:
                        items.extend(found)
                        matched_frame = frame
                if not items:
                    logger.debug(f"[otp] attempt {attempt+1}/{max_retries}: keine Mail von {sender_filter}")
                    await asyncio.sleep(retry_delay)
                    continue

                # Bestes Match: erstes Item mit Fireworks-Link
                best = None
                for it in items:
                    if 'fireworks' in it['text'].lower():
                        best = it
                        break
                if not best:
                    best = items[0]

                # Mail öffnen via Click
                clicked = await matched_frame.evaluate(click_js, [best['mailId'], best['text']])
                if not clicked:
                    logger.warning(f"[otp] click fehlgeschlagen, retry")
                    await asyncio.sleep(retry_delay)
                    continue

                await asyncio.sleep(3)

                # Link extrahieren
                extract_js = r"""
                () => {
                    let out = [];
                    function walk(root) {
                        let nodes;
                        try { nodes = root.querySelectorAll('a[href]'); } catch (e) { return; }
                        for (const a of nodes) {
                            const href = a.getAttribute('href') || '';
                            if (href.startsWith('http') && href.includes('fireworks.ai')) {
                                out.push(href);
                            }
                        }
                    }
                    if (document.body) walk(document.body);
                    return out;
                }
                """
                for frame in pw_page.frames:
                    try:
                        links = await frame.evaluate(extract_js)
                    except Exception:
                        links = []
                    for link in links:
                        m = pattern.search(link)
                        if m:
                            logger.info(f"[otp] Found verify URL: {m.group(0)[:80]}")
                            return {"status": "success", "otp_url": m.group(0)}
                logger.debug(f"[otp] Kein Fireworks-Link in Mail, retry")
                await asyncio.sleep(retry_delay)

            except Exception as e:
                logger.error(f"[otp] attempt {attempt+1} error: {e}")
                await asyncio.sleep(retry_delay)
        return {"status": "error", "otp_url": None, "error": f"OTP nicht gefunden nach {max_retries} Versuchen"}

    # ── Public Helpers ────────────────────────────────────────────────────
    async def check_session(self, cdp_port: int = 9222, page: Optional[Page] = None) -> Dict[str, Any]:
        try:
            page = await self._pw_connect(cdp_port, page=page)
            await page.goto("https://www.gmx.net/", wait_until="domcontentloaded")
            await asyncio.sleep(3)
            text = await page.evaluate("() => document.body.innerText")
            logged_in = "Sie sind eingeloggt" in text or "Zum Postfach" in text
            return {"status": "logged_in" if logged_in else "not_logged_in", "current_url": page.url}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def open_email_addresses(self, cdp_port: int = 9222, page: Optional[Page] = None) -> Dict[str, Any]:
        try:
            page = await self._pw_connect(cdp_port, page=page)
            ok = await self._navigate_to_all_email_addresses(page)
            return {"status": "success" if ok else "error", "current_url": page.url}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ── Legacy Cookie Injection ──────────────────────────────────────────

    async def _inject_cookies(self, client: CDPClient, session_id: str) -> int:
        cookies_file = Path("./data/gmx-cookies.json")
        if not cookies_file.exists():
            return 0
        try:
            with open(cookies_file) as f:
                cookies = json.load(f)
        except Exception:
            return 0
        injected = 0
        for cookie in cookies:
            try:
                params = {
                    "name": cookie.get("name"),
                    "value": cookie.get("value"),
                    "domain": cookie.get("domain"),
                    "path": cookie.get("path", "/"),
                    "secure": cookie.get("secure", False),
                    "httpOnly": cookie.get("httpOnly", False),
                }
                same_site = cookie.get("sameSite")
                if same_site and same_site != "None":
                    params["sameSite"] = same_site
                expires = cookie.get("expires", -1)
                if expires and expires != -1:
                    try:
                        params["expires"] = float(expires)
                    except (ValueError, TypeError):
                        pass
                result = await client.send_to_session(session_id, "Network.setCookie", params)
                if result and not result.get("error"):
                    injected += 1
            except Exception:
                pass
        logger.info(f"{injected}/{len(cookies)} Cookies injiziert")
        return injected


_gmx_service: Optional[GmxService] = None


def get_gmx_service() -> GmxService:
    global _gmx_service
    if _gmx_service is None:
        _gmx_service = GmxService()
    return _gmx_service
