#!/usr/bin/env python3
"""
SINator - Rotation Tool V19 (SIN-Browser-Tools, 2026-06-01)

Fireworks flow via SIN-Browser-Tools. Bot Chrome bleibt GEÖFFNET bis API Key.
GMX flow in User Chrome (Profile 73, CDP).
OTP polling via User Chrome (GMX session).
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

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "agent_toolbox" / "core"))

logging.basicConfig(level=logging.DEBUG if os.environ.get("LOG_LEVEL") == "DEBUG" else logging.INFO, format='%(message)s')
logger = logging.getLogger("rotate")


def _find_free_port(start: int = 9230) -> int:
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    raise RuntimeError("No free port found")


async def main():
    parser = argparse.ArgumentParser(description="GMX + Fireworks Rotation V19")
    parser.add_argument("alias", nargs="?", help="Optional alias name")
    parser.add_argument("--gmx-email", help="GMX account email (required)")
    parser.add_argument("--gmx-password", help="GMX account password (required)")
    parser.add_argument("--password", help="Fireworks account password (required)")
    parser.add_argument("--save", action="store_true", default=True, help="Save API key to pool")
    parser.add_argument("--cdp-port", type=int, default=0, help="CDP port (0 = chromium.launch)")
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG logging")
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

    # ══════════════════════════════════════════════════════════════════
    # User Chrome (GMX)
    # ══════════════════════════════════════════════════════════════════
    gmx_browser = None
    ctx = None

    if args.cdp_port:
        logger.info(f"=== Connecting to User Chrome on CDP port {args.cdp_port} ===")
        gmx_browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{args.cdp_port}")
        logger.info("Connected to User Chrome")
    else:
        cdp_port = _find_free_port()
        gmx_browser = await p.chromium.launch(
            headless=False,
            args=[f'--remote-debugging-port={cdp_port}']
        )

    fw_mgr = None
    alias = None
    try:
        from gmx_service import GmxService
        gmx = GmxService()

        ctx = await gmx_browser.new_context()
        work_tab = await ctx.new_page()
        gmx.work_tab = work_tab
        gmx.inbox_tab = work_tab
        await work_tab.bring_to_front()

        # Step 0: GMX Login
        logged_in = False
        await work_tab.goto("https://navigator.gmx.net/mail", wait_until="domcontentloaded")
        await asyncio.sleep(3)
        if "navigator.gmx.net/mail" in work_tab.url and "login" not in work_tab.url.lower():
            logger.info("GMX session active in Profile 73")
            logged_in = True
        else:
            logger.info("GMX login via Profile 73")
            logged_in = await gmx._login(work_tab, email=args.gmx_email, password=args.gmx_password)
            if not logged_in:
                logger.error("GMX Login failed")
                return

        sid_match = re.search(r"[?&]sid=([a-f0-9]{40,})", work_tab.url)
        gmx_sid = sid_match.group(1) if sid_match else None
        gmx_work_url = work_tab.url

        # Step 1: GMX Alias Rotation
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

        # ══════════════════════════════════════════════════════════════
        # Bot Chrome (Fireworks) — SIN-Browser-Tools
        # Bleibt GEÖFFNET bis API Key generiert
        # ══════════════════════════════════════════════════════════════
        logger.info("=== Launching Bot Chrome via SIN-Browser-Tools ===")
        from fireworks_service import launch, cleanup_bot, signup_fireworks
        from fireworks_service import verify_account, login_fireworks, create_api_key

        launch_result = await launch()
        fw_mgr = launch_result.get("browser_manager")
        logger.info("Bot Chrome launched and registered with SIN-Browser-Tools")

        # Step 2: Fireworks Signup
        logger.info("=== Fireworks Signup ===")
        signup_result = await signup_fireworks(alias, args.password)
        logger.info(f"Signup: {signup_result.get('status')} - steps: {signup_result.get('steps_completed', [])}")

        # Step 3: OTP Poll (User Chrome)
        logger.info("=== OTP Polling (User Chrome) ===")
        await work_tab.bring_to_front()
        await work_tab.goto(gmx_work_url, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        verify_ok = False
        otp_url = None
        try:
            otp_result = await gmx.read_otp_main_frame_only(sender_keyword="fireworks", timeout=80)
            otp_url = otp_result.get("otp_url")
        except AttributeError:
            logger.info("Fallback to CDP AXTree OTP scanner")
            otp_result = await gmx.read_otp_cdp_axtree(sender_keyword="fireworks", timeout=80)
            otp_url = otp_result.get("otp_url")

        if otp_url:
            logger.info(f"OTP-URL: {otp_url[:60]}")
            verify_ok = await verify_account(otp_url)
            logger.info(f"Verify: {'OK' if verify_ok else 'Failed'}")
        else:
            logger.warning(f"OTP nicht gefunden: {otp_result.get('error')}")

        # Step 4: Login + Onboarding
        logger.info("=== Fireworks Login + Onboarding ===")
        login_result = await login_fireworks(alias, args.password)
        if login_result.get('status') == 'success':
            logger.info(f"Login OK: {login_result.get('steps_completed', [])}")
        else:
            logger.info(f"Login: {login_result.get('status')} - {login_result.get('error', '')}")

        # Step 5: API Key
        logger.info("=== API Key ===")
        key_name = alias.split("@")[0].split("-")[0] if alias else "sinator-key"
        api_result = await create_api_key(key_name=key_name)
        api_key = api_result.get("api_key")

        if not api_key:
            logger.error(f"API Key creation failed: {api_result.get('error')}")
            return

        logger.info(f"API Key: {api_key}")

        # Step 6: Save to pool
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
        if fw_mgr:
            logger.info("Closing Bot Chrome (Fireworks)")
            await cleanup_bot(fw_mgr)
        if gmx_browser:
            logger.info("Disconnecting from User Chrome (GMX)")
            await gmx_browser.close()
        await p.stop()
        logger.info(f"\nROTATION COMPLETE - {elapsed:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
