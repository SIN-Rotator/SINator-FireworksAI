#!/usr/bin/env python3
"""
SINator - Rotation Tool V9.0 (CEO-Review Fixes, 2026-06-01)
Docs: rotate.doc.md

V9.0 CEO-Fixes:
  - Session Persistence via storage_state (0.1s Login statt 30s)
  - Main-Frame-Only OTP Scanner (keine 62 Ad-iFrames)
  - React-kompatibles Fireworks Onboarding
  - Network Interception fuer Signup-Confirmation

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
import re
from pathlib import Path

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from playwright.async_api import Browser, Page

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "agent_toolbox" / "core"))

logging.basicConfig(level=logging.DEBUG if os.environ.get("LOG_LEVEL") == "DEBUG" else logging.INFO, format='%(message)s')
logger = logging.getLogger("rotate")

# Session storage paths
SESSION_DIR = Path(__file__).parent.parent / "data" / "sessions"
GMX_SESSION_FILE = SESSION_DIR / "gmx_session.json"


def _find_free_port(start: int = 9230) -> int:
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    raise RuntimeError("No free port found")


async def main():
    parser = argparse.ArgumentParser(description="GMX + Fireworks Rotation (V9.0 CEO-Fixes)")
    parser.add_argument("alias", nargs="?", help="Optional alias name")
    parser.add_argument("--gmx-email", help="GMX account email (required)")
    parser.add_argument("--gmx-password", help="GMX account password (required)")
    parser.add_argument("--password", help="Fireworks account password (required)")
    parser.add_argument("--save", action="store_true", default=True, help="Save API key to pool")
    parser.add_argument("--cdp-port", type=int, default=0, help="CDP port (0 = chromium.launch)")
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG logging")
    parser.add_argument("--no-session", action="store_true", help="Disable session persistence")
    args = parser.parse_args()
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        for h in logging.getLogger().handlers:
            h.setLevel(logging.DEBUG)

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

    browser = None
    ctx = None
    
    if args.cdp_port:
        logger.info(f"=== Connecting to Chrome on CDP port {args.cdp_port} ===")
        browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{args.cdp_port}")
        logger.info("Connected to existing Chrome")
    else:
        cdp_port = _find_free_port()
        logger.info(f"=== Launching Bot Chromium (CDP port {cdp_port}) ===")
        browser = await p.chromium.launch(
            headless=False,
            args=[f'--remote-debugging-port={cdp_port}']
        )
        logger.info("Bot Chromium launched")

    alias = None
    try:
        from gmx_service import GmxService
        gmx = GmxService()

        # ══════════════════════════════════════════════════════════════════
        # CEO-FIX: Session Persistence (0.1s Login statt 30s)
        # ══════════════════════════════════════════════════════════════════
        
        session_loaded = False
        if not args.no_session and GMX_SESSION_FILE.exists():
            logger.info("=== Loading GMX Session (CEO-Fix: 0.1s Login) ===")
            try:
                ctx = await browser.new_context(storage_state=str(GMX_SESSION_FILE))
                session_loaded = True
                logger.info(f"Session loaded from {GMX_SESSION_FILE}")
            except Exception as e:
                logger.warning(f"Session load failed: {e}")
                ctx = await browser.new_context()
        else:
            ctx = await browser.new_context()
        
        # Create tabs
        work_tab = await ctx.new_page()
        inbox_tab = await ctx.new_page()
        gmx.work_tab = work_tab
        gmx.inbox_tab = inbox_tab

        await work_tab.bring_to_front()
        logger.info(f"work_tab: {work_tab.url[:80]}")
        logger.info(f"inbox_tab: {inbox_tab.url[:80]}")

        # ══════════════════════════════════════════════════════════════════
        # Step 0: GMX Login (oder Session-Restore)
        # ══════════════════════════════════════════════════════════════════
        
        logged_in = False
        if session_loaded:
            # Verify session is still valid
            logger.info("=== Verifying GMX Session ===")
            await work_tab.goto("https://navigator.gmx.net/mail", wait_until="domcontentloaded")
            await asyncio.sleep(3)
            
            if "navigator.gmx.net/mail" in work_tab.url and "login" not in work_tab.url.lower():
                logger.info("Session valid - skipping login")
                logged_in = True
            else:
                logger.info("Session expired - full login required")
        
        if not logged_in:
            logger.info("=== GMX Login ===")
            logged_in = await gmx._login(work_tab, email=args.gmx_email, password=args.gmx_password)
            if logged_in:
                logger.info("GMX Login OK")
                # CEO-FIX: Save session for next run
                if not args.no_session:
                    try:
                        SESSION_DIR.mkdir(parents=True, exist_ok=True)
                        await ctx.storage_state(path=str(GMX_SESSION_FILE))
                        logger.info(f"Session saved to {GMX_SESSION_FILE}")
                    except Exception as e:
                        logger.warning(f"Session save failed: {e}")
            else:
                logger.error("GMX Login failed")
                return

        # Extract SID
        sid_match = re.search(r"[?&]sid=([a-f0-9]{40,})", work_tab.url)
        gmx_sid = sid_match.group(1) if sid_match else None
        gmx_work_url = work_tab.url
        logger.info(f"GMX SID: {gmx_sid[:20] if gmx_sid else 'None'}...")

        # Navigate inbox_tab to GMX
        if gmx_sid:
            await inbox_tab.goto(gmx_work_url, wait_until="domcontentloaded")
            await asyncio.sleep(3)
            
            # Consent handling
            for consent_btn in ['button:has-text("Alle akzeptieren")', 'button:has-text("Zustimmen")']:
                try:
                    btn = inbox_tab.locator(consent_btn).first
                    if await btn.is_visible(timeout=2000):
                        await btn.click()
                        await asyncio.sleep(2)
                        break
                except:
                    pass

        # ══════════════════════════════════════════════════════════════════
        # Step 1: GMX Alias Rotation
        # ══════════════════════════════════════════════════════════════════
        
        logger.info("=== GMX Alias Rotation ===")
        result = await gmx.rotate_alias(new_alias_name=args.alias, page=work_tab)
        if result.get('status') not in ('success', 'partial'):
            logger.error(f"GMX rotation failed: {result.get('error')}")
            return
        alias = result.get('created_alias')
        logger.info(f"GMX Alias: {alias}")
        if not alias:
            logger.error("No alias created")
            return

        # ══════════════════════════════════════════════════════════════════
        # Step 2: Fireworks Signup (mit CEO-Fixes)
        # ══════════════════════════════════════════════════════════════════
        
        logger.info("=== Fireworks Signup ===")
        from fireworks_service import signup_fireworks
        signup_result = await signup_fireworks(alias, args.password, browser=browser, existing_page=work_tab)
        logger.info(f"Signup: {signup_result.get('status')} - steps: {signup_result.get('steps_completed', [])}")

        # ══════════════════════════════════════════════════════════════════
        # Step 3: OTP Poll (CEO-FIX: Main-Frame-Only, keine 62 Ad-iFrames!)
        # ══════════════════════════════════════════════════════════════════
        
        logger.info("=== OTP Polling (CEO-Fix: Main-Frame-Only) ===")
        
        await inbox_tab.bring_to_front()
        await inbox_tab.goto(gmx_work_url, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        # Try CEO-Fixed Main-Frame-Only scanner first
        verify_ok = False
        otp_url = None
        otp_code = None
        
        try:
            otp_result = await gmx.read_otp_main_frame_only(sender_keyword="fireworks", timeout=60)
            otp_url = otp_result.get("otp_url")
            otp_code = otp_result.get("otp_code")
        except AttributeError:
            # Fallback to CDP AXTree if main_frame_only not available
            logger.info("Fallback to CDP AXTree OTP scanner")
            otp_result = await gmx.read_otp_cdp_axtree(sender_keyword="fireworks", timeout=60)
            otp_url = otp_result.get("otp_url")
            otp_code = otp_result.get("otp_code")

        if otp_url:
            logger.info(f"OTP-URL: {otp_url[:60]}")
            from fireworks_service import verify_account
            verify_ok = await verify_account(otp_url, browser=browser)
            logger.info(f"Verify: {'OK' if verify_ok else 'Failed'}")
        elif otp_code:
            logger.info(f"OTP-Code: {otp_code}")
        else:
            logger.warning(f"OTP nicht gefunden: {otp_result.get('error')}")

        # ══════════════════════════════════════════════════════════════════
        # Step 4: Fireworks Login + Onboarding (CEO-Fixed)
        # ══════════════════════════════════════════════════════════════════
        
        logger.info("=== Fireworks Login + Onboarding ===")
        from fireworks_service import login_fireworks
        login_result = await login_fireworks(alias, args.password, browser=browser)
        if login_result.get('status') == 'success':
            logger.info(f"Login OK: {login_result.get('steps_completed', [])}")
        else:
            logger.info(f"Login: {login_result.get('status')} - {login_result.get('error', '')}")

        # ══════════════════════════════════════════════════════════════════
        # Step 5: API Key
        # ══════════════════════════════════════════════════════════════════
        
        logger.info("=== API Key ===")
        from fireworks_service import create_api_key
        key_name = alias.split("@")[0].split("-")[0] if alias else "sinator-key"
        api_result = await create_api_key(key_name=key_name, browser=browser)
        api_key = api_result.get("api_key")

        if not api_key:
            logger.error(f"API Key creation failed: {api_result.get('error')}")
            return

        logger.info(f"API Key: {api_key}")

        # ══════════════════════════════════════════════════════════════════
        # Step 6: Save to pool
        # ══════════════════════════════════════════════════════════════════
        
        if args.save:
            try:
                from pool_manager import PoolManager
                pool = PoolManager()
                pool.add_key(api_key=api_key, alias_email=alias, key_name=key_name)
                logger.info(f"Saved to pool ({pool.get_stats()['total']} keys total)")
            except Exception as e:
                logger.warning(f"Pool save skipped: {e}")

    finally:
        elapsed = time.time() - t0
        logger.info("=== Shutdown ===")
        if browser:
            await browser.close()
        await p.stop()
        logger.info(f"\nROTATION COMPLETE - {elapsed:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
