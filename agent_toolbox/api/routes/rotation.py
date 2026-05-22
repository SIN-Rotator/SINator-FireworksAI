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
import re as _re
from pathlib import Path

from fastapi import APIRouter

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
    # Ensure GMX session before rotation (API route skips rotate.py login)
    await svc.ensure_gmx_session()
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
    KOMPLETTE Account-Rotation via tools/rotate.py subprocess.
    Das ist der einzige getestete und verifizierte Weg.
    """
    import subprocess, re, json, asyncio
    t0 = time.time()

    args = ["python3", "tools/rotate.py", "--password", request.fireworks_password]
    if request.new_alias_name:
        args.append(request.new_alias_name)
    if not request.save_to_pool:
        args.append("--no-save")

    logger.info(f"Starting rotation: {' '.join(args)}")

    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(Path(__file__).parent.parent.parent.parent),
            env={**__import__("os").environ, "PYTHONUNBUFFERED": "1"},
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=360)
        # rotate.py uses logging which goes to stderr, not stdout
        output = stderr.decode() + stdout.decode()

        # Parse output for API key and alias
        api_key_match = re.search(r'API Key:\s+(fw_\S+)', output)
        alias_match = re.search(r'Alias:\s+(\S+@gmx\.\w+)', output)

        gmx_alias = alias_match.group(1) if alias_match else None
        api_key = api_key_match.group(1) if api_key_match else None
        api_key_name = gmx_alias.split("@")[0].split("-")[0] if gmx_alias else "key"
        success = "ROTATION COMPLETE" in output

        if success and gmx_alias:
            return RotationResponse(
                status="success",
                gmx_alias=gmx_alias,
                fireworks_account=gmx_alias,
                api_key=api_key,
                api_key_name=api_key_name,
                steps_completed=["rotation_complete"],
                steps_failed=[],
                execution_time=f"{time.time() - t0:.2f}s",
            )
        else:
            error = stderr.decode()[:200] if stderr else output[-200:]
            return RotationResponse(
                status="failed",
                gmx_alias=gmx_alias,
                error=f"rotate.py failed: {error}",
                steps_completed=[],
                steps_failed=["rotation_failed"],
                execution_time=f"{time.time() - t0:.2f}s",
            )
    except asyncio.TimeoutError:
        return RotationResponse(
            status="failed",
            error="Rotation timeout (>360s)",
            steps_completed=[], steps_failed=["timeout"],
            execution_time=f"{time.time() - t0:.2f}s",
        )


# Legacy helpers kept for compatibility
