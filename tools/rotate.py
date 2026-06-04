"""
SINator v0+Vercel — Full Rotation Orchestrator
Docs: rotate.doc.md

End-to-End Flow:
  1. Isolierten Chrome starten (temp-Profil, NIE User-Chrome)
  2. GMX Alias rotieren (löschen + erstellen)
  3. Vercel Signup mit Referral-Link (v0.app/ref/6IMSRI)
  4. GMX OTP (6-stellig numerisch) abrufen
  5. SMSPool UK-Nummer für Telefon-Verifizierung
  6. API-Token generieren und extrahieren
  7. In Pool speichern

Usage:
  python tools/rotate.py
"""
import asyncio
import json
import time
import random
import logging
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from sin_browser_tools.core.manager import BrowserManager
from sin_browser_tools.tools.navigation import manager as nav_mgr

# Import our services
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "agent_toolbox" / "core"))
from gmx_service import GmxService, get_gmx_service
from vercel_service import VercelService
from smspool_service import SMSPoolService

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setLevel(logging.DEBUG)
    _formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    _handler.setFormatter(_formatter)
    logger.addHandler(_handler)

# ── Configuration ───────────────────────────────────────────────────────

CDP_PORT = 9222
POOL_FILE = Path(__file__).parent.parent / "data" / "vercel-pool.json"
SMSPOOL_API_KEY = "nKw7Vo0JVNqPGkLSRYkn66KVockWfcoa"  # Set via env var SMSPOOL_API_KEY
GMX_PASSWORD = ""     # Set via env var GMX_PASSWORD


# ── Pool Storage ────────────────────────────────────────────────────────

