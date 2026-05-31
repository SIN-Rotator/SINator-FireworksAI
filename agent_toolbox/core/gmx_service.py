"""
SINATOR AGENT-TOOLBOX — GMX Service (Playwright-native v2026-05-28)

Kernfunktionen:
  - GMX Session-Management
  - Alias-Rotation (Löschen + Erstellen)
  - OTP/Confirm-URL Extraktion

Playwright-native für Alias-Rotation + OTP (read_otp_via_playwright).
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
    def __init__(self, context=None):
        self.context = context
        self.inbox_tab: Optional[Page] = None
        self.work_tab: Optional[Page] = None
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

    # ── Multi-Tab Architecture ───────────────────────────────────────────

    async def initialize_architecture(self, browser: Browser):
        """Erstelle isolierte Tabs: work_tab (Alias/FW) + inbox_tab (OTP, bleibt IMMER im Posteingang).
        inbox_tab wird ERST navigiert nach erfolgreichem Login (via navigate_inbox()).
        """
        logger.info("Initialisiere Multi-Tab Architektur...")
        self.work_tab = await browser.new_page()
        self.inbox_tab = await browser.new_page()
        logger.info("Tabs erstellt. inbox_tab wird nach Login navigiert.")

    async def navigate_inbox(self):
        """Navigiert inbox_tab zum Posteingang (NUR nach Login aufrufen!)."""
        if self.inbox_tab is None:
            logger.error("inbox_tab nicht initialisiert")
            return False
        logger.info("Navigiere inbox_tab zum Posteingang...")
        await self.inbox_tab.goto("https://navigator.gmx.net/mail", wait_until="domcontentloaded")
        await asyncio.sleep(5)
        body = await self.inbox_tab.evaluate("() => document.body.innerText")
        if "Nicht eingeloggt" in body or ("anmelden" in body.lower()[:200] and "E-Mail" not in body):
            logger.error("inbox_tab Session ungültig — Login vorher ausführen!")
            return False
        logger.info("✅ inbox_tab im Posteingang (session-verifiziert)")
        return True

    async def read_otp_cdp_axtree(
        self, sender_keyword: str = "fireworks", timeout: int = 180
    ) -> Dict[str, Any]:
        """BULLETPROOF OTP via CDP Accessibility Tree.
        Umgeht das '62 Ad-Frames' Problem komplett.
        Nutzt Chromium's prozessübergreifende AXTree (durchdringt OOPIFs + Shadow-DOM).
        """
        if self.inbox_tab is None:
            logger.error("inbox_tab nicht initialisiert")
            return {"status": "error", "otp_url": None, "error": "inbox_tab missing"}

        logger.info(f"[CDP-AXTree] Starte OTP-Suche (Keyword: {sender_keyword}, timeout: {timeout}s)")
        pattern_url = re.compile(
            r"https://app\.fireworks\.ai/(?:signup/(?:confirm|verify)|confirm|verify|accounts/confirm)\S+"
        )
        pattern_otp = re.compile(r"\b[A-Z0-9]{6}\b")

        cdp = None
        start_time = time.time()
        try:
            cdp = await self.inbox_tab.context.new_cdp_session(self.inbox_tab)
            await cdp.send("Accessibility.enable")
            logger.info("[CDP-AXTree] CDP session erstellt")

            deadline = start_time + timeout
            while time.time() < deadline:
                try:
                    tree_result = await cdp.send("Accessibility.getFullAXTree", {"pierce": True})
                    nodes = tree_result.get("nodes", [])
                    logger.debug(f"[CDP-AXTree] {len(nodes)} AXTree nodes gescannt, URL: {self.inbox_tab.url[:60]}")

                    # Session Restore / Consent / Loading page detection
                    current_url = self.inbox_tab.url or ""
                    is_on_inbox = "navigator.gmx.net/mail" in current_url or "bap.navigator.gmx.net/mail" in current_url

                    if len(nodes) < 20 or not is_on_inbox or "logoutlounge" in current_url:
                        # Check for session restore interstitial
                        session_keywords = ["sitzung", "wiederhergestellt", "cookies", "loading", "bitte warten", "wird geladen"]
                        sample_text = " ".join(
                            f"{(n.get('name') or {}).get('value', '')} {(n.get('description') or {}).get('value', '')}"
                            for n in nodes[:15]
                        ).lower()
                        has_session_msg = any(kw in sample_text for kw in session_keywords)

                        if has_session_msg or len(nodes) < 20 or "logoutlounge" in current_url:
                            logger.warning(f"[CDP-AXTree] GMX Session/Loading-Seite erkannt (nodes={len(nodes)}, inbox={is_on_inbox}, url={current_url[:60]}) — lade neu...")
                            try:
                                await self.inbox_tab.reload(wait_until="domcontentloaded", timeout=15000)
                                await asyncio.sleep(5)
                                logger.info("[CDP-AXTree] Page reloaded, continue polling")
                                continue
                            except Exception as reload_err:
                                logger.warning(f"[CDP-AXTree] Reload failed: {reload_err}")
                                try:
                                    await self.inbox_tab.goto(current_url, wait_until="domcontentloaded", timeout=15000)
                                    await asyncio.sleep(5)
                                except Exception:
                                    pass
                                continue

                    full_text = ""
                    fireworks_found = False

                    for node in nodes:
                        name_val = (node.get("name") or {}).get("value", "")
                        desc_val = (node.get("description") or {}).get("value", "")
                        val_val = (node.get("value") or {}).get("value", "")
                        node_text = f"{name_val} {desc_val} {val_val}"
                        node_lower = node_text.lower()

                        if sender_keyword.lower() in node_lower:
                            fireworks_found = True
                            full_text += " " + node_text

                            url_match = pattern_url.search(node_text)
                            if url_match:
                                elapsed = time.time() - start_time
                                logger.info(f"[CDP-AXTree] ✅ URL gefunden nach {elapsed:.1f}s")
                                return {
                                    "status": "success",
                                    "otp_url": html_module.unescape(url_match.group(0)),
                                    "otp_code": None,
                                    "execution_time": f"{elapsed:.2f}s",
                                }

                    if fireworks_found:
                        otp_match = pattern_otp.search(full_text)
                        if otp_match:
                            elapsed = time.time() - start_time
                            logger.info(f"[CDP-AXTree] ✅ OTP-Code: {otp_match.group(0)}")
                            return {
                                "status": "success",
                                "otp_url": None,
                                "otp_code": otp_match.group(0),
                                "execution_time": f"{elapsed:.2f}s",
                            }

                    elapsed = time.time() - start_time
                    remaining = deadline - time.time()
                    sleep_t = min(8, remaining) if remaining > 0 else 0
                    if sleep_t > 0:
                        logger.info(f"[CDP-AXTree] Mail nicht da. Warte {sleep_t:.0f}s... (elapsed: {elapsed:.0f}s)")
                        await asyncio.sleep(sleep_t)

                except Exception as e:
                    logger.warning(f"[CDP-AXTree] Scan error: {e}")
                    await asyncio.sleep(5)

            logger.warning("[CDP-AXTree] Timeout")
            return {"status": "not_found", "otp_url": None, "otp_code": None, "error": "Timeout"}
        except Exception as e:
            logger.error(f"[CDP-AXTree] CDP session error: {e}")
            return {"status": "error", "otp_url": None, "error": str(e)}
        finally:
            if cdp:
                try:
                    await cdp.detach()
                except Exception:
                    pass

    async def read_otp_axtree_and_frames(self, sender_keyword: str = "fireworks", timeout: int = 90) -> Dict[str, Any]:
        """OTP-Suche via Frame-Traversal + Shadow-DOM-Durchdringung.
        Nutzt inbox_tab (dedizierter GMX-Tab, session-isoliert).
        Sucht 6-stellige Codes (A-Z0-9) sobald Keyword irgendwo im Frame gefunden.
        """
        if self.inbox_tab is None:
            logger.error("inbox_tab nicht initialisiert — initialize_architecture() vorher aufrufen!")
            return {"status": "error", "otp_url": None, "error": "inbox_tab missing"}
        logger.info(f"Starte OTP-Suche via Frame-Traversal (Keyword: {sender_keyword}, inbox_tab)")
        otp_pattern = re.compile(r'\b[A-Z0-9]{6}\b')
        start = time.time()
        while time.time() - start < timeout:
            for frame in self.inbox_tab.frames:
                try:
                    texts = await frame.evaluate("""() => {
                        let results = [];
                        function traverse(node) {
                            if (!node) return;
                            if (node.shadowRoot) { traverse(node.shadowRoot); }
                            node.childNodes.forEach(child => {
                                if (child.nodeType === Node.TEXT_NODE && child.textContent?.trim()) {
                                    results.push(child.textContent.trim());
                                } else if (child.nodeType === Node.ELEMENT_NODE) {
                                    traverse(child);
                                }
                            });
                        }
                        if (document.body) traverse(document.body);
                        return results;
                    }""")
                    full_text = " ".join(texts)
                    full_lower = full_text.lower()
                    has_ctx = (sender_keyword.lower() in full_lower or "verification" in full_lower
                               or "verify" in full_lower or "confirm" in full_lower or "code" in full_lower)
                    if has_ctx:
                        # 1) Fireworks Confirm-URL bevorzugt (eindeutiger als ein 6-stelliger Code)
                        url_m = re.search(r'https://app\.fireworks\.ai/(?:signup/(?:confirm|verify)|confirm|verify|accounts/confirm)\S+', full_text)
                        if url_m:
                            elapsed = time.time() - start
                            logger.info(f"OTP-URL in Frame {frame.url[:60]} gefunden")
                            return {"status": "success", "otp_url": html_module.unescape(url_m.group(0)), "otp_code": None, "execution_time": f"{elapsed:.2f}s"}
                        # 2) 6-stelliger Code NUR aus Chunks mit Verifizierungs-Kontext (vermeidet False-Positives)
                        for chunk in texts:
                            cl = chunk.lower()
                            if any(k in cl for k in ("code", "verif", "confirm", "bestätig", "einmal")):
                                m = re.search(r'\b\d{6}\b', chunk) or otp_pattern.search(chunk)
                                if m:
                                    elapsed = time.time() - start
                                    logger.info(f"OTP-Code in Frame {frame.url[:60]} gefunden: {m.group(0)}")
                                    return {"status": "success", "otp_url": None, "otp_code": m.group(0), "execution_time": f"{elapsed:.2f}s"}
                except Exception:
                    continue
            await asyncio.sleep(3)
        logger.warning("Timeout: OTP nicht im inbox_tab gefunden")
        return {"status": "not_found", "otp_url": None, "otp_code": None, "error": "Timeout"}

# ── Playwright Connection ────────────────────────────────────────────

    async def _pw_connect(self, cdp_port: int = 9222, page: Optional[Page] = None) -> Page:
        """Connect to existing Chrome via CDP and return a Playwright Page.
        If page is provided (V15.4 ONE Browser), returns it directly.
        Otherwise connects via CDP and looks for existing GMX pages."""
        if page is not None:
            logger.info("[_pw_connect] Using provided page (V15.4 ONE Browser)")
            return page
        logger.info(f"[_pw_connect] Connecting to Chrome on CDP port {cdp_port}")
        p = await async_playwright().start()
        browser = await p.chromium.connect_over_cdp(f"http://localhost:{cdp_port}")
        
        # First, look for allEmailAddresses page
        page = None
        for ctx in browser.contexts:
            for pg in ctx.pages:
                url = pg.url or ""
                if "allEmailAddresses" in url and "settings" in url and "iac/restart" not in url:
                    page = pg
                    logger.info(f"[_pw_connect] Found allEmailAddresses page: {url[:60]}...")
                    return page
        
        # Otherwise, look for any valid GMX page (not iac/restart)
        for ctx in browser.contexts:
            for pg in ctx.pages:
                url = pg.url or ""
                if "gmx.net" in url and "iac/restart" not in url and "session-expired" not in url and "logoutlounge" not in url:
                    page = pg
                    logger.info(f"[_pw_connect] Found GMX page: {url[:60]}...")
                    return page
        
        # Fallback to first page that is not iac/restart
        for ctx in browser.contexts:
            for pg in ctx.pages:
                url = pg.url or ""
                if "iac/restart" not in url and "session-expired" not in url and "logoutlounge" not in url:
                    page = pg
                    logger.info(f"[_pw_connect] Using fallback page: {url[:60]}...")
                    return page
        
        # Last resort: create new page
        if browser.contexts and browser.contexts[0].pages:
            page = browser.contexts[0].pages[0]
            logger.info(f"[_pw_connect] Using first page: {page.url[:60]}...")
        else:
            page = await browser.contexts[0].new_page() if browser.contexts else await browser.new_page()
            logger.info(f"[_pw_connect] Created new page")
        
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
            
            # Fallback: click Login button on homepage, then two-step auth
            logger.info("Homepage without login form — clicking Login button")
            try:
                login_btn = page.locator('button:has-text("Login")').first
                if await login_btn.is_visible(timeout=3000):
                    await login_btn.click()
                    logger.info("Clicked Login button on homepage")
                    await asyncio.sleep(5)
                    url = page.url
                    logger.info(f"After login click: {url[:80]}")
                    
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
                        
                        # If prompt=none, replace with prompt=login via JS
                        if "prompt=none" in page.url:
                            logger.info("prompt=none detected — replacing with prompt=login")
                            await page.evaluate("""
                                const u = new URL(window.location.href);
                                u.searchParams.set('prompt', 'login');
                                window.history.replaceState({}, '', u.toString());
                            """)
                            await asyncio.sleep(1)
                        
                        # Step 2: password
                        password_input = page.locator('input[type="password"]').first
                        if await password_input.is_visible(timeout=8000):
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
            if not await self._login(page):
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
                if '@gmx.' in line and 'delqhi@gmx.de' not in line and 'opensin@gmx.de' not in line:
                    parts = line.split()
                    for part in parts:
                        if '@gmx.' in part and part != 'delqhi@gmx.de' and part != 'opensin@gmx.de':
                            logger.info(f"Found alias: {part}")
                            return part
        except Exception as e:
            logger.warning(f"Error finding alias: {e}")
        return None

    async def _delete_alias(self, page: Page, alias_email: str) -> bool:
        """Delete an alias via CDP Input.dispatchMouseEvent (Wicket-kompatibel)."""
        logger.info(f"[_delete_alias] Deleting {alias_email}")
        try:
            frame = await self._get_all_email_frame(page)
            if not frame:
                logger.warning("allEmailAddresses iframe not found for delete")
                return False

            # 1) TABLE-ROW finden die den Alias enthält
            row_data = await frame.evaluate(f"""() => {{
                var rows = document.querySelectorAll('tr, li, .row, [class*="row"]');
                for (var i=0; i<rows.length; i++) {{
                    if (rows[i].textContent.includes('{alias_email}')) {{
                        var r = rows[i].getBoundingClientRect();
                        if (r.width > 20 && r.height > 5) {{
                            // Mitte der Zeile (für Hover)
                            return {{
                                cx: Math.round(r.x + r.width/2),
                                cy: Math.round(r.y + r.height/2)
                            }};
                        }}
                    }}
                }}
                return null;
            }}""")
            if not row_data:
                logger.warning(f"Alias row not found: {alias_email}")
                return False

            # 2) CDP-Session für native Mouse-Events
            cdp = await page.context.new_cdp_session(page)

            # 3) Hover über die ZEILE (nicht über ein Text-Element)
            logger.info(f"Hover row via CDP at ({row_data['cx']}, {row_data['cy']})")
            await cdp.send('Input.dispatchMouseEvent', {
                'type': 'mouseMoved', 'x': row_data['cx'], 'y': row_data['cy']
            })
            await asyncio.sleep(1.5)

            # 4) Delete-Icon INNERHALB der Zeile suchen
            delete_pos = await frame.evaluate(f"""() => {{
                var rows = document.querySelectorAll('tr, li, .row, [class*="row"]');
                for (var i=0; i<rows.length; i++) {{
                    if (rows[i].textContent.includes('{alias_email}')) {{
                        var delEl = rows[i].querySelector('[title*="lösch"], [aria-label*="lösch"], [title*="lösch"], [class*="delete"]');
                        if (!delEl) {{
                            delEl = rows[i].querySelector('a, button, span, i, img, svg');
                        }}
                        if (delEl) {{
                            var r = delEl.getBoundingClientRect();
                            if (r.width > 5 && r.height > 5) {{
                                return {{x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2), title: delEl.getAttribute('title') || ''}};
                            }}
                        }}
                    }}
                }}
                return null;
            }}""")
            if not delete_pos:
                logger.warning("Delete icon not found in alias row — global search as fallback")
                # Fallback: global search
                delete_pos = await frame.evaluate("""() => {
                    var allEls = document.querySelectorAll('a, button, span, i, img, svg');
                    for (var i=0; i<allEls.length; i++) {
                        var el = allEls[i];
                        var title = (el.getAttribute('title') || '').toLowerCase();
                        var aria = (el.getAttribute('aria-label') || '').toLowerCase();
                        if (title.includes('l\u00f6sch') || aria.includes('l\u00f6sch') || title.includes('delete')) {
                            var r = el.getBoundingClientRect();
                            if (r.width > 5 && r.height > 5) {
                                return {x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2), title: el.getAttribute('title') || ''};
                            }
                        }
                    }
                    return null;
                }""")
                if not delete_pos:
                    logger.warning("Delete icon not found globally either")
                    return False

            logger.info(f"Delete '{delete_pos.get('title', '')}' at ({delete_pos['x']}, {delete_pos['y']})")

            # 5) Delete per CDP klicken
            await cdp.send('Input.dispatchMouseEvent', {
                'type': 'mousePressed', 'x': delete_pos['x'], 'y': delete_pos['y'],
                'button': 'left', 'clickCount': 1
            })
            await asyncio.sleep(0.05)
            await cdp.send('Input.dispatchMouseEvent', {
                'type': 'mouseReleased', 'x': delete_pos['x'], 'y': delete_pos['y'],
                'button': 'left', 'clickCount': 1
            })
            await asyncio.sleep(3)

            # 6) Confirm-Dialog (OK)
            ok_pos = await frame.evaluate("""() => {
                var allEls = document.querySelectorAll('button, a, span');
                for (var i=0; i<allEls.length; i++) {
                    var el = allEls[i];
                    if (el.textContent && el.textContent.trim() === 'OK') {
                        var r = el.getBoundingClientRect();
                        if (r.width > 5 && r.height > 5) {
                            return {x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)};
                        }
                    }
                }
                return null;
            }""")
            if ok_pos:
                logger.info(f"OK confirm at ({ok_pos['x']}, {ok_pos['y']})")
                await cdp.send('Input.dispatchMouseEvent', {
                    'type': 'mousePressed', 'x': ok_pos['x'], 'y': ok_pos['y'],
                    'button': 'left', 'clickCount': 1
                })
                await asyncio.sleep(0.05)
                await cdp.send('Input.dispatchMouseEvent', {
                    'type': 'mouseReleased', 'x': ok_pos['x'], 'y': ok_pos['y'],
                    'button': 'left', 'clickCount': 1
                })
                await asyncio.sleep(2)

            # 7) Verifikation
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
            import traceback
            traceback.print_exc()
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
        """Click the add alias button via CDP native events (Wicket-kompatibel)."""
        logger.info("[_click_add_button] Looking for add button")
        try:
            frame = await self._get_all_email_frame(page)
            if not frame:
                logger.warning("allEmailAddresses iframe not found")
                return False

            # CDP native click via bounding box (Wicket-kompatibel)
            btn = frame.locator('button:has-text("Hinzufügen")').first
            bb = await btn.bounding_box()
            if bb:
                cx = bb['x'] + bb['width'] / 2
                cy = bb['y'] + bb['height'] / 2
                cdp = await page.context.new_cdp_session(page)
                await cdp.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": cx, "y": cy})
                await asyncio.sleep(0.1)
                await cdp.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": cx, "y": cy, "button": "left", "clickCount": 1})
                await asyncio.sleep(0.1)
                await cdp.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": cx, "y": cy, "button": "left", "clickCount": 1})
                await asyncio.sleep(2)
                logger.info("Hinzufügen button clicked via CDP")
                try: await cdp.detach()
                except: pass
                return True

            # Fallback: JS evaluate
            result = await frame.evaluate("""(function() {
                var btns = document.querySelectorAll('button');
                for (var i = 0; i < btns.length; i++) {
                    if (btns[i].textContent.indexOf('Hinzuf') >= 0) {
                        btns[i].click();
                        return true;
                    }
                }
                return false;
            })()""")
            if result:
                logger.info("Hinzufügen button clicked via JS")
                await asyncio.sleep(2)
                return True
            
            logger.warning("Add button not found")
            return False
        except Exception as e:
            logger.error(f"Error clicking add button: {e}")
            return False

    async def _verify_alias(self, page: Page, alias_email: str, present: bool = True, max_wait: float = 12.0) -> bool:
        """Verify alias is present/absent — searches iframe content (not top frame)."""
        logger.info(f"[_verify_alias] Checking {alias_email} present={present}")
        try:
            deadline = time.time() + max_wait
            while time.time() < deadline:
                frame = await self._get_all_email_frame(page)
                if frame:
                    text = await frame.evaluate("() => document.body.innerText")
                    found = alias_email in text
                    if present and found:
                        return True
                    if not present and not found:
                        return True
                else:
                    for f in page.frames:
                        if "allEmailAddresses" in f.url and "settings" in f.url:
                            text = await f.evaluate("() => document.body.innerText")
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

    async def rotate_alias(self, new_alias_name: Optional[str] = None, cdp_port: int = 9222, page: Optional[Page] = None) -> Dict[str, Any]:
        start_time = time.time()
        steps = []
        deleted_alias = None
        created_alias = None
        try:
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
    # OTP bleibt auf CDP — funktioniert, komplex (MailCheck Extension, OOPIF)

    async def _otp_connect(self, cdp_port: int) -> Tuple[CDPClient, str]:
        ws_url = await get_browser_ws_endpoint(cdp_port)
        client = CDPClient(ws_url)
        await client.connect()
        targets = await client.get_targets()
        target = None
        for t in targets:
            if t.get("type") == "page" and "sid=" in t.get("url", "") and "gmx.net" in t.get("url", ""):
                target = t
                break
        if not target:
            target = await get_page_target(client, url_filter="gmx.net")
        if not target:
            # Kein GMX-Target — neues Target via Target.createTarget
            logger.info("No GMX target found — creating new page via CDP")
            create = await client.send_to_session(None, "Target.createTarget", {"url": "https://www.gmx.net/"})
            new_target_id = create.get("targetId")
            if new_target_id:
                target = await get_page_target(client, url_filter="gmx.net")
        if not target:
            await client.disconnect()
            raise RuntimeError("Kein GMX Page-Target gefunden")
        session_id = await client.attach_to_target(target["targetId"])
        await client.send_to_session(session_id, "Page.enable")
        await client.send_to_session(session_id, "Runtime.enable")
        return client, session_id

    async def read_otp(self, sender_filter: str = "fireworks", max_retries: int = 12, retry_delay: int = 5, cdp_port: int = 9222) -> Dict[str, Any]:
        start_time = time.time()
        client = None
        try:
            client, session_id = await self._otp_connect(cdp_port)
            url_result = await client.evaluate(session_id, "window.location.href")
            current_url = url_result.get("result", {}).get("value", "")
            sid = None
            if "bap.navigator.gmx.net" in current_url and "sid=" in current_url:
                sid = re.search(r'[?&]sid=([^&]+)', current_url)
                sid = sid.group(1) if sid else None
            if not sid:
                await client.navigate(session_id, "https://www.gmx.net/")
                await asyncio.sleep(4)
                body = await client.evaluate(session_id, "document.body.innerText")
                text = body.get("result", {}).get("value", "")
                if "Sie sind eingeloggt" not in text and "Zum Postfach" not in text:
                    return {"status": "error", "otp_url": None, "error": "Nicht eingeloggt"}
                await client.evaluate(session_id, """
                (function(){
                    var els = Array.from(document.querySelectorAll('a, button, [role=link], nav a'));
                    var el = els.find(e => (e.textContent||'').trim() === 'E-Mail');
                    if (el) { el.click(); return true; }
                    return false;
                })()
                """, return_by_value=True)
                await asyncio.sleep(5)
                url_result = await client.evaluate(session_id, "window.location.href")
                current_url = url_result.get("result", {}).get("value", "")
                sid = re.search(r'[?&]sid=([^&]+)', current_url)
                sid = sid.group(1) if sid else None
            if not sid:
                return {"status": "error", "otp_url": None, "error": "Kein SID"}
            mail_url = f"https://bap.navigator.gmx.net/mail?sid={sid}"
            await client.navigate(session_id, mail_url)
            await asyncio.sleep(6)
            iframe_result = await client.evaluate(session_id, """
            (function() {
                var iframe = document.querySelector('#thirdPartyFrame_mail');
                return iframe ? iframe.src : null;
            })()
            """, return_by_value=True)
            iframe_src = iframe_result.get("result", {}).get("value", "")
            if not iframe_src:
                return {"status": "error", "otp_url": None, "error": "Mail iframe nicht gefunden"}
            await client.navigate(session_id, iframe_src)
            await asyncio.sleep(5)
            cookies_res = await client.send_to_session(session_id, "Network.getAllCookies")
            jsessionid = None
            for c in cookies_res.get("cookies", []):
                if c.get("name") == "JSESSIONID":
                    jsessionid = c.get("value", "")
                    break
            if not jsessionid:
                current_url_result = await client.evaluate(session_id, "window.location.href")
                current_page_url = current_url_result.get("result", {}).get("value", "")
                jsessionid_match = re.search(r'jsessionid=([^?&;]+)', current_page_url)
                jsessionid = jsessionid_match.group(1) if jsessionid_match else None
            if not jsessionid:
                return {"status": "error", "otp_url": None, "error": "Kein JSESSIONID"}
            known_ids = set()
            for i in range(max_retries):
                logger.info(f"OTP-Suche: Versuch {i+1}/{max_retries}")
                safe_filter = sender_filter.lower().replace("'", "\\'")
                items_js = f"""
                (function() {{
                    function findItems(root) {{
                        let items = [];
                        const all = root.querySelectorAll('*');
                        for (const el of all) {{
                            if (el.tagName.toLowerCase() === 'list-mail-item') {{
                                const text = (el.textContent || '').toLowerCase();
                                if (text.includes('{safe_filter}')) {{
                                    const idAttr = el.getAttribute('id');
                                    const mailId = idAttr ? idAttr.replace(/^id/, '') : null;
                                    if (mailId) {{
                                        items.push({{mailId: mailId, text: el.textContent.trim().slice(0, 120)}});
                                    }}
                                }}
                            }}
                            if (el.shadowRoot) {{
                                items = items.concat(findItems(el.shadowRoot));
                            }}
                        }}
                        return items;
                    }}
                    return findItems(document.body);
                }})()
                """
                items_result = await client.evaluate(session_id, items_js, return_by_value=True)
                items = items_result.get("result", {}).get("value", [])
                new_items = [it for it in items if it.get("mailId") not in known_ids]
                if new_items:
                    await client.send_to_session(session_id, "Accessibility.enable")
                    await asyncio.sleep(1)
                    ax_result = await client.send_to_session(session_id, "Accessibility.getFullAXTree", {"depth": -1, "pierce": True})
                    ax_nodes = ax_result.get("nodes", [])
                    verify_nodes = []
                    for n in ax_nodes:
                        name_val = (n.get("name", {}) or {}).get("value", "")
                        desc_val = (n.get("description", {}) or {}).get("value", "")
                        combined = f"{name_val} {desc_val}".lower()
                        if "fireworks" in combined:
                            verify_nodes.append(n)
                    logger.info(f"AXTree: {len(ax_nodes)} nodes, {len(verify_nodes)} fireworks hits")
                    if verify_nodes:
                        target_node = verify_nodes[0]
                        bid = target_node.get("backendDOMNodeId")
                        if bid:
                            try:
                                quad = await client.send_to_session(session_id, "DOM.getContentQuads", {"backendNodeId": bid})
                                quads = quad.get("quads", [])
                                if quads and quads[0]:
                                    q = quads[0]
                                    cx = (q[0] + q[4]) / 2
                                    cy = (q[1] + q[5]) / 2
                                    logger.info(f"Click fireworks email at ({cx:.0f},{cy:.0f})")
                                    before_ids = {t["targetId"] for t in await client.get_targets()}
                                    await client.send_to_session(session_id, "Input.dispatchMouseEvent", {"type": "mouseMoved", "x": cx, "y": cy})
                                    await asyncio.sleep(0.2)
                                    await client.send_to_session(session_id, "Input.dispatchMouseEvent", {"type": "mousePressed", "x": cx, "y": cy, "button": "left", "clickCount": 1})
                                    await asyncio.sleep(0.15)
                                    await client.send_to_session(session_id, "Input.dispatchMouseEvent", {"type": "mouseReleased", "x": cx, "y": cy, "button": "left", "clickCount": 1})
                                    await asyncio.sleep(5)
                                    after = await client.get_targets()
                                    for t in after:
                                        tu = t.get("url", "")
                                        if "mailbody" in tu:
                                            logger.info(f"Mailbody OOPIF: {tu[:120]}")
                                            try:
                                                ifs = await client.attach_to_target(t["targetId"])
                                                await client.send_to_session(ifs, "Runtime.enable")
                                                body_r = await client.evaluate(ifs, 'document.body ? document.body.innerText : ""', return_by_value=True)
                                                b = body_r.get("result", {}).get("value", "") or ""
                                                if not b.strip():
                                                    html_r = await client.evaluate(ifs, 'document.body ? document.body.innerHTML : ""', return_by_value=True)
                                                    b = html_r.get("result", {}).get("value", "") or ""
                                                urls = re.findall(r'https?://app\.fireworks\.ai/(?:signup/(?:confirm|verify)|confirm|verify)[^\s\"\'<>]+', b)
                                                if urls:
                                                    elapsed = time.time() - start_time
                                                    return {"status": "success", "otp_url": html_module.unescape(urls[0]), "mail_id": None, "execution_time": f"{elapsed:.2f}s"}
                                            except Exception:
                                                pass
                                            await asyncio.sleep(0.1)
                            except Exception as e:
                                logger.warning(f"AXTree click failed: {e}")
                for it in items:
                    mid = it.get("mailId")
                    if mid:
                        known_ids.add(mid)
                if i < max_retries - 1:
                    await asyncio.sleep(retry_delay)
            return {"status": "not_found", "otp_url": None, "error": "Nicht gefunden"}
        except Exception as e:
            logger.error(f"OTP-Suche fehlgeschlagen: {e}")
            return {"status": "error", "otp_url": None, "error": str(e)}
        finally:
            if client:
                await client.disconnect()

    async def read_otp_via_playwright(self, browser: Browser, sender_filter: str = "fireworks",
                                       max_retries: int = 15, retry_delay: int = 6,
                                       existing_page: Optional[Page] = None) -> Dict[str, Any]:
        """Read OTP via Playwright. Wenn existing_page übergeben, reuse (bleibt im logged-in Tab).
        Sonst frische Page pro Versuch (fallback).
        """
        start_time = time.time()
        pattern = re.compile(r'https://app\.fireworks\.ai/(?:signup/(?:confirm|verify)|confirm|verify|accounts/confirm)\S+')
        for attempt in range(max_retries):
            pw_page = None
            own_page = False
            try:
                if existing_page is not None and attempt == 0:
                    pw_page = existing_page
                else:
                    pw_page = await browser.new_page()
                    own_page = True
                await pw_page.goto("https://navigator.gmx.net/mail", wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(5)

                body = await pw_page.evaluate("() => document.body.innerText")
                if "Nicht eingeloggt" in body or ("anmelden" in body.lower()[:300] and "E-Mail" not in body):
                    logger.warning(f"GMX session verloren (attempt {attempt+1})")
                    return {"status": "error", "otp_url": None, "error": "Nicht eingeloggt"}

                # Shadow-DOM + Multi-Frame Scan: Mail kann in OOPIF (z.B. bap.navigator.gmx.net) liegen,
                # nicht nur im Hauptframe. Wir scannen daher ALLE Frames der Page.
                scan_js = r"""
                (() => {
                    const SENDER = arguments[0];
                    let out = [];
                    function walk(root) {
                        let nodes;
                        try { nodes = root.querySelectorAll('*'); } catch (e) { return; }
                        for (const el of nodes) {
                            if (el.tagName && el.tagName.toLowerCase() === 'list-mail-item') {
                                const txt = (el.innerText || el.textContent || '');
                                if (txt.toLowerCase().includes(SENDER)) {
                                    const id = (el.getAttribute('id') || '').replace(/^id/, '') || null;
                                    out.push({mailId: id, text: txt.trim().slice(0, 400)});
                                }
                            }
                            if (el.shadowRoot) walk(el.shadowRoot);
                        }
                    }
                    if (document.body) walk(document.body);
                    return out;
                })()
                """
                click_js = r"""
                (() => {
                    const a = arguments[0] || [];
                    const targetId = a[0];
                    const targetText = a[1];
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
                })()
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
                        items = found
                        matched_frame = frame
                        break

                if items and matched_frame is not None:
                    logger.info(f"Found {len(items)} email(s) matching '{sender_filter}' in {matched_frame.url[:60]}")
                    logger.debug(f"Items: {[i.get('text','')[:60] for i in items]}")

                    # Check mail list preview for URL
                    for item in items:
                        urls = pattern.findall(item.get('text', ''))
                        if urls:
                            elapsed = time.time() - start_time
                            return {"status": "success", "otp_url": html_module.unescape(urls[0]), "execution_time": f"{elapsed:.2f}s"}

                    # Click first matching email IN ITS FRAME (Playwright evaluate nimmt genau 1 Arg -> Liste)
                    clicked = await matched_frame.evaluate(click_js, [items[0].get('mailId'), items[0].get('text', '')])
                    if clicked:
                        logger.info("Clicked email — polling for OOPIF...")
                        # Poll OOPIF: 3 tries × 3s = 9s max wait
                        for oopif_wait in range(3):
                            await asyncio.sleep(3)
                            for frame in pw_page.frames:
                                try:
                                    text = await frame.evaluate("() => document.body.innerText", timeout=3000)
                                    urls = pattern.findall(text or '')
                                    if urls:
                                        elapsed = time.time() - start_time
                                        return {"status": "success", "otp_url": html_module.unescape(urls[0]), "execution_time": f"{elapsed:.2f}s"}
                                except Exception:
                                    pass
                        # Fallback: scan entire page HTML
                        html = await pw_page.content()
                        urls = pattern.findall(html)
                        if urls:
                            elapsed = time.time() - start_time
                            return {"status": "success", "otp_url": html_module.unescape(urls[0]), "execution_time": f"{elapsed:.2f}s"}
                        logger.warning("OOPIF not found after clicking email")
                else:
                    logger.info(f"No '{sender_filter}' email yet (attempt {attempt+1}/{max_retries})")
            except Exception as e:
                logger.warning(f"OTP attempt {attempt+1} fehlgeschlagen: {e}")
            finally:
                if pw_page and own_page:
                    try:
                        await pw_page.close()
                    except Exception:
                        pass

            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)

        return {"status": "not_found", "otp_url": None, "error": "Nicht gefunden"}

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
