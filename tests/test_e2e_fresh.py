"""E2E regression tests for the full rotation flow.

⚠️  These tests interact with real GMX/Fireworks accounts.
     They will create real API keys.

GMX alias ops (rotate_alias, delete/create) depend on CUA and macOS AX,
which are unreliable in test-driven Chromium. They are NOT tested here.
Test them manually via: python tools/rotate.py

Run with:
    rtk test pytest tests/ -v
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "agent_toolbox" / "core"))

import pytest
import asyncio
import logging

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.asyncio

destructive = pytest.mark.destructive


class TestE2ESession:
    """Verify GMX/Fireworks session prerequisites."""

    async def test_chrome_has_gmx_session(self, chrome_ok, browser):
        """Check that Chrome has at least one GMX page or cookie."""
        from playwright.async_api import async_playwright as _ap
        async with _ap() as _p:
            _b = await _p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            found_gmx = any("gmx" in pg.url.lower() for pg in _b.contexts[0].pages)
            if found_gmx:
                print("  ✅ GMX page found in open tabs")
            else:
                cookies = await _b.contexts[0].cookies()
                gmx_cookies = [c for c in cookies if "gmx" in c.get("domain", "")]
                print(f"  GMX cookies: {len(gmx_cookies)}")
                if len(gmx_cookies) == 0:
                    pytest.skip("No GMX session — log in manually first")

    async def test_gmx_email_click(self, chrome_ok, browser, gmx_page):
        """E-Mail link click should establish GMX session (SPA hash URL, not sid=)."""
        await gmx_page.locator('a:has-text("E-Mail")').first.click(timeout=5000)
        await asyncio.sleep(5)
        url = gmx_page.url
        text = await gmx_page.evaluate("() => document.body.innerText")
        assert "gmx" in url, f"Should be on GMX domain: {url[:60]}"
        assert len(text) > 50, f"Body too short: {len(text)} chars"
        print(f"  ✅ GMX session active: {url[:60]} ({len(text)} chars)")

    async def test_fireworks_dashboard(self, chrome_ok, browser, fireworks_page):
        """Fireworks dashboard should be accessible (user is logged in)."""
        url = fireworks_page.url
        text = await fireworks_page.evaluate("() => document.body.innerText")
        print(f"  FW URL: {url[:60]}")
        print(f"  Body: {len(text)} chars")
        assert "fireworks" in url.lower() or "fireworks" in text.lower(), \
            f"Should be on Fireworks domain: {url[:60]}"
        assert len(text) > 200, f"Page too sparse: {len(text)} chars"

    async def test_fireworks_api_keys_url(self, chrome_ok, browser):
        """API Keys page should load."""
        from playwright.async_api import async_playwright as _ap
        async with _ap() as _p:
            _b = await _p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            pg = await _b.contexts[0].new_page()
            await pg.goto("https://app.fireworks.ai/settings/users/api-keys")
            await asyncio.sleep(5)
            content = await pg.content()
            assert len(content) > 500, "API Keys page too short"
            assert "api" in pg.url.lower() or "settings" in pg.url.lower(), \
                f"Not on API Keys page: {pg.url[:60]}"
            print(f"  ✅ API Keys page loaded: {pg.url[:60]}")


@destructive
class TestE2EPlaywright:
    """Fireworks form interaction tests (Playwright only, no CUA).

    GMX alias operations need CUA + real Chrome — test via tools/rotate.py.
    """

    async def _logout_fireworks(self):
        """Clear Fireworks cookies via CDP (scoped to .fireworks.ai)."""
        from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint
        ws = await get_browser_ws_endpoint(9222)
        c = CDPClient(ws)
        await c.connect()
        targets = await c.get_targets()
        for t in targets:
            if t.get("type") == "page":
                sid = await c.attach_to_target(t["targetId"])
                cookies = await c.send_to_session(sid, "Network.getAllCookies")
                for cookie in cookies.get("cookies", []):
                    if "fireworks" in cookie.get("domain", "").lower():
                        await c.send_to_session(sid, "Network.deleteCookies", {
                            "name": cookie["name"],
                            "domain": "." + cookie["domain"].lstrip("."),
                        })
                break
        await c.disconnect()
        from playwright.async_api import async_playwright as _ap
        async with _ap() as _p:
            _b = await _p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            for pg in _b.contexts[0].pages:
                if "fireworks" in pg.url.lower():
                    await pg.close()
            await _b.close()

    async def test_fireworks_signup_form(self, chrome_ok, browser):
        """Fireworks signup form — can fill email + password fields.

        Destructive: logs out of FW, fills form (OTP will fail, OK).
        """
        await self._logout_fireworks()
        from fireworks_service import signup_fireworks
        result = await signup_fireworks("test-verify-999@gmx.de", "TestPass123!")
        print(f"  Signup: {result.get('status')} — steps: {result.get('steps_completed', [])}")
        assert "email_filled" in result.get("steps_completed", []), \
            "Email field should be fillable"

    async def test_fireworks_login_form(self, chrome_ok, browser):
        """Fireworks login form — can reach login page after logout.

        Destructive: logs out of FW, fills login form.
        """
        await self._logout_fireworks()
        from fireworks_service import login_fireworks
        result = await login_fireworks("opensin@gmx.de", "ZOE.jerry2024!")
        print(f"  Login: {result.get('status')} — steps: {result.get('steps_completed', [])}")
        assert "login_page" in result.get("steps_completed", []), \
            "Should reach login page"
