#!/usr/bin/env python3
"""
SINator — Single Command Rotation Tool V5 (2026-05-21)

GMX Alias Rotation → Fireworks Login → Onboarding → API Key — in einem Lauf.

Usage:
    python tools/rotate.py              # Auto-generated alias
    python tools/rotate.py my-alias-123 # Specific alias name
"""
import sys, asyncio, time, logging, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("rotate")

# Add SINator core to path
sys.path.insert(0, str(Path(__file__).parent.parent / "agent_toolbox" / "core"))


async def main():
    parser = argparse.ArgumentParser(description="GMX + Fireworks Rotation")
    parser.add_argument("alias", nargs="?", help="Optional alias name")
    parser.add_argument("--password", default="ZOE.jerry2024!", help="Fireworks password")
    parser.add_argument("--save", action="store_true", default=True, help="Save API key to pool")
    args = parser.parse_args()

    from pool_manager import PoolManager
    pool = PoolManager()

    t0 = time.time()

    # ═══ Step 0: GMX Session ═══
    logger.info("=== GMX Session ===")
    import re as _re
    from playwright.async_api import async_playwright as _ap
    async with _ap() as _p:
        _b = await _p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        _page = _b.contexts[0].pages[0]
        await _page.goto("https://www.gmx.net/")
        await asyncio.sleep(3)
        
        # Try E-Mail click first (if session exists)
        try:
            await _page.get_by_role("link", name="E-Mail", exact=True).first.click(timeout=5000)
            await asyncio.sleep(5)
            if 'navigator' in _page.url and 'sid=' in _page.url:
                logger.info("✅ GMX Session OK (cookie-based)")
        except:
            # Full login
            logger.info("GMX Login needed...")
            await _page.goto("https://www.gmx.net/mail/login")
            await asyncio.sleep(5)
            for inp in await _page.locator('input').all():
                t = await inp.get_attribute('type') or ''
                if t == 'email': 
                    await inp.fill("opensin@gmx.de")
                    break
            for btn in await _page.locator('button:has-text("Weiter")').all():
                await btn.click(); await asyncio.sleep(5); break
            for inp in await _page.locator('input').all():
                t = await inp.get_attribute('type') or ''
                if t == 'password':
                    await inp.fill("ZOE.jerry2024")
                    break
            for btn in await _page.locator('button:has-text("Login")').all():
                await btn.click(); await asyncio.sleep(6); break
            if 'sid=' in _page.url:
                logger.info("✅ GMX Login OK")

    # ═══ Step 1: GMX Alias Rotation ═══
    logger.info("=== GMX Alias Rotation ===")
    from gmx_service import GmxService
    svc = GmxService()
    result = await svc.rotate_alias(new_alias_name=args.alias, cdp_port=9222)
    if result.get('status') != 'success':
        logger.error(f"❌ GMX rotation failed: {result.get('error')}")
        return
    alias = result.get('created_alias')
    logger.info(f"✅ GMX Alias: {alias} ({result.get('execution_time')})")

    # ═══ Step 2: Fireworks Account (Signup or Login) ═══
    logger.info("=== Fireworks Account ===")
    from fireworks_service import signup_fireworks, login_fireworks
    
    # Try signup first (new account)
    logger.info("Attempting signup...")
    signup_result = await signup_fireworks(alias, args.password)
    
    if signup_result.get('status') == 'success':
        logger.info("✅ Fireworks signup + verify OK")
    else:
        logger.info(f"Signup: {signup_result.get('status')} — trying login")
    
    # Login (works for both new and existing accounts)
    login_result = await login_fireworks(alias, args.password)
    if login_result.get('status') != 'success':
        logger.error(f"❌ Login failed: {login_result.get('error')}")
        return
    logger.info("✅ Fireworks Login + Onboarding OK")

    # ═══ Step 3: API Key ═══
    logger.info("=== API Key ===")
    from fireworks_service import create_api_key
    key_name = alias.split("@")[0].split("-")[0] if alias else "sinator-key"
    key_result = await create_api_key(key_name)
    api_key = key_result.get('api_key')
    if not api_key:
        logger.error("❌ API Key creation failed")
        return
    logger.info(f"✅ API Key: {api_key}")

    # ═══ Step 4: Save to pool ═══
    if args.save:
        pool.add_key(api_key=api_key, alias_email=alias, key_name=key_name)
        logger.info(f"✅ Saved to pool ({pool.get_stats()['total']} keys total)")

    elapsed = time.time() - t0
    logger.info(f"\n🎉 ROTATION COMPLETE — {elapsed:.1f}s")
    logger.info(f"   Alias:   {alias}")
    logger.info(f"   API Key: {api_key}")


if __name__ == "__main__":
    asyncio.run(main())
