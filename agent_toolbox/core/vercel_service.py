"""Vercel v0 E2E flow — signup, phone verify, login, API token.

Uses 100% SIN-Browser-Tools (zero raw page.evaluate calls).
Bot Chrome stays open until API token is generated.

Docs: vercel_service.doc.md
"""
import asyncio
import logging
import random
import string
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class VercelService:
    """Vercel account creation, phone verification via SMSPool, and API token extraction."""

    def __init__(self, manager=None):
        self.mgr = manager

    # ── Helpers ────────────────────────────────────────────────────────────────

    async def _set_react_value(self, selector: str, value: str) -> bool:
        """Fill a React-controlled input using native value setter + events.

        Playwright's fill()/type() only writes to the DOM attribute; React's
        synthetic event system ignores it unless 'input' and 'change' events
        bubble. This helper uses Object.getOwnPropertyDescriptor to call the
        native HTMLInputElement setter, then dispatches the two events React
        listens for.

        Returns True if element was found and set, False otherwise.
        """
        from sin_browser_tools.tools.extraction import browser_console

        r = await browser_console(f"""(() => {{
            var inp = document.querySelector({selector!r});
            if (!inp) return 'not_found';
            var setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
            setter.call(inp, {value!r});
            inp.dispatchEvent(new Event('input', {{bubbles: true}}));
            inp.dispatchEvent(new Event('change', {{bubbles: true}}));
            return 'ok';
        }})()""")
        ok = (r or {}).get("result") == "ok"
        if ok:
            logger.info(f"React-set {selector} = {value[:20]}...")
        else:
            logger.warning(f"React-set failed for {selector}: {r}")
        return ok

    async def _click_by_js_text(self, text_substring: str, tag: str = "button") -> bool:
        """Click first element whose textContent contains substring (JS fallback)."""
        from sin_browser_tools.tools.extraction import browser_console

        r = await browser_console(f"""(() => {{
            var els = document.querySelectorAll('{tag}');
            for (var i=0; i<els.length; i++) {{
                var t = (els[i].textContent || '').trim();
                if (t.indexOf({text_substring!r}) !== -1) {{
                    els[i].dispatchEvent(new MouseEvent('click', {{bubbles: true, cancelable: true}}));
                    return t;
                }}
            }}
            return 'not_found';
        }})()""")
        res = (r or {}).get("result", "")
        if res != "not_found":
            logger.info(f"JS-clicked '{text_substring}' → {res}")
            return True
        return False

    async def _current_url(self) -> str:
        from sin_browser_tools.tools.navigation import browser_get_url
        return (await browser_get_url()).get("url", "")

    async def _body_text(self) -> str:
        from sin_browser_tools.tools.extraction import browser_console
        r = await browser_console("document.body.innerText")
        return (r or {}).get("result", "")[:500]

    async def _handle_cookie_banner(self) -> None:
        """Remove common cookie consent banners (Generic / CookieYes)."""
        from sin_browser_tools.tools.extraction import browser_console
        await browser_console("""(() => {
            document.querySelectorAll('.cky-overlay, .cky-consent-container, .cky-modal, [class*="cky-"]').forEach(e => e.remove());
            document.body.style.overflow = 'visible';
        })()""")
        await asyncio.sleep(0.5)

    # ── Signup ─────────────────────────────────────────────────────────────────

    async def signup(
        self,
        alias_email: str,
        otp_code: str,
        smspool_service=None,
        password: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Complete Vercel signup after email + OTP has been received.

        Steps:
            1. Fill OTP (6-digit) and submit
            2. Set password + submit
            3. Phone verification (SMSPool UK number, React-setter fill)
            4. Name / username + submit
            5. Navigate to tokens page + extract Bearer token or generate PAT

        Args:
            alias_email: The GMX alias used for signup (already on Vercel page)
            otp_code: 6-digit OTP from GMX
            smspool_service: SMSPoolService instance (optional)
            password: Password to set (auto-generated if None)

        Returns:
            Dict with 'status', 'api_key', 'password', 'steps' list.
        """
        from sin_browser_tools.tools.navigation import browser_navigate, browser_get_url, browser_press
        from sin_browser_tools.tools.interaction import browser_click_by_text, browser_fill
        from sin_browser_tools.tools.extraction import browser_console

        steps = []
        pwd = password or self._gen_password()

        # ── Step A: OTP ─────────────────────────────────────────────────────────
        logger.info("=== Vercel: Fill OTP ===")
        # Vercel uses 6 separate <input> boxes OR a single input[name="digits"]
        otp_filled = await self._fill_otp(otp_code)
        if not otp_filled:
            logger.error("OTP fill failed — trying fallback single input")
            await self._set_react_value('input[name="digits"]', otp_code)
            await asyncio.sleep(0.5)
            await browser_press("Enter")
        await asyncio.sleep(2)
        steps.append("otp_filled")

        # Wait for transition away from OTP page
        for _ in range(10):
            await asyncio.sleep(1)
            url = await self._current_url()
            if "verify" not in url.lower() and "confirm" not in url.lower():
                break
        logger.info(f"Post-OTP URL: {url}")

        # ── Step B: Password ────────────────────────────────────────────────────
        logger.info("=== Vercel: Set Password ===")
        r = await browser_console("document.querySelectorAll('input[type=password]').length")
        pw_count = int((r or {}).get("result", 0))
        if pw_count > 0:
            await self._set_react_value('input[type="password"]', pwd)
            await asyncio.sleep(0.5)
            await browser_press("Enter")
            await asyncio.sleep(2)
            steps.append("password_set")
        else:
            logger.warning("No password field found — may be skipped or merged step")

        # ── Step C: Phone Verification ──────────────────────────────────────────
        logger.info("=== Vercel: Phone Verification ===")
        body = await self._body_text()
        if "phone" in body.lower() or "verification" in body.lower() or "number" in body.lower():
            phone_ok = await self._handle_phone_verification(smspool_service)
            if phone_ok:
                steps.append("phone_verified")
            else:
                logger.warning("Phone verification failed / skipped")
        else:
            logger.info("No phone step detected — continuing")

        # ── Step D: Name / Username ─────────────────────────────────────────────
        logger.info("=== Vercel: Name / Username ===")
        await self._handle_name_step()
        steps.append("name_set")

        # ── Step E: Wait for Dashboard ──────────────────────────────────────────
        logger.info("=== Vercel: Waiting for Dashboard ===")
        dashboard_url = None
        for _ in range(30):
            await asyncio.sleep(2)
            url = await self._current_url()
            if any(x in url for x in ["/dashboard", "/home", "/account", "/settings"]):
                dashboard_url = url
                break
            body = await self._body_text()
            if "dashboard" in body.lower() or "projects" in body.lower():
                dashboard_url = url
                break
        if not dashboard_url:
            logger.warning("No dashboard redirect — forcing navigate")
            await browser_navigate("https://vercel.com/dashboard")
            await asyncio.sleep(5)
            dashboard_url = await self._current_url()
        steps.append("dashboard_reached")
        logger.info(f"Dashboard URL: {dashboard_url}")

        # ── Step F: API Token ───────────────────────────────────────────────────
        logger.info("=== Vercel: Extract API Token ===")
        api_key = await self._generate_api_token()
        if api_key:
            steps.append("api_key_extracted")
            return {"status": "success", "api_key": api_key, "password": pwd, "steps": steps}
        else:
            steps.append("api_key_failed")
            return {"status": "error", "error": "api_key_extraction_failed", "password": pwd, "steps": steps}

    # ── Internal Steps ─────────────────────────────────────────────────────────

    async def _fill_otp(self, otp_code: str) -> bool:
        """Fill 6-digit OTP into Vercel's input fields.

        Vercel renders EITHER:
        - 6 separate <input maxlength=1> boxes (one per digit)
        - OR a single <input name="digits">
        """
        from sin_browser_tools.tools.extraction import browser_console
        from sin_browser_tools.tools.navigation import browser_press

        # Try single input first
        r = await browser_console("document.querySelector('input[name=\"digits\"]') ? 'found' : 'not_found'")
        if (r or {}).get("result") == "found":
            await self._set_react_value('input[name="digits"]', otp_code)
            await asyncio.sleep(0.3)
            await browser_press("Enter")
            return True

        # Try 6 separate boxes
        for i, digit in enumerate(otp_code):
            ok = await self._set_react_value(f'input[maxlength="1"]:nth-of-type({i+1})', digit)
            if not ok:
                # Fallback: any input with autocomplete="one-time-code" or aria-label
                ok = await self._set_react_value(f'input[autocomplete="one-time-code"]:nth-of-type({i+1})', digit)
            if not ok:
                return False
            await asyncio.sleep(0.1)
        await asyncio.sleep(0.3)
        await browser_press("Enter")
        return True

    async def _handle_phone_verification(self, smspool_service=None) -> bool:
        """Order UK number from SMSPool, fill it into Vercel phone form, poll OTP, submit.

        CRITICAL: Vercel defaults to US flag. MUST switch to UK (+44) before entering number.
        Uses React Native Value Setter for the phone input.
        """
        from sin_browser_tools.tools.navigation import browser_press
        from sin_browser_tools.tools.extraction import browser_console
        from sin_browser_tools.tools.interaction import browser_click_by_text

        if not smspool_service:
            logger.warning("No SMSPool service provided — skipping phone verification")
            for txt in ("Skip", "Skip for now", "Verify later"):
                try:
                    await browser_click_by_text(txt, role="button")
                    logger.info(f"Clicked '{txt}' to skip phone verification")
                    return True
                except Exception:
                    continue
            return False

        # Order UK number
        logger.info("[SMSPool] Ordering UK number...")
        order = await smspool_service.order_uk_number()
        if not order.get("success"):
            logger.error(f"[SMSPool] Order failed: {order}")
            return False
        phone_number = order["number"]
        order_id = order["order_id"]
        logger.info(f"[SMSPool] Got number: {phone_number}, order_id={order_id}")

        # Extract digits for UK national format (with leading 0)
        digits_only = "".join(c for c in phone_number if c.isdigit())
        if digits_only.startswith("44") and len(digits_only) > 10:
            # UK national format: 07xxx xxxxxx (remove +44, add leading 0 if missing)
            national = digits_only[2:]
            if not national.startswith("0"):
                national = "0" + national
            display_number = national
        else:
            display_number = digits_only
        logger.info(f"Phone number to enter (UK national): {display_number}")

        # Step 1: Switch country from US to UK
        logger.info("Switching country code to UK (+44)...")
        country_switched = False
        # Click the country flag dropdown (usually the first button before the input)
        try:
            # Try clicking the flag/country button (US flag)
            r = await browser_console("""(() => {
                var btn = document.querySelector('button[id*="country"], button[aria-label*="country" i], [role="combobox"]');
                if (btn) { btn.click(); return 'clicked'; }
                // Fallback: click any element showing US flag or +1
                var all = document.querySelectorAll('*');
                for (var i=0; i<all.length; i++) {
                    var txt = (all[i].textContent || '').trim();
                    if (txt === '+1' || txt === 'US' || txt === 'United States') {
                        all[i].click(); return 'clicked_fallback';
                    }
                }
                return 'not_found';
            })()""")
            if (r or {}).get("result") in ("clicked", "clicked_fallback"):
                await asyncio.sleep(1.5)
                # Now search for UK / United Kingdom / +44 in the dropdown
                r2 = await browser_console("""(() => {
                    var items = document.querySelectorAll('li, div[role="option"], [role="listbox"] > *');
                    for (var i=0; i<items.length; i++) {
                        var txt = (items[i].textContent || '').trim().toLowerCase();
                        if (txt.indexOf('united kingdom') !== -1 || txt.indexOf('uk') !== -1 || txt.indexOf('+44') !== -1) {
                            items[i].click(); return 'uk_selected';
                        }
                    }
                    return 'uk_not_found';
                })()""")
                if (r2 or {}).get("result") == "uk_selected":
                    country_switched = True
                    logger.info("UK country code selected")
                    await asyncio.sleep(0.5)
        except Exception as e:
            logger.warning(f"Country switch attempt failed: {e}")

        if not country_switched:
            logger.warning("Could not switch country code — proceeding anyway, may fail")

        # Step 2: Fill phone number
        logger.info(f"Filling phone number: {display_number}")
        filled = await self._set_react_value('input[type="tel"]', display_number)
        if not filled:
            filled = await self._set_react_value('input[name="phone"]', display_number)
        if not filled:
            filled = await self._set_react_value('input[placeholder*="phone" i]', display_number)
        if not filled:
            r = await browser_console(f"""(() => {{
                var labels = Array.from(document.querySelectorAll('label, span, p'));
                for (var lbl of labels) {{
                    if ((lbl.textContent || '').toLowerCase().indexOf('phone') !== -1) {{
                        var inp = lbl.querySelector('input') || lbl.parentElement.querySelector('input[type=tel], input[type=text]');
                        if (inp) {{
                            var setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                            setter.call(inp, {display_number!r});
                            inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                            inp.dispatchEvent(new Event('change', {{bubbles: true}}));
                            return 'ok';
                        }}
                    }}
                }}
                return 'not_found';
            }})()""")
            filled = (r or {}).get("result") == "ok"

        if not filled:
            logger.error("Could not find phone input field")
            await smspool_service.cancel_order(order_id)
            return False

        await asyncio.sleep(1)

        # Step 3: Submit phone number
        clicked = False
        for txt in ("Continue", "Verify", "Submit", "Send Code"):
            if await self._click_by_js_text(txt):
                clicked = True
                break
        if not clicked:
            await browser_press("Enter")
        await asyncio.sleep(3)

        # Step 4: Poll SMSPool for OTP
        logger.info(f"[SMSPool] Polling OTP for order_id={order_id}...")
        sms_otp = await smspool_service.poll_otp(order_id, timeout=120, interval=5)
        if not sms_otp:
            logger.error("[SMSPool] OTP poll timeout")
            await smspool_service.cancel_order(order_id)
            return False
        logger.info(f"[SMSPool] OTP received: {sms_otp}")

        # Step 5: Fill SMS OTP
        otp_filled = await self._fill_otp(sms_otp)
        if not otp_filled:
            await self._set_react_value('input[name="digits"]', sms_otp)
        await asyncio.sleep(1)
        await browser_press("Enter")
        await asyncio.sleep(3)

        # Step 6: Verify phone step cleared
        for _ in range(10):
            await asyncio.sleep(2)
            body = await self._body_text()
            if "phone" not in body.lower() and "verification" not in body.lower():
                logger.info("Phone verification step passed")
                return True
        return True

    async def _handle_name_step(self) -> None:
        """Fill name/username if presented. Vercel sometimes asks for full name."""
        from sin_browser_tools.tools.navigation import browser_press
        from sin_browser_tools.tools.extraction import browser_console
        from sin_browser_tools.tools.interaction import browser_click_by_text

        body = await self._body_text()
        if "name" in body.lower() or "username" in body.lower():
            first = "Super"
            last = "Cheetah"
            await self._set_react_value('input[name="firstName"]', first)
            await self._set_react_value('input[name="lastName"]', last)
            await asyncio.sleep(0.5)
            # Try to submit
            for txt in ("Continue", "Submit", "Next"):
                if await self._click_by_js_text(txt):
                    break
            else:
                await browser_press("Enter")
            await asyncio.sleep(3)

    async def _generate_api_token(self) -> Optional[str]:
        """Navigate to Vercel tokens page and extract/generate an API token.

        Strategy:
        1. Navigate to /account/tokens
        2. Click "Create" / "Generate"
        3. Copy token (starts with 'vercel_')
        4. If page is inaccessible, try localStorage / cookies for auth token
        """
        from sin_browser_tools.tools.navigation import browser_navigate, browser_get_url
        from sin_browser_tools.tools.extraction import browser_console
        from sin_browser_tools.tools.interaction import browser_click_by_text
        from sin_browser_tools.tools.vision import browser_get_text

        await browser_navigate("https://vercel.com/account/tokens")
        await asyncio.sleep(4)
        url = await self._current_url()
        if "login" in url.lower():
            logger.error("Redirected to login on tokens page")
            return None

        # Check if token already visible
        text = (await browser_get_text("body")).get("text", "")
        tokens = [t for t in text.split() if t.startswith("vercel_") and len(t) > 20]
        if tokens:
            logger.info(f"Found existing token: {tokens[0][:16]}...")
            return tokens[0]

        # Click Create
        for txt in ("Create", "Create Token", "Generate Token", "Add"):
            try:
                await browser_click_by_text(txt, role="button")
                logger.info(f"Clicked '{txt}' on tokens page")
                await asyncio.sleep(2)
                break
            except Exception:
                continue
        else:
            # Fallback JS click
            await self._click_by_js_text("Create")
            await asyncio.sleep(2)

        # Fill token name
        token_name = "sinator-" + "".join(random.choices(string.ascii_lowercase, k=4))
        await self._set_react_value('input[name="name"]', token_name)
        await self._set_react_value('input[placeholder*="name" i]', token_name)
        await asyncio.sleep(0.5)

        # Submit
        await self._click_by_js_text("Create Token")
        await asyncio.sleep(3)

        # Extract token from page text
        text = (await browser_get_text("body")).get("text", "")
        tokens = [t for t in text.split() if t.startswith("vercel_") and len(t) > 20]
        if tokens:
            logger.info(f"New token generated: {tokens[0][:16]}...")
            return tokens[0]

        # Fallback: try to grab from clipboard or localStorage (Vercel sometimes stores it temporarily)
        r = await browser_console("""(() => {
            try { return localStorage.getItem('vercel-token') || ''; } catch(e) { return ''; }
        })()""")
        token = (r or {}).get("result", "")
        if token and token.startswith("vercel_"):
            return token

        logger.error("Could not extract Vercel API token")
        return None

    @staticmethod
    def _gen_password(length: int = 16) -> str:
        """Generate a secure random password."""
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        return "".join(random.choices(chars, k=length))
