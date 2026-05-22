"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           SINATOR AGENT-TOOLBOX — Rotation Routes (V6 Playwright+CUA)       ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ENDPOINT:                                                                    ║
║  POST /rotation/full         → Komplette Account-Rotation (GMX + Fireworks) ║
║                                                                              ║
║  FLOW (V6 — 2026-05-22):                                                     ║
║  0. GMX Login built-in (Playwright, Step 0 in rotate.py)                     ║
║  1. GMX Session via Playwright + 15s SID Polling + IAC Tab Cleanup           ║
║  2. GMX Alias Rotation via Playwright (iframe delete + create)               ║
║  3. Fireworks Signup via Playwright + CUA                                    ║
║  4. GMX OTP Email via MailCheck Extension + CDP OOPIF                        ║
║  5. Fireworks Login + Onboarding (Playwright + CUA + Playwright-Fallback)    ║
║  6. API Key via PopUpButton + menuitem (V6: disabled-Wait + DOM-Polling)     ║
║  7. Save to pool                                                             ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import time
import logging
import asyncio
import re
from typing import Optional

from fastapi import APIRouter, HTTPException

from agent_toolbox.core.browser_manager import get_browser_manager
from agent_toolbox.core.gmx_service import GmxService
from agent_toolbox.core.pool_manager import get_pool_manager
from agent_toolbox.api.schemas import RotationRequest, RotationResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rotation", tags=["Account Rotation"])

GMX_ALIAS_API_URL = "http://localhost:8001"


def _require_browser():
    browser_mgr = get_browser_manager()
    if not browser_mgr.is_running:
        raise HTTPException(status_code=400, detail="Browser nicht gestartet. POST /browser/start zuerst aufrufen.")
    return browser_mgr.cdp_port


async def _gmx_rotate(alias_name: Optional[str] = None) -> str:
    """GMX Alias Rotation via GmxService (Playwright iframe). Returns alias_email."""
    svc = GmxService()
    result = await svc.rotate_alias(new_alias_name=alias_name, cdp_port=9222)
    if result.get('status') == 'success':
        return result.get('created_alias')
    raise RuntimeError(f"GMX rotation failed: {result.get('error', 'unknown')}")


async def _fireworks_login(email: str, password: str) -> bool:
    """Fireworks Login + Onboarding + API Key via Playwright+CUA.
    Returns True if login successful (account home reached)."""
    import json
    import subprocess
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        page = await browser.contexts[0].new_page()
        
        # Login via /login → Email Login
        await page.goto("https://app.fireworks.ai/login")
        await asyncio.sleep(4)
        try: await page.locator('button:has-text("Accept All")').first.click(force=True, timeout=5000); await asyncio.sleep(2)
        except: pass
        
        await page.locator('a:has-text("Email Login")').first.click()
        await asyncio.sleep(4)
        
        await page.locator('input[name="email"]').first.fill(email)
        await page.locator('input[name="password"]').first.fill(password)
        
        for btn in await page.locator('button[type="submit"]').all():
            if 'Next' in (await btn.text_content() or ''):
                await btn.click(); await asyncio.sleep(5)
                break
        
        if 'onboarding' in page.url:
            logger.info("Onboarding needed — completing via CUA...")
            # Find CUA window
            res = subprocess.run(["cua-driver", "call", "list_windows"],
                capture_output=True, text=True, timeout=10,
                input=json.dumps({"query": "Chrome"}))
            for w in json.loads(res.stdout).get('windows', []):
                if 'Google Chrome' == w.get('app_name','') and w.get('is_on_screen') and 'Fireworks' in w.get('title',''):
                    pid, wid = w['pid'], w['window_id']
                    # Fill names
                    for el_idx in [124, 128]:
                        subprocess.run(["cua-driver", "call", "click"],
                            capture_output=True, text=True, timeout=10,
                            input=json.dumps({"pid": pid, "window_id": wid, "element_index": el_idx}))
                        await asyncio.sleep(0.3)
                        text_val = "Super" if el_idx == 124 else "Cheetah"
                        subprocess.run(["cua-driver", "call", "type_text"],
                            capture_output=True, text=True, timeout=5,
                            input=json.dumps({"pid": pid, "text": text_val}))
                        await asyncio.sleep(0.3)
                    # Terms checkbox + Continue
                    subprocess.run(["cua-driver", "call", "click"],
                        capture_output=True, text=True, timeout=10,
                        input=json.dumps({"pid": pid, "window_id": wid, "element_index": 129}))
                    await asyncio.sleep(0.3)
                    subprocess.run(["cua-driver", "call", "click"],
                        capture_output=True, text=True, timeout=10,
                        input=json.dumps({"pid": pid, "window_id": wid, "element_index": 137}))
                    await asyncio.sleep(6)
                    # Use-case + credits
                    for uc_idx in [112, 115, 145, 151]:
                        subprocess.run(["cua-driver", "call", "click"],
                            capture_output=True, text=True, timeout=5,
                            input=json.dumps({"pid": pid, "window_id": wid, "element_index": uc_idx}))
                        await asyncio.sleep(0.2)
                    subprocess.run(["cua-driver", "call", "click"],
                        capture_output=True, text=True, timeout=10,
                        input=json.dumps({"pid": pid, "window_id": wid, "element_index": 160}))
                    await asyncio.sleep(6)
                    break
        
        return 'home' in page.url or 'account' in page.url


