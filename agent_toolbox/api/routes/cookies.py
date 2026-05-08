"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SINATOR AGENT-TOOLBOX — Cookie Routes                           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ENDPOINTS:                                                                   ║
║  POST /cookies/extract  → Cookies aus Browser extrahieren                   ║
║  POST /cookies/inject   → Cookies in Browser injecten                       ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import time
import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException

from agent_toolbox.core.browser_manager import get_browser_manager
from agent_toolbox.core.cookie_manager import get_cookie_manager
from agent_toolbox.api.schemas import (
    CookieExtractRequest,
    CookieExtractResponse,
    CookieInjectRequest,
    CookieInjectResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cookies", tags=["Cookie Management"])


@router.post("/extract", response_model=CookieExtractResponse)
async def extract_cookies(request: CookieExtractRequest):
    """
    Extrahiert Cookies aus dem aktuellen Browser.
    """
    start_time = time.time()
    browser_mgr = get_browser_manager()

    if not browser_mgr.is_running:
        raise HTTPException(status_code=400, detail="Browser nicht gestartet. Rufe /browser/start auf.")

    try:
        page = await browser_mgr.get_page()
        cookie_mgr = get_cookie_manager()

        cookies = cookie_mgr.extract_cookies(page, domain_filter=request.domain_filter)
        stats = cookie_mgr.get_cookie_stats(cookies)

        saved_to = None
        if request.save_to_file:
            saved_to = cookie_mgr.save_cookies(cookies, filename=request.filename)

        elapsed = time.time() - start_time
        await page.close()

        return CookieExtractResponse(
            status="success",
            cookie_count=len(cookies),
            stats=stats,
            saved_to=saved_to,
            execution_time=f"{elapsed:.2f}s",
        )

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Cookie-Extraktion fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/inject", response_model=CookieInjectResponse)
async def inject_cookies(request: CookieInjectRequest):
    """
    Injiziert Cookies in den aktuellen Browser.
    """
    start_time = time.time()
    browser_mgr = get_browser_manager()

    if not browser_mgr.is_running:
        raise HTTPException(status_code=400, detail="Browser nicht gestartet. Rufe /browser/start auf.")

    try:
        cookie_mgr = get_cookie_manager()
        cookies = cookie_mgr.load_cookies(filename=request.filename)

        injected_count = await cookie_mgr.inject_cookies(browser_mgr._context, cookies)

        session_active = False
        if request.verify_session:
            page = await browser_mgr.get_page()
            session_active = await cookie_mgr.verify_session(page)
            await page.close()

        elapsed = time.time() - start_time

        return CookieInjectResponse(
            status="success",
            injected_count=injected_count,
            session_active=session_active,
            execution_time=f"{elapsed:.2f}s",
        )

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Cookie-Injektion fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))
