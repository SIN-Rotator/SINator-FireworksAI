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
    cdp_port = args.cdp_port or _find_free_port()

    from playwright.async_api import async_playwright
    p = await async_playwright().start()
    logger.info(f"=== Launching Chromium (CDP port {cdp_port}) ===")
    browser = await p.chromium.launch(
        headless=False,
        args=[f'--remote-debugging-port={cdp_port}']
    )
    logger.info("✅ Chromium launched")

    alias = None
    try:
        from gmx_service import GmxService
        gmx = GmxService()

        # ═══ Multi-Tab Architektur ═══
        await gmx.initialize_architecture(browser)
        work_tab = gmx.work_tab
        inbox_tab = gmx.inbox_tab

        # ═══ Step 0: GMX Login auf work_tab ═══
        logger.info("=== GMX Login ===")
        logged_in = await gmx._login(work_tab, email=args.gmx_email, password=args.gmx_password)
        if logged_in:
            logger.info("✅ GMX Login OK")
        else:
            logger.info("⚠️ Login may not have completed — continuing anyway")

 # inbox_tab jetzt zum Posteingang navigieren (Login ist abgeschlossen)
        if inbox_tab:
            try:
                nav_ok = await gmx.navigate_inbox()
                if not nav_ok:
                    logger.warning("⚠️ inbox_tab navigation nicht bestätigt — verwende work_tab für OTP")
                    inbox_tab = None
            except Exception as e:
                logger.warning(f"⚠️ inbox_tab navigation fehlgeschlagen: {e} — verwende work_tab für OTP")
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
        verify_ok = False
        if signup_result.get('status') == 'success':
            logger.info(f"✅ Fireworks signup OK: {signup_result.get('verify_url', '')[:60]}")
            verify_url = signup_result.get('verify_url')
            if verify_url:
                from fireworks_service import verify_account
                verify_ok = await verify_account(verify_url, browser=browser)
                logger.info(f"Verify: {'✅ OK' if verify_ok else '⚠️ Failed'}")
        else:
            logger.info(f"Signup: {signup_result.get('status')} — {signup_result.get('error', '')}")

        # ═══ Step 3: OTP Poll auf inbox_tab (session-isoliert) ═══
        logger.info("=== OTP Polling (inbox_tab, isoliert) ===")
        otp_result = await gmx.read_otp_axtree_and_frames(sender_keyword="fireworks", timeout=120)
        otp_code = otp_result.get("otp_code")
        if otp_code and not verify_ok:
            logger.info(f"OTP-Code gefunden: {otp_code}")
        elif not verify_ok:
            # Fallback: alte read_otp_via_playwright auf inbox_tab
            logger.info("Fallback: read_otp_via_playwright auf inbox_tab")
            otp_result2 = await gmx.read_otp_via_playwright(
                browser, sender_filter="fireworks", max_retries=8, retry_delay=5,
                existing_page=inbox_tab
            )
            otp_url = otp_result2.get("otp_url")
            if otp_url:
                from fireworks_service import verify_account
                verify_ok = await verify_account(otp_url, browser=browser)
                logger.info(f"OTP verify (fallback): {'✅ OK' if verify_ok else '⚠️ Failed'}")

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
