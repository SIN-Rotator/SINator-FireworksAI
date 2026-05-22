"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SINATOR AGENT-TOOLBOX — Browser Routes                          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ENDPOINTS:                                                                   ║
║  POST /browser/start   → Chrome starten mit Profil-Kopie                    ║
║  POST /browser/stop    → Chrome beenden & Cleanup                           ║
║  GET  /browser/status  → Browser-Status prüfen                              ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import time
import logging

from fastapi import APIRouter, HTTPException

from agent_toolbox.core.browser_manager import get_browser_manager
from agent_toolbox.api.schemas import (
    BrowserStartRequest,
    BrowserStartResponse,
    BrowserStopResponse,
    BrowserStatusResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/browser", tags=["Browser Management"])


@router.post("/start", response_model=BrowserStartResponse)
async def start_browser(request: BrowserStartRequest):
    """
    Startet Chrome mit kopiertem Profil und CDP-Debugging.

    - Kopiert Local State + Profile nach /tmp
    - Startet Chrome via subprocess
    - Verbindet Playwright via CDP
    - Injectiert Stealth-JS

    **Warm-Start:** Wenn Browser bereits läuft, wird bestehende Instanz verwendet.
    """
    start_time = time.time()
    browser_mgr = get_browser_manager()

    # Update manager settings
    browser_mgr.profile_name = request.profile_name
    browser_mgr.cdp_port = request.cdp_port
    browser_mgr.headless = request.headless
    if request.chrome_path:
        browser_mgr.chrome_path = request.chrome_path

    try:
        result = await browser_mgr.start()
        elapsed = time.time() - start_time

        return BrowserStartResponse(
            status=result["status"],
            browser_info=result.get("browser_info", {}),
            temp_profile_dir=result.get("temp_profile_dir"),
            execution_time=f"{elapsed:.2f}s",
        )

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Browser-Start fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop", response_model=BrowserStopResponse)
async def stop_browser():
    """
    Beendet den Browser und räumt das Temp-Profil auf.
    """
    start_time = time.time()
    browser_mgr = get_browser_manager()

    try:
        result = await browser_mgr.stop()
        elapsed = time.time() - start_time

        return BrowserStopResponse(
            status=result["status"],
            cleanup_info=result.get("temp_profile_cleaned"),
            execution_time=f"{elapsed:.2f}s",
        )

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Browser-Stopp fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=BrowserStatusResponse)
async def browser_status():
    """
    Prüft den aktuellen Browser-Status.
    """
    browser_mgr = get_browser_manager()

    page_count = 0
    if browser_mgr.is_running and browser_mgr._context:
        page_count = len(browser_mgr._context.pages)

    return BrowserStatusResponse(
        is_running=browser_mgr.is_running,
        cdp_port=browser_mgr.cdp_port if browser_mgr.is_running else None,
        temp_profile=browser_mgr._temp_profile_dir,
        page_count=page_count,
    )