def load_pool() -> list:
    if POOL_FILE.exists():
        try:
            with open(POOL_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Pool load error: {e}, starting fresh")
    return []


def save_pool(pool: list):
    POOL_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(POOL_FILE, "w") as f:
        json.dump(pool, f, indent=2, default=str)
    logger.info(f"Pool saved: {len(pool)} entries")


def add_to_pool(entry: Dict[str, Any]):
    pool = load_pool()
    entry["id"] = str(uuid.uuid4())
    entry["created_at"] = datetime.now(timezone.utc).isoformat()
    pool.append(entry)
    save_pool(pool)
    logger.info(f"Added to pool: {entry.get('email')} -> key={entry.get('api_key','')[:12]}...")


# ── Main Rotation ───────────────────────────────────────────────────────

async def run_rotation() -> Dict[str, Any]:
    start_time = time.time()
    steps = []

    # Load credentials from env
    import os
    smspool_key = os.environ.get("SMSPOOL_API_KEY", SMSPOOL_API_KEY)
    gmx_password = os.environ.get("GMX_PASSWORD", GMX_PASSWORD)

    if not gmx_password:
        logger.error("GMX_PASSWORD not set — cannot login to GMX")
        return {"status": "failed", "error": "GMX_PASSWORD missing", "steps": steps}

    # Step 0: Start isolated Chrome (temp profile — NEVER touches user Chrome)
    logger.info("=== STEP 0: Start isolated Chrome ===")
    import tempfile
    user_data_dir = tempfile.mkdtemp(prefix="sinator-automation-")
    logger.info(f"Using temp profile: {user_data_dir}")
    mgr = BrowserManager(headless=False, user_data_dir=user_data_dir)
    try:
        await mgr.start_local()
        nav_mgr._set_instance(mgr)
        logger.info(f"Chrome started: {len(mgr._browser.contexts)} context(s)")
        steps.append("chrome_started")
    except Exception as e:
        logger.error(f"Chrome start failed: {e}")
        return {"status": "failed", "error": f"Chrome start: {e}", "steps": steps}

    # Step 1: Initialize GMX Service
    logger.info("=== STEP 1: Initialize GMX Service ===")
    gmx = get_gmx_service(
        browser=mgr._browser,
        context=mgr._context,
        password=gmx_password
    )

    # Initialize multi-tab architecture
    await gmx.initialize_architecture(mgr._browser)
    # Navigate inbox_tab to GMX mail (if already logged in)
    await gmx.inbox_tab.goto("https://navigator.gmx.net/mail", wait_until="domcontentloaded")
    await asyncio.sleep(5)
    steps.append("gmx_initialized")

    # Step 2: Rotate GMX Alias
    logger.info("=== STEP 2: Rotate GMX Alias ===")
    alias_result = await gmx.rotate_alias(page=gmx.work_tab)
    if alias_result.get("status") != "success":
        logger.error(f"Alias rotation failed: {alias_result}")
        await mgr.cleanup()
        return {"status": "failed", "error": f"Alias rotation: {alias_result}", "steps": steps}
    alias_email = alias_result["created_alias"]
    logger.info(f"Alias created: {alias_email}")
    steps.append("alias_rotated")

    # Step 3: Initialize Vercel Service and start signup
    logger.info("=== STEP 3: Vercel Signup ===")
    # Switch active page to a new tab for Vercel
    vercel_tab = await mgr.new_page()
    mgr.set_active_page(vercel_tab)
    vercel = VercelService(manager=mgr)

    # Open referral link and fill email (without OTP yet)
    logger.info("Navigating to referral link and filling email...")
    from sin_browser_tools.tools.navigation import browser_navigate
    from sin_browser_tools.tools.interaction import browser_fill_react, browser_click_by_text, browser_press
    from sin_browser_tools.tools.extraction import browser_get_html

    await browser_navigate("https://v0.app/ref/6IMSRI")
    await asyncio.sleep(5)
    await vercel._handle_cookie_banner()
    await asyncio.sleep(1)

    # Wait for email field and fill
    for _ in range(15):
        html = await browser_get_html()
        if 'type="email"' in str(html).lower() or 'name="email"' in str(html).lower():
            break
        await asyncio.sleep(1)

    await browser_fill_react('input[type="email"]', alias_email)
    await asyncio.sleep(0.5)
    try:
        await browser_click_by_text("Continue with Email", role="button", exact=False)
    except Exception:
        try:
            await browser_click_by_text("Continue", role="button", exact=False)
        except Exception:
            await browser_press("Enter")
    await asyncio.sleep(3)
    steps.append("vercel_email_submitted")

    # Step 4: Read OTP from GMX
    logger.info("=== STEP 4: Read OTP from GMX ===")
    otp_result = await gmx.read_otp(sender_filter="vercel", max_retries=20, retry_delay=5)
    if otp_result.get("status") != "success":
        logger.error(f"OTP read failed: {otp_result}")
        # Try fallback with CDP AXTree
        otp_result = await gmx.read_otp_cdp_axtree(sender_keyword="vercel", timeout=100)
    if otp_result.get("status") != "success":
        logger.error("OTP read failed completely")
        await mgr.cleanup()
        return {"status": "failed", "error": f"OTP: {otp_result}", "steps": steps}
    otp_code = otp_result["otp_code"]
    logger.info(f"OTP received: {otp_code}")
    steps.append("otp_received")

    # Step 5: Complete signup with OTP, password, phone, API key
    logger.info("=== STEP 5: Complete Vercel Signup ===")
    # Switch back to Vercel tab
    mgr.set_active_page(vercel_tab)

    smspool = None
    if smspool_key:
        smspool = SMSPoolService(api_key=smspool_key)
    else:
        logger.warning("SMSPOOL_API_KEY not set — phone verification will be skipped")

    signup_result = await vercel.signup(
        alias_email=alias_email,
        otp_code=otp_code,
        smspool_service=smspool,
        password=None  # auto-generate
    )

    if smspool:
        await smspool.close()

    steps.extend(signup_result.get("steps", []))

    if signup_result.get("status") == "success":
        api_key = signup_result["api_key"]
        password = signup_result.get("password", "")
        logger.info(f"Signup successful! API key: {api_key[:12]}...")
        steps.append("signup_success")

        # Step 6: Save to pool
        logger.info("=== STEP 6: Save to Pool ===")
        add_to_pool({
            "email": alias_email,
            "api_key": api_key,
            "password": password,
            "otp_result": otp_result,
            "signup_result": {k: v for k, v in signup_result.items() if k != "screenshots"},
        })
        steps.append("saved_to_pool")
    else:
        logger.error(f"Signup failed: {signup_result.get('error')}")
        # Still save partial result for debugging
        add_to_pool({
            "email": alias_email,
            "api_key": signup_result.get("api_key"),
            "password": signup_result.get("password", ""),
            "status": signup_result.get("status"),
            "error": signup_result.get("error"),
            "steps": steps,
        })

    elapsed = time.time() - start_time
    logger.info(f"Rotation completed in {elapsed:.1f}s")

    await mgr.cleanup()
    # Clean up temp profile directory
    try:
        import shutil
        if user_data_dir and os.path.exists(user_data_dir):
            shutil.rmtree(user_data_dir, ignore_errors=True)
            logger.info(f"Cleaned up temp profile: {user_data_dir}")
    except Exception as e:
        logger.warning(f"Temp profile cleanup failed (non-critical): {e}")
    return {
        "status": signup_result.get("status"),
        "alias_email": alias_email,
        "api_key": signup_result.get("api_key"),
        "password": signup_result.get("password"),
        "steps": steps,
        "execution_time": f"{elapsed:.1f}s",
    }


if __name__ == "__main__":
    result = asyncio.run(run_rotation())
    print(json.dumps(result, indent=2, default=str))
