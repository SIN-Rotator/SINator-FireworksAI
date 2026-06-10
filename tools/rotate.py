#!/usr/bin/env python3
"""
SINator - Rotation Tool V8.1 (2026-05-31) — TRUE ONE Browser

V8.1: chromium.launch() → _login() auf der page → page an ALLE ops reichen.
Kein CDP mehr — gmx_service._pw_connect() bypassed mit page=page.

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

# FIXED PORT for SINator-FireworksAI Rotation Bot Chrome
# Ephemeral range (49152-65535), extrem unwahrscheinlich belegt
SINATOR_ROTATION_CDP_PORT = 59230

# macOS HDMI/GPU fix: verhindert GPU-Prozess-Reset, der den externen Monitor abstürzen lässt.
_CHROMIUM_GPU_FLAGS = [
    "--disable-gpu",
    "--disable-gpu-compositing",
    "--disable-software-rasterizer",
    "--use-angle=swiftshader",
]


async def main():
    parser = argparse.ArgumentParser(description="GMX + Fireworks Rotation")
    parser.add_argument("alias", nargs="?", help="Optional alias name")
    parser.add_argument("--gmx-email", help="GMX account email (required)")
    parser.add_argument("--gmx-password", help="GMX account password (required)")
    parser.add_argument("--password", help="Fireworks account password (required)")
    parser.add_argument("--save", action="store_true", default=True, help="Save API key to pool")
    parser.add_argument("--cdp-port", type=int, default=SINATOR_ROTATION_CDP_PORT, help=f"CDP port (default: {SINATOR_ROTATION_CDP_PORT}, fixed for SINator)")
    args = parser.parse_args()

    # Fill missing args from config file (backend-only source of truth)
    from agent_toolbox.core.config_manager import get_config
    cfg = get_config()
    if not args.gmx_email:
        args.gmx_email = cfg.gmx_email
    if not args.gmx_password:
        args.gmx_password = cfg.gmx_password
    if not args.password:
        args.password = cfg.fireworks_password

    t0 = time.time()
    cdp_port = args.cdp_port  # ALWAYS use fixed port

    # ═══ ONE Browser Startup ═══
    from playwright.async_api import async_playwright
    p = await async_playwright().start()
    logger.info(f"=== Launching Chromium (CDP port {cdp_port}) ===")
    browser = await p.chromium.launch(
        headless=False,
        args=[f'--remote-debugging-port={cdp_port}'] + _CHROMIUM_GPU_FLAGS
    )
    page = await browser.new_page()
    logger.info(f"✅ Chromium launched — ONE Browser for entire rotation")

    alias = None

    try:
        from gmx_service import GmxService
        gmx = GmxService()

        # ═══ Step 0: GMX Login on this page ═══
        logger.info("=== GMX Login ===")
        logged_in = await gmx._login(page, email=args.gmx_email, password=args.gmx_password)
        if logged_in:
            logger.info("✅ GMX Login OK")
        else:
            logger.info("⚠️ Login may not have completed — continuing anyway")

        # ═══ Step 1: GMX Alias Rotation (same page) ═══
        logger.info("=== GMX Alias Rotation ===")
        result = await gmx.rotate_alias(new_alias_name=args.alias, page=page, email=args.gmx_email, password=args.gmx_password)
        if result.get('status') not in ('success', 'partial'):
            logger.error(f"❌ GMX rotation failed: {result.get('error')}")
            return
        alias = result.get('created_alias')
        logger.info(f"✅ GMX Alias: {alias} ({result.get('execution_time')})")

        if not alias:
            logger.error("❌ No alias created")
            return

        # ═══ Step 2: Fireworks Signup (Playwright page reuse) ═══
        logger.info("=== Fireworks Signup ===")
        from fireworks_service import signup_fireworks
        signup_result = await signup_fireworks(alias, args.password, cdp_port=cdp_port, page=page, browser=browser)
        verify_ok = False
        if signup_result.get('status') == 'success':
            logger.info(f"✅ Fireworks signup OK: {signup_result.get('verify_url', '')[:60]}")
            verify_url = signup_result.get('verify_url')
            if verify_url:
                from fireworks_service import verify_account
                verify_ok = await verify_account(verify_url, cdp_port=cdp_port, page=page, browser=browser)
                logger.info(f"Verify: {'✅ OK' if verify_ok else '⚠️ Failed'}")
        else:
            logger.info(f"Signup: {signup_result.get('status')} — {signup_result.get('error', '')}")

        # ═══ Step 3: OTP Poll (Playwright-native, Shadow-DOM + Multi-Frame Scan) ═══
        logger.info("=== OTP Polling (Playwright-native) ===")
        otp_result = await gmx.read_otp_via_playwright(browser, sender_filter="fireworks", existing_page=page)
        otp_url = otp_result.get("otp_url")
        if otp_url and not verify_ok:
            logger.info(f"Verifying via OTP URL")
            from fireworks_service import verify_account
            verify_ok = await verify_account(otp_url, cdp_port=cdp_port, page=page, browser=browser)
            logger.info(f"OTP verify: {'✅ OK' if verify_ok else '⚠️ Failed'}")

        # ═══ Step 4: Fireworks Login + Onboarding ═══
        logger.info("=== Fireworks Login + Onboarding ===")
        from fireworks_service import login_fireworks
        login_result = await login_fireworks(alias, args.password, cdp_port=cdp_port, page=page, browser=browser)
        if login_result.get('status') == 'success':
            logger.info(f"✅ Login OK: {login_result.get('steps_completed', [])}")
        else:
            logger.info(f"Login: {login_result.get('status')} — {login_result.get('error', '')}")

        # ═══ Step 5: API Key ═══
        logger.info("=== API Key ===")
        from fireworks_service import create_api_key
        key_name = alias.split("@")[0].split("-")[0] if alias else "sinator-key"
        api_result = await create_api_key(key_name=key_name, cdp_port=cdp_port, page=page, browser=browser)
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
            logger.info(f"   Alias:   {alias}")


if __name__ == "__main__":
    asyncio.run(main())
