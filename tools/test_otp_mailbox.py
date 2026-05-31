#!/usr/bin/env python3
"""Test: MailCheck Extension OTP + Frame-Traversal auf aktuellen Posteingang."""
import sys, asyncio, logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "agent_toolbox" / "core"))

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("test_otp")

async def main():
    from gmx_service import GmxService
    from playwright.async_api import async_playwright

    CDP_PORT = 9222  # Existing Chrome with GMX session

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
        gmx = GmxService()
        await gmx.initialize_architecture(browser)

        # Login auf work_tab
        logger.info("=== GMX Login ===")
        logged_in = await gmx._login(gmx.work_tab, email="delqhi@gmx.de", password="ZOE.jerry2024")
        logger.info(f"Login: {'✅' if logged_in else '⚠️'}")

        # inbox_tab zum Posteingang navigieren
        ok = await gmx.navigate_inbox()
        logger.info(f"Inbox: {'✅' if ok else '❌'}")

        # ── TEST 1: Frame-Traversal auf inbox_tab ──
        logger.info("\n=== TEST 1: read_otp_axtree_and_frames() ===")
        otp = await gmx.read_otp_axtree_and_frames(sender_keyword="fireworks", timeout=30)
        logger.info(f"OTP Result: {otp}")

        # ── TEST 2: MailCheck Extension ──
        logger.info("\n=== TEST 2: read_fireworks_verification_email() ===")
        verify_url = await gmx.read_fireworks_verification_email(cdp_port=CDP_PORT)
        logger.info(f"Verify URL: {verify_url}")

        # ── Dump inbox_tab Inhalt für Debug ──
        logger.info("\n=== Dump inbox_tab page content (first 3000 chars) ===")
        content = await gmx.inbox_tab.content()
        logger.info(f"Page content ({len(content)} chars):")
        print(content[:3000])

        logger.info("\n=== Dump inbox_tab innerText (first 2000 chars) ===")
        inner = await gmx.inbox_tab.evaluate("() => document.body.innerText")
        print(inner[:2000])

        await browser.close()

asyncio.run(main())
