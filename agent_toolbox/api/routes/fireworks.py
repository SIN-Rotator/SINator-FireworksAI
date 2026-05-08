"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SINATOR AGENT-TOOLBOX — Fireworks Routes                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ENDPOINTS:                                                                   ║
║  POST /fireworks/register  → Fireworks Account registrieren                 ║
║  POST /fireworks/confirm   → Fireworks Account bestätigen                   ║
║  POST /fireworks/apikey    → Fireworks API-Key erstellen                    ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import time
import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException

from agent_toolbox.core.browser_manager import get_browser_manager
from agent_toolbox.core.fireworks_service import get_fireworks_service
from agent_toolbox.api.schemas import (
    FireworksRegisterRequest,
    FireworksRegisterResponse,
    FireworksConfirmRequest,
    FireworksConfirmResponse,
    FireworksApiKeyRequest,
    FireworksApiKeyResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/fireworks", tags=["Fireworks AI Services"])


@router.post("/register", response_model=FireworksRegisterResponse)
async def register_fireworks(request: FireworksRegisterRequest):
    """
    Registriert einen neuen Fireworks AI Account.
    """
    start_time = time.time()
    browser_mgr = get_browser_manager()

    if not browser_mgr.is_running:
        raise HTTPException(status_code=400, detail="Browser nicht gestartet. Rufe /browser/start auf.")

    try:
        page = await browser_mgr.get_page()
        fireworks_service = get_fireworks_service()

        result = await fireworks_service.register_account(
            page,
            email=request.email,
            password=request.password,
            first_name=request.first_name,
            last_name=request.last_name,
        )
        elapsed = time.time() - start_time

        await page.close()

        return FireworksRegisterResponse(
            status=result["status"],
            account_email=result["account_email"],
            execution_time=f"{elapsed:.2f}s",
            error=result.get("error"),
        )

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Fireworks Registrierung fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/confirm", response_model=FireworksConfirmResponse)
async def confirm_fireworks(request: FireworksConfirmRequest):
    """
    Bestätigt den Fireworks Account via OTP-URL.
    """
    start_time = time.time()
    browser_mgr = get_browser_manager()

    if not browser_mgr.is_running:
        raise HTTPException(status_code=400, detail="Browser nicht gestartet. Rufe /browser/start auf.")

    try:
        page = await browser_mgr.get_page()
        fireworks_service = get_fireworks_service()

        result = await fireworks_service.confirm_account(
            page,
            confirm_url=request.confirm_url,
            email=request.email,
            password=request.password,
            first_name=request.first_name,
            last_name=request.last_name,
        )
        elapsed = time.time() - start_time

        await page.close()

        return FireworksConfirmResponse(
            status=result["status"],
            account_confirmed=result["account_confirmed"],
            execution_time=f"{elapsed:.2f}s",
            error=result.get("error"),
        )

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Fireworks Bestätigung fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/apikey", response_model=FireworksApiKeyResponse)
async def create_fireworks_apikey(request: FireworksApiKeyRequest):
    """
    Erstellt einen neuen Fireworks API-Key.
    """
    start_time = time.time()
    browser_mgr = get_browser_manager()

    if not browser_mgr.is_running:
        raise HTTPException(status_code=400, detail="Browser nicht gestartet. Rufe /browser/start auf.")

    try:
        page = await browser_mgr.get_page()
        fireworks_service = get_fireworks_service()

        result = await fireworks_service.create_api_key(
            page,
            key_name=request.key_name,
        )
        elapsed = time.time() - start_time

        await page.close()

        return FireworksApiKeyResponse(
            status=result["status"],
            api_key=result["api_key"],
            key_name=result["key_name"],
            execution_time=f"{elapsed:.2f}s",
            error=result.get("error"),
        )

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Fireworks API-Key-Erstellung fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))
