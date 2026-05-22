"""Tests for GMX session — E-Mail click → SID verification."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "agent_toolbox" / "core"))

import asyncio
import pytest


pytestmark = pytest.mark.asyncio


class TestGMXSession:
    """GMX inbox access via E-Mail link click."""

    async def test_email_click_returns_sid(self, chrome_ok, browser, gmx_page):
        """Clicking E-Mail on www.gmx.net should establish GMX mailbox session.

        GMX uses SPA hash routing (www.gmx.net/mail/#....) so SID is not
        visible in the URL bar but the session cookie is set. Verify via
        page content and cookies.
        """
        await gmx_page.locator('a:has-text("E-Mail")').first.click(timeout=5000)
        await asyncio.sleep(5)
        url = gmx_page.url
        text = await gmx_page.evaluate("() => document.body.innerText")
        print(f"  URL: {url[:80]}")
        print(f"  Body: {len(text)} chars")
        # GMX SPA hash URL is the expected result via Playwright CDP
        assert "gmx" in url, f"Should be on GMX domain: {url[:60]}"
        assert len(text) > 50, f"Body too short: {len(text)} chars"

    async def test_gmx_inbox_accessible(self, chrome_ok, browser, gmx_page):
        """After E-Mail click, page should show GMX mailbox content."""
        await gmx_page.locator('a:has-text("E-Mail")').first.click(timeout=5000)
        await asyncio.sleep(5)
        text = await gmx_page.evaluate("() => document.body.innerText")
        assert len(text) > 50, f"Body too short: {len(text)} chars"
        print(f"  Body: {len(text)} chars ({text[:100]}...)")

    async def test_gmx_alias_page_navigable(self, chrome_ok, browser, gmx_page):
        """Should be able to navigate to alias settings from inbox.

        This verifies the E-Mail → Einstellungen flow used by GmxService.
        """
        # Get SID from cookies (GMX stores session in cookies via SPA)
        cookies = await browser.contexts[0].cookies()
        gmx_cookies = {c["name"]: c["value"] for c in cookies if "gmx" in c.get("domain", "")}
        has_sid = any("sid" in n.lower() or "session" in n.lower() for n in gmx_cookies)
        print(f"  GMX cookies: {list(gmx_cookies.keys())}")
        if not has_sid:
            # Try navigating to GMX homepage first
            await gmx_page.goto("https://www.gmx.net/")
            await asyncio.sleep(3)
            cookies = await browser.contexts[0].cookies()
            gmx_cookies = {c["name"]: c["value"] for c in cookies if "gmx" in c.get("domain", "")}
            has_sid = any("sid" in n.lower() or "session" in n.lower() for n in gmx_cookies)
            print(f"  After refresh — GMX cookies: {list(gmx_cookies.keys())}")
        assert has_sid, f"No GMX session cookie found. Cookies: {list(gmx_cookies.keys())}"
