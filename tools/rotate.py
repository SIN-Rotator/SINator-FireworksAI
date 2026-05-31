#!/usr/bin/env python3
"""
SINator - Rotation Tool V8.2 (2026-05-31) — Multi-Tab Architektur

V8.2:
  - initialize_architecture() erstellt TWO TABS:
    * work_tab → Login, Alias, Fireworks
    * inbox_tab → IMMER im Posteingang geparkt (nie navigiert)
  - OTP via read_otp_axtree_and_frames() auf inbox_tab
  - Session-isoliert: inbox_tab hat nie Session-Vergiftung

Usage:
  python3 tools/rotate.py
  python3 tools/rotate.py my-alias-123
"""
import sys
import os
import asyncio
import time
import logging
import argparse
import socket
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "agent_toolbox" / "core"))

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("rotate")


def _find_free_port(start: int = 9230) -> int:
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    raise RuntimeError("No free port found")


async def _get_or_create_gmx_tab(browser: Browser, url_contains: str = "gmx.net") -> Page:
    """Find existing GMX tab or create new one in the connected Chrome."""
    for ctx in browser.contexts:
        for pg in ctx.pages:
            if url_contains in (pg.url or "") and "about:blank" not in pg.url:
                return pg
    return await browser.new_page()


async def main():
    parser = argparse.ArgumentParser(description="GMX + Fireworks Rotation (V8.2 Multi-Tab)")
    parser.add_argument("alias", nargs="?", help="Optional alias name")
    parser.add_argument("--gmx-email", help="GMX account email (required)")
    parser.add_argument("--gmx-password", help="GMX account password (required)")
    parser.add_argument("--password", help="Fireworks account password (required)")
    parser.add_argument("--save", action="store_true", default=True, help="Save API key to pool")
    parser.add_argument("--cdp-port", type=int, default=0, help="CDP port (0 = chromium.launch)")
    args = parser.parse_args()

    from agent_toolbox.core.config_manager import get_config
    cfg = get_config()
    if not args.gmx_email:
        args.gmx_email = cfg.gmx_email
    if not args.gmx_password:
        args.gmx_password = cfg.gmx_password
    if not args.password:
        args.password = cfg.fireworks_password

    t0 = time.time()

    from playwright.async_api import async_playwright
    p = await async_playwright().start()

    # Verbinden zu laufender Chrome Session (hat GMX Session = Profile 73)
    cdp_url = f"http://localhost:9222"
    logger.info(f"=== Connecting to Chrome at {cdp_url} (Profile 73 — GMX eingeloggt) ===")
    browser = await p.chromium.connect_over_cdp(cdp_url)
    logger.info("✅ Connected to Chrome")

    alias = None
    try:
        from gmx_service import GmxService
        gmx = GmxService()

        # ═══ Multi-Tab Architektur — existierende GMX-Tabs wiederverwenden ═══
        existing_pages = []
        for ctx in browser.contexts:
            existing_pages.extend(ctx.pages)

        # Finde den eingeloggten GMX-Tab (SID + navigator.gmx.net)
        sid_tab = None
        for pg in existing_pages:
            url = pg.url or ""
            if "sid=" in url and "navigator.gmx.net" in url:
                sid_tab = pg
                logger.info(f"Found logged-in GMX tab: {url[:80]}")
                break

        if sid_tab:
            gmx.work_tab = sid_tab
        else:
            logger.warning("No existing GMX tab with SID found!")
            gmx.work_tab = existing_pages[0] if existing_pages else await browser.new_page()

        # inbox_tab: existierenden zweiten GMX-Tab suchen, sonst neuen erstellen
        inbox_tab = None
        for pg in existing_pages:
            url = pg.url or ""
            if pg != sid_tab and "gmx.net" in url and "sid=" in url:
                inbox_tab = pg
                logger.info(f"Found second GMX tab: {url[:80]}")
                break

        if inbox_tab is None:
            logger.warning("Creating new inbox_tab — no GMX cookies!")
            inbox_tab = await browser.new_page()
        gmx.inbox_tab = inbox_tab

        work_tab = gmx.work_tab
        inbox_tab = gmx.inbox_tab
        await work_tab.bring_to_front()
        logger.info(f"work_tab: {work_tab.url[:80]}")
        logger.info(f"inbox_tab: {inbox_tab.url[:80]}")

        # ═══ Step 0: GMX Session-Verifikation ═══
        logger.info("=== GMX Session Verification ===")
        await work_tab.bring_to_front()
        await asyncio.sleep(2)
        body = await work_tab.evaluate("() => document.body.innerText")
        if "Sie sind eingeloggt" in body or "Zum Postfach" in body:
            logger.info("✅ GMX Session bereits aktiv (Profile 73)")
        else:
            logger.info("⚠️ Keine aktive GMX Session — versuche Login")
            logged_in = await gmx._login(work_tab, email=args.gmx_email, password=args.gmx_password)
            if logged_in:
                logger.info("✅ GMX Login OK")
            else:
                logger.info("⚠️ Login fehlgeschlagen — continue trotzdem")

 # inbox_tab ist existierende eingeloggte GMX Page — nur prüfen
        if inbox_tab:
            try:
                url = inbox_tab.url or ""
                logger.info(f"inbox_tab URL: {url[:80]}")
                if "gmx.net" not in url or "navigator.gmx.net/mail" not in url:
                    logger.info("Navigating inbox_tab to mail")
                    await inbox_tab.goto("https://navigator.gmx.net/mail", wait_until="domcontentloaded")
                    await asyncio.sleep(5)
                    if "navigator.gmx.net/mail" not in inbox_tab.url:
                        logger.warning("⚠️ inbox_tab nicht im Posteingang")
            except Exception as e:
                logger.warning(f"⚠️ inbox_tab check fehlgeschlagen: {e}")
                inbox_tab = None
        else:
            inbox_tab = None

        # ═══ Step 1: GMX Alias Rotation auf work_tab ═══
        logger.info("=== GMX Alias Rotation ===")
        result = await gmx.rotate_alias(new_alias_name=args.alias, page=work_tab)
        if result.get('status') not in ('success', 'partial'):
            logger.error(f"❌ GMX rotation failed: {result.get('error')}")
            return
        alias = result.get('created_alias')
        logger.info(f"✅ GMX Alias: {alias} ({result.get('execution_time')})")
        if not alias:
            logger.error("❌ No alias created")
            return

        # ═══ Step 2: Fireworks Signup auf work_tab ═══
        logger.info("=== Fireworks Signup ===")
        from fireworks_service import signup_fireworks
        signup_result = await signup_fireworks(alias, args.password, browser=browser, existing_page=work_tab)
        signup_status = signup_result.get('status')
        logger.info(f"Signup: {signup_status} — {signup_result.get('error', '')}")

        # ═══ Step 3: OTP Poll auf inbox_tab (session-isoliert) ═══
        logger.info("=== OTP Polling (inbox_tab, bis 180s) ===")
        otp_result = await gmx.read_otp_axtree_and_frames(sender_keyword="fireworks", timeout=180)
        otp_url = otp_result.get("otp_url")
        otp_code = otp_result.get("otp_code")

        verify_ok = False
        if otp_url:
            logger.info(f"OTP-URL gefunden: {otp_url[:60]}")
            from fireworks_service import verify_account
            verify_ok = await verify_account(otp_url, browser=browser)
            logger.info(f"Verify via OTP-URL: {'✅ OK' if verify_ok else '⚠️ Failed'}")
        elif otp_code:
            logger.info(f"OTP-Code gefunden: {otp_code}")
        else:
            logger.warning(f"OTP nicht gefunden: {otp_result.get('error')} — versuche read_otp_via_playwright")
            for fallback_attempt in range(10):
                await asyncio.sleep(5)
                # Navigate inbox_tab fresh to handle any consent redirect
                if inbox_tab:
                    try:
                        await inbox_tab.goto("https://navigator.gmx.net/mail", wait_until="networkidle", timeout=15000)
                        await asyncio.sleep(2)
                        # Handle consent if present
                        for consent_btn in ['button:has-text("Alle akzeptieren")', 'button:has-text("Zustimmen")', 'button:has-text("Akzeptieren")']:
                            try:
                                btn = inbox_tab.locator(consent_btn).first
                                if await btn.is_visible(timeout=2000):
                                    await btn.click()
                                    await asyncio.sleep(2)
                                    break
                            except:
                                pass
                    except Exception as e:
                        logger.warning(f"inbox_tab navigate failed: {e}")
                otp_fb = await gmx.read_otp_via_playwright(
                    browser, sender_filter="fireworks", max_retries=1, retry_delay=3,
                    existing_page=inbox_tab
                )
                if otp_fb.get("status") == "success":
                    otp_url = otp_fb.get("otp_url")
                    if otp_url:
                        from fireworks_service import verify_account
                        verify_ok = await verify_account(otp_url, browser=browser)
                        logger.info(f"OTP verify (fallback): {'✅ OK' if verify_ok else '⚠️ Failed'}")
                    break
                logger.info(f"Fallback OTP poll {fallback_attempt+1}/10...")

        # ═══ Step 4: Fireworks Login + Onboarding auf work_tab ═══
        logger.info("=== Fireworks Login + Onboarding ===")
        from fireworks_service import login_fireworks
        login_result = await login_fireworks(alias, args.password, browser=browser)
        if login_result.get('status') == 'success':
            logger.info(f"✅ Login OK: {login_result.get('steps_completed', [])}")
        else:
            logger.info(f"Login: {login_result.get('status')} — {login_result.get('error', '')}")

        # ═══ Step 5: API Key auf work_tab ═══
        logger.info("=== API Key ===")
        from fireworks_service import create_api_key
        key_name = alias.split("@")[0].split("-")[0] if alias else "sinator-key"
        api_result = await create_api_key(key_name=key_name, browser=browser)
        api_key = api_result.get("api_key")

        if not api_key:
            logger.error(f"❌ API Key creation failed: {api_result.get('error')}")
            return

        logger.info(f"✅ API Key: {api_key}")

        # ═══ Step 6: Save to pool ═══
        if args.save:
            try:
                from pool_manager import PoolManager
                pool = PoolManager()
                pool.add_key(api_key=api_key, alias_email=alias, key_name=key_name)
                logger.info(f"✅ Saved to pool ({pool.get_stats()['total']} keys total)")
            except Exception as e:
                logger.warning(f"Pool save skipped: {e}")

    finally:
        elapsed = time.time() - t0
        logger.info("=== Shutdown ===")
        await browser.close()
        await p.stop()
        logger.info(f"\n🎉 ROTATION COMPLETE — {elapsed:.1f}s")
        if alias:
            logger.info(f" Alias: {alias}")


if __name__ == "__main__":
    asyncio.run(main())