async def _fireworks_api_key(key_name: str = "sinator-key") -> Optional[str]:
    """Create Fireworks API Key via Playwright. Returns fw_ key or None."""
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        for pg in browser.contexts[0].pages:
            if 'fireworks' in pg.url and ('home' in pg.url or 'account' in pg.url):
                await pg.goto("https://app.fireworks.ai/settings/users/api-keys")
                await asyncio.sleep(5)
                
                # Click Create API Key (PopUpButton)
                for btn in await pg.locator('button').all():
                    if 'Create API Key' == (await btn.text_content() or '').strip():
                        await btn.click(force=True); await asyncio.sleep(2)
                        break
                
                # Click API Key menu item
                await pg.locator('[role="menuitem"]:has-text("API Key")').first.click(force=True)
                await asyncio.sleep(3)
                
                # Fill name
                for inp in await pg.locator('input').all():
                    if 'name' in (await inp.get_attribute('name') or '').lower():
                        await inp.fill(key_name); break
                
                # Generate
                for btn in await pg.locator('button').all():
                    if 'Generate' in (await btn.text_content() or '').strip():
                        await btn.click(force=True); await asyncio.sleep(5)
                        break
                
                # Extract key
                content = await pg.content()
                text = await pg.evaluate("() => document.body.innerText")
                keys = re.findall(r'fw_[a-zA-Z0-9]{20,}', content + text)
                if keys: return keys[0]
        
        return None


@router.post("/full", response_model=RotationResponse)
async def full_rotation(request: RotationRequest):
    """
    KOMPLETTE Account-Rotation — V6 Playwright+CUA (2026-05-22).

    Flow:
    1. GMX Alias via Playwright iframe (delete existing + create new)
    2. Fireworks Login + Onboarding via Playwright + CUA
    3. API Key via PopUpButton + menuitem
    4. Save to pool
    """
    t0 = time.time()
    _require_browser()
    steps_completed = []
    steps_failed = []

    gmx_alias = None
    fireworks_account = None
    api_key = None
    api_key_name = None

    try:
        # ═══ STEP 1: GMX Alias Rotation via Playwright ═══
        logger.info("=== GMX Alias Rotation (Playwright) ===")
        try:
            gmx_alias = await _gmx_rotate(request.new_alias_name)
            steps_completed.append("gmx_alias_rotated")
            logger.info(f"✅ GMX Alias: {gmx_alias}")
        except Exception as e:
            steps_failed.append("gmx_alias_rotation_failed")
            return RotationResponse(
                status="failed", gmx_alias=None, fireworks_account=None,
                api_key=None, api_key_name=None,
                steps_completed=steps_completed, steps_failed=steps_failed,
                execution_time=f"{time.time()-t0:.2f}s", error=str(e),
            )
        
        fireworks_account = gmx_alias
        api_key_name = gmx_alias.split("@")[0].split("-")[0] if gmx_alias else "key"

        # ═══ STEP 2: Fireworks Login + Onboarding ═══
        logger.info(f"=== Fireworks Login ({gmx_alias}) ===")
        try:
            logged_in = await _fireworks_login(gmx_alias, request.fireworks_password)
            if logged_in:
                steps_completed.append("fireworks_login")
                logger.info("✅ Fireworks login OK")
            else:
                steps_failed.append("fireworks_login_failed")
        except Exception as e:
            logger.warning(f"⚠️ Fireworks login error: {e}")
            steps_failed.append("fireworks_login_error")

        # ═══ STEP 3: API Key ═══
        logger.info("=== API Key Creation ===")
        try:
            api_key = await _fireworks_api_key(api_key_name)
            if api_key:
                steps_completed.append("api_key_created")
                logger.info(f"✅ API Key: {api_key[:12]}...")
            else:
                steps_failed.append("api_key_creation_failed")
        except Exception as e:
            logger.warning(f"⚠️ API Key error: {e}")
            steps_failed.append("api_key_error")

        # ═══ STEP 4: Save to Pool ═══
        if request.save_to_pool and api_key:
            pool = get_pool_manager()
            pool.add_key(api_key=api_key, alias_email=gmx_alias, key_name=api_key_name)
            steps_completed.append("api_key_saved_to_pool")
            logger.info("✅ Saved to pool")

        elapsed = time.time() - t0
        final_status = "success" if api_key else "partial"

        return RotationResponse(
            status=final_status,
            gmx_alias=gmx_alias,
            fireworks_account=fireworks_account,
            api_key=api_key,
            api_key_name=api_key_name,
            steps_completed=steps_completed,
            steps_failed=steps_failed,
            execution_time=f"{elapsed:.2f}s",
        )

    except Exception as e:
        elapsed = time.time() - t0
        logger.error(f"Rotation failed: {e}")
        return RotationResponse(
            status="error", gmx_alias=gmx_alias, fireworks_account=fireworks_account,
            api_key=api_key, api_key_name=api_key_name,
            steps_completed=steps_completed, steps_failed=steps_failed,
            execution_time=f"{elapsed:.2f}s", error=str(e),
        )