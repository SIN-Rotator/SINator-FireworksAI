#!/usr/bin/env python3
"""
SINator - Rotation Tool V8 (2026-05-31) — ONE Browser Flow

V8: Launch ONE chromium with --remote-debugging-port.
GMX connects via CDP (session preserved), Fireworks shares same browser.

Usage:
    python3 tools/rotate.py              # Auto-generated alias
    python3 tools/rotate.py my-alias-123 # Specific alias name
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
    """Find a free TCP port for Chromium CDP."""
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    raise RuntimeError("No free port found")


async def main():
    parser = argparse.ArgumentParser(description="GMX + Fireworks Rotation")
    parser.add_argument("alias", nargs="?", help="Optional alias name")
    parser.add_argument("--gmx-email", default="delqhi@gmx.de", help="GMX account email")
    parser.add_argument("--gmx-password", default="ZOE.jerry2024", help="GMX account password")
    parser.add_argument("--password", default="ZOE.jerry2024!", help="Fireworks account password")
    parser.add_argument("--save", action="store_true", default=True, help="Save API key to pool")
    parser.add_argument("--cdp-port", type=int, default=0, help="CDP port (0 = auto from running Chrome)")
    args = parser.parse_args()

    t0 = time.time()

    # ═══ ONE Browser Startup ═══
    from playwright.async_api import async_playwright
    p = await async_playwright().start()
    
    cdp_port = args.cdp_port or _find_free_port()
    logger.info(f"=== Launching Chromium (CDP port {cdp_port}) ===")
    browser = await p.chromium.launch(
        headless=False,
        args=[f'--remote-debugging-port={cdp_port}']
    )
    logger.info(f"✅ Chromium launched on CDP port {cdp_port}")

    try:
        # ═══ Step 0: GMX Login (connects to SAME Chromium via CDP) ═══
        logger.info("=== GMX Login ===")
        from gmx_service import GmxService
        gmx = GmxService()

        session_check = await gmx.check_session(cdp_port=cdp_port)
        if session_check.get("status") == "logged_in":
            logger.info("✅ Bereits eingeloggt (Session restored)")
        else:
            logger.info("Session not found — login handled by service")

        # ═══ Step 1: GMX Alias Rotation ═══
        logger.info("=== GMX Alias Rotation ===")
        result = await gmx.rotate_alias(new_alias_name=args.alias, cdp_port=cdp_port)
        if result.get('status') != 'success':
            logger.error(f"❌ GMX rotation failed: {result.get('error')}")
            return
        alias = result.get('created_alias')
        logger.info(f"✅ GMX Alias: {alias} ({result.get('execution_time')})")

        # ═══ Step 2: Fireworks Signup (same Chromium, CDP port) ═══
        logger.info("=== Fireworks Signup ===")
        from fireworks_service import signup_fireworks
        signup_result = await signup_fireworks(alias, args.password, cdp_port=cdp_port)
        if signup_result.get('status') == 'success':
            logger.info(f"✅ Fireworks signup OK: {signup_result.get('verify_url', '')[:60]}")
        else:
            logger.info(f"Signup: {signup_result.get('status')} — {signup_result.get('error', '')}")

        # ═══ Step 3: OTP via GMX ═══
        if signup_result.get('verify_url'):
            logger.info("=== Account Verify ===")
            from fireworks_service import verify_account
            verify_ok = await verify_account(signup_result['verify_url'], cdp_port=cdp_port)
            logger.info(f"Verify: {'✅ OK' if verify_ok else '⚠️ Failed'}")

        # ═══ Step 4: OTP Poll via GMX (alternative verify) ═══
        logger.info("=== OTP Polling ===")
        otp_result = await gmx.read_otp(sender_filter="fireworks", cdp_port=cdp_port)
        otp_url = otp_result.get("otp_url")
        if otp_url and not verify_ok:
            logger.info(f"Opening OTP verify URL")
            verify_ok = await verify_account(otp_url, cdp_port=cdp_port)
            logger.info(f"OTP verify: {'✅ OK' if verify_ok else '⚠️ Failed'}")

        # ═══ Step 5: Fireworks Login + Onboarding ═══
        logger.info("=== Fireworks Login + Onboarding ===")
        from fireworks_service import login_fireworks
        login_result = await login_fireworks(alias, args.password, cdp_port=cdp_port)
        if login_result.get('status') == 'success':
            logger.info(f"✅ Login OK: {login_result.get('steps_completed', [])}")
        else:
            logger.info(f"Login: {login_result.get('status')} — {login_result.get('error', '')}")

        # ═══ Step 6: API Key ═══
        logger.info("=== API Key ===")
        from fireworks_service import create_api_key
        key_name = alias.split("@")[0].split("-")[0] if alias else "sinator-key"
        api_result = await create_api_key(key_name=key_name, cdp_port=cdp_port)
        api_key = api_result.get("api_key")

        if not api_key:
            logger.error(f"❌ API Key creation failed: {api_result.get('error')}")
            return

        logger.info(f"✅ API Key: {api_key}")

        # ═══ Step 7: Save to pool ═══
        if args.save:
            try:
                from pool_manager import PoolManager
                pool = PoolManager()
                pool.add_key(api_key=api_key, alias_email=alias, key_name=key_name)
                logger.info(f"✅ Saved to pool ({pool.get_stats()['total']} keys total)")
            except Exception as e:
                logger.warning(f"Pool save skipped: {e}")

    finally:
        logger.info("=== Shutdown ===")
        await browser.close()
        await p.stop()
        elapsed = time.time() - t0
        logger.info(f"\n🎉 ROTATION COMPLETE — {elapsed:.1f}s")
        logger.info(f"   Alias:   {alias}")


if __name__ == "__main__":
    asyncio.run(main())
