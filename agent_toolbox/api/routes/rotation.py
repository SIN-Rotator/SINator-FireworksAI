"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           SINATOR AGENT-TOOLBOX — Rotation Routes (V8 Playwright+CUA)       ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ENDPOINT:                                                                    ║
║  POST /rotation/full         → Komplette Account-Rotation (GMX + Fireworks) ║
║                                                                              ║
║  FLOW (V8 — 2026-05-22):                                                     ║
║  0. GMX Login built-in (Playwright, Step 0 in rotate.py)                     ║
║  1. GMX Alias: Playwright inbox → CUA Einstellungen → JS hidden-nav          ║
║     → New-Tab allEmailAddresses iframe → delete + create                     ║
║  2. Fireworks Signup via Playwright + CUA                                    ║
║  3. GMX OTP Email via MailCheck Extension + CDP OOPIF                        ║
║  4. Fireworks Login + Onboarding via fireworks_service (CUA+Playwright)      ║
║  5. API Key via fireworks_service.create_api_key() (V8: PopUpButton + DOM)   ║
║  6. Save to pool                                                             ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import time
import logging
import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException

from agent_toolbox.core.browser_manager import get_browser_manager
from agent_toolbox.core.pool_manager import get_pool_manager
from agent_toolbox.api.schemas import RotationRequest, RotationResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rotation", tags=["rotation"])


def _require_browser():
    browser_mgr = get_browser_manager()
    if not browser_mgr.is_running:
        raise HTTPException(status_code=400, detail="Browser nicht gestartet. POST /browser/start zuerst aufrufen.")
    return browser_mgr.cdp_port


async def _gmx_rotate_via_api(alias_name: Optional[str] = None) -> Optional[str]:
    """GMX Alias Rotation via gmx-alias-tool API (localhost:8001)."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post("http://localhost:8001/alias/rotate", json={"alias_name": alias_name or ""})
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success":
                    return data.get("alias_email")
                logger.warning(f"gmx-alias-tool API returned: {data.get('status')} — {data.get('error')}")
            else:
                logger.warning(f"gmx-alias-tool API HTTP {resp.status_code}")
    except Exception as e:
        logger.warning(f"gmx-alias-tool API error: {e}")
    return None


async def _gmx_rotate_fallback(alias_name: Optional[str] = None) -> str:
    """Fallback: direkt via GmxService (Playwright iframe)."""
    from agent_toolbox.core.gmx_service import GmxService
    svc = GmxService()
    result = await svc.rotate_alias(new_alias_name=alias_name, cdp_port=9222)
    if result.get('status') == 'success':
        return result.get('created_alias')
    raise RuntimeError(f"GMX rotation failed: {result.get('error', 'unknown')}")


async def _gmx_rotate(alias_name: Optional[str] = None) -> str:
    """GMX Alias Rotation — API first, fallback to direct."""
    alias = await _gmx_rotate_via_api(alias_name)
    if alias:
        logger.info(f"✅ GMX Alias via API: {alias}")
        return alias
    logger.info("⚠️ gmx-alias-tool API offline, using direct fallback")
    return await _gmx_rotate_fallback(alias_name)


async def _fireworks_login(email: str, password: str) -> bool:
    """Fireworks Login + Onboarding via fireworks_service."""
    from agent_toolbox.core.fireworks_service import login_fireworks
    result = await login_fireworks(email, password)
    return result.get('status') == 'success'


async def _fireworks_api_key(key_name: str = "sinator-key") -> Optional[str]:
    """Create API Key via fireworks_service (V8: PopUpButton + DOM-polling)."""
    from agent_toolbox.core.fireworks_service import create_api_key
    result = await create_api_key(key_name)
    return result.get('api_key')


@router.post("/full", response_model=RotationResponse)
async def full_rotation(request: RotationRequest):
    """
    KOMPLETTE Account-Rotation — V8 Playwright+CUA (2026-05-22).

    Flow:
    1. GMX Alias: Playwright inbox → CUA Einstellungen → JS hidden-nav → New-Tab iframe
    2. Fireworks Login + Onboarding via fireworks_service
    3. API Key via fireworks_service.create_api_key()
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
        # ═══ STEP 1: GMX Alias Rotation ═══
        logger.info("=== GMX Alias Rotation ===")
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
