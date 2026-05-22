"""E2E regression tests for the full rotation flow.

⚠️  These tests interact with real GMX/Fireworks accounts.
     They will create real aliases and API keys.

Run with:
    python -m pytest tests/test_e2e_fresh.py -v --capture=no

Skip destructive tests:
    python -m pytest tests/test_e2e_fresh.py -v -k "not destructive"
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "agent_toolbox" / "core"))

import pytest
import asyncio
import logging
import re

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.asyncio

# ── Markers ───────────────────────────────────────────────────────────────────

destructive = pytest.mark.destructive


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestE2ESession:
    """Verify GMX session prerequisites for E2E flow."""

    async def test_chrome_has_gmx_session(self, chrome_ok, browser):
        """Check that Chrome has at least one GMX page or cookie."""
        from playwright.async_api import async_playwright as _ap
        async with _ap() as _p:
            _b = await _p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            found_gmx = any("gmx" in pg.url.lower() for pg in _b.contexts[0].pages)
            if found_gmx:
                print("  ✅ GMX page found in open tabs")
            else:
                # Try cookie check
                cookies = await _b.contexts[0].cookies()
                gmx_cookies = [c for c in cookies if "gmx" in c.get("domain", "")]
                print(f"  GMX cookies: {len(gmx_cookies)}")
                if len(gmx_cookies) == 0:
                    pytest.skip("No GMX session — need to log in manually first")

    async def test_gmx_email_click(self, chrome_ok, browser, gmx_page):
        """E-Mail link click should establish GMX session.

        GMX uses SPA hash routing — SID lives in cookies, not URL bar.
        """
        await gmx_page.locator('a:has-text("E-Mail")').first.click(timeout=5000)
        await asyncio.sleep(5)
        url = gmx_page.url
        text = await gmx_page.evaluate("() => document.body.innerText")
        assert "gmx" in url, f"Should be on GMX domain: {url[:60]}"
        assert len(text) > 50, f"Body too short: {len(text)} chars"
        print(f"  ✅ GMX session active: {url[:60]} ({len(text)} chars)")

    async def test_fireworks_login_page(self, chrome_ok, browser, fireworks_page):
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
class TestE2ERotation:
    """Full E2E rotation tests — these create real aliases and API keys!

    These tests WILL consume GMX alias slots and create Fireworks API keys.
    """

    async def test_gmx_alias_rotate(self, chrome_ok, browser):
        """GMX alias rotation via GmxService (Playwright iframe).

        Destructive: deletes existing alias, creates new one.
        """
        from gmx_service import GmxService
        svc = GmxService()
        result = await svc.rotate_alias(cdp_port=9222)
        assert result.get("status") == "success", \
            f"Rotation failed: {result.get('error')}"
        assert result.get("created_alias"), "No created_alias in result"
        print(f"  ✅ Created: {result['created_alias']}")
        print(f"  ⏱  {result.get('execution_time', '?')}")

    async def test_gmx_alias_create_and_delete(self, chrome_ok, browser):
        """Create → verify → delete a specific alias.

        Destructive: creates and then deletes an alias.
        """
        from gmx_service import GmxService
        svc = GmxService()
        test_name = svc.generate_alias_name()

        # Create
        created = await svc._create_alias_via_playwright(test_name, cdp_port=9222)
        assert created == f"{test_name}@gmx.de", \
            f"Create failed: {created}"
        print(f"  ✅ Created alias: {created}")

        # Delete
        deleted = await svc._delete_alias_via_playwright(created, cdp_port=9222)
        assert deleted, f"Delete failed for {created}"
        print(f"  ✅ Deleted alias: {created}")

    async def test_fireworks_signup_flow(self, chrome_ok, browser):
        """Fireworks signup form should accept input.

        Non-destructive: fills form but relies on existing tests for actual signup.
        This validates the Playwright selectors work.
        """
        from fireworks_service import signup_fireworks
        # Use a dummy email — this will fail at OTP but that's expected
        # We're testing the form interaction, not the full flow
        alias = "test-verify-selector-999@gmx.de"
        result = await signup_fireworks(alias, "TestPass123!")
        print(f"  Signup result status: {result.get('status')}")
        print(f"  Steps: {result.get('steps_completed', [])}")
        # Accept partial (form filled but OTP will fail — no real email sent)
        assert "email_filled" in result.get("steps_completed", []), \
            "Email field should be fillable"

    async def test_fireworks_login_flow(self, chrome_ok, browser):
        """Fireworks login form should work.

        Uses existing credentials from .env or defaults.
        """
        from fireworks_service import login_fireworks
        result = await login_fireworks(
            "opensin@gmx.de",
            "ZOE.jerry2024!"
        )
        print(f"  Login status: {result.get('status')}")
        print(f"  Steps: {result.get('steps_completed', [])}")
        # Login may fail if account doesn't exist — that's OK
        # We're testing that the form interaction doesn't crash
        assert "login_page" in result.get("steps_completed", []), \
            "Should reach login page"
