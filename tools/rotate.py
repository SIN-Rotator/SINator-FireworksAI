#!/usr/bin/env python3
"""
SINator - Rotation Tool V7 (2026-05-28)

Vereinfachte Version: Nutzt GmxService + FireworksService (raw CDP).
Kein Playwright mehr im Haupt-Workflow.

Usage:
    python tools/rotate.py              # Auto-generated alias
    python tools/rotate.py my-alias-123 # Specific alias name
"""
import sys
import os
import asyncio
import time
import logging
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "agent_toolbox" / "core"))

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("rotate")


async def main():
    parser = argparse.ArgumentParser(description="GMX + Fireworks Rotation")
    parser.add_argument("alias", nargs="?", help="Optional alias name")
    parser.add_argument("--gmx-email", default="opensin@gmx.de", help="GMX account email")
    parser.add_argument("--gmx-password", default="ZOE.jerry2024", help="GMX account password")
    parser.add_argument("--password", default="ZOE.jerry2024!", help="Fireworks account password")
    parser.add_argument("--save", action="store_true", default=True, help="Save API key to pool")
    parser.add_argument("--cdp-port", type=int, default=9222, help="CDP port for Chrome")
    args = parser.parse_args()

    t0 = time.time()

    # ═══ Step 0: GMX Login (via Hermes browser_* tools + CDP fallback) ═══
    logger.info("=== GMX Login ===")
    from gmx_service import GmxService
    gmx = GmxService()

    # Prüfe ob bereits eingeloggt
    session_check = await gmx.check_session(cdp_port=args.cdp_port)
    if session_check.get("status") == "logged_in":
        logger.info("✅ Bereits eingeloggt (Session restored)")
    else:
        logger.info("Nicht eingeloggt — GMX Login wird von GmxService._ensure_mail_session beim nächsten Aufruf gehandhabt")

    # ═══ Step 1: GMX Alias Rotation ═══
    logger.info("=== GMX Alias Rotation ===")
    result = await gmx.rotate_alias(new_alias_name=args.alias, cdp_port=args.cdp_port)
    if result.get('status') != 'success':
        logger.error(f"❌ GMX rotation failed: {result.get('error')}")
        return
    alias = result.get('created_alias')
    logger.info(f"✅ GMX Alias: {alias} ({result.get('execution_time')})")

    # ═══ Step 2: Fireworks Signup + OTP ═══
    logger.info("=== Fireworks Signup ===")
    from fireworks_service import signup_fireworks
    signup_result = await signup_fireworks(alias, args.password, cdp_port=args.cdp_port)
    if signup_result.get('status') == 'success':
        logger.info("✅ Fireworks signup + verify OK")
    else:
        logger.info(f"Signup: {signup_result.get('status')} — trying login fallback")

    # ═══ Step 3: Fireworks Login + Onboarding ═══
    logger.info("=== Fireworks Login + Onboarding ===")
    # Login via CDP
    from fireworks_service import FireworksService
    fw = FireworksService()
    client = None
    try:
        client, session_id = await fw._connect(args.cdp_port)
        await client.navigate(session_id, "https://app.fireworks.ai/login")
        await asyncio.sleep(3)
        # Email
        await fw._fill_input(client, session_id, ['input[name="email"]'], alias)
        await fw._fill_input(client, session_id, ['input[type="password"]'], args.password)
        await fw._click_text(client, session_id, ["next", "login", "anmelden"])
        await asyncio.sleep(5)
        # Check URL
        url_res = await client.evaluate(session_id, "window.location.href")
        current_url = url_res.get("result", {}).get("value", "")
        logger.info(f"Post-login URL: {current_url}")

        # Onboarding: Name + Checkboxes
        if "onboarding" in current_url:
            logger.info("Onboarding detected — filling form...")
            await fw._fill_input(client, session_id, ['input[name="firstName"]', 'input[name="first"]'], "Super")
            await fw._fill_input(client, session_id, ['input[name="lastName"]', 'input[name="last"]'], "Cheetah")
            # Terms checkbox
            await client.evaluate(session_id, """
            (function() {
                const cb = document.querySelector('input[type="checkbox"]');
                if (cb && !cb.checked) { cb.click(); return true; }
                return false;
            })()
            """, return_by_value=True)
            await asyncio.sleep(1)
            await fw._click_text(client, session_id, ["continue", "next", "weiter"])
            await asyncio.sleep(3)
            # Use cases
            for uc in ["Prototype", "Flexible", "Conversational", "Search"]:
                await client.evaluate(session_id, f"""
                (function() {{
                    const labels = document.querySelectorAll('label, span, div');
                    for (const el of labels) {{
                        if (el.textContent.includes('{uc}')) {{
                            const cb = el.querySelector('input[type="checkbox"]') || el.previousElementSibling;
                            if (cb && !cb.checked) {{ cb.click(); return true; }}
                        }}
                    }}
                    return false;
                }})()
                """, return_by_value=True)
                await asyncio.sleep(0.5)
            await fw._click_text(client, session_id, ["submit", "get started", "loslegen"])
            await asyncio.sleep(5)
    except Exception as e:
        logger.warning(f"Login/Onboarding error: {e}")
    finally:
        if client:
            await client.disconnect()

    # ═══ Step 4: API Key ═══
    logger.info("=== API Key ===")
    key_name = alias.split("@")[0].split("-")[0] if alias else "sinator-key"
    api_result = await fw.create_api_key(key_name=key_name, cdp_port=args.cdp_port)
    api_key = api_result.get("api_key")

    if not api_key:
        logger.error(f"❌ API Key creation failed: {api_result.get('error')}")
        return

    logger.info(f"✅ API Key: {api_key}")

    # ═══ Step 5: Save to pool ═══
    if args.save:
        try:
            from pool_manager import PoolManager
            pool = PoolManager()
            pool.add_key(api_key=api_key, alias_email=alias, key_name=key_name)
            logger.info(f"✅ Saved to pool ({pool.get_stats()['total']} keys total)")
        except Exception as e:
            logger.warning(f"Pool save skipped: {e}")

    elapsed = time.time() - t0
    logger.info(f"\n🎉 ROTATION COMPLETE — {elapsed:.1f}s")
    logger.info(f"   Alias:   {alias}")
    logger.info(f"   API Key: {api_key}")


if __name__ == "__main__":
    asyncio.run(main())
