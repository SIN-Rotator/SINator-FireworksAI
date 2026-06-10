"""
SINATOR — Fireworks Routes V8 (Playwright+CUA, 2026-05-22)

Docs: fireworks.doc.md
"""
import time
import logging
from fastapi import APIRouter, HTTPException

# V15.4: chromium.launch() — kein browser_manager nötig
from agent_toolbox.core.fireworks_service import login_fireworks, create_api_key
from agent_toolbox.api.schemas import (
    FireworksRegisterRequest, FireworksRegisterResponse,
    FireworksApiKeyRequest, FireworksApiKeyResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/fireworks", tags=["Fireworks AI Services"])


def _require_browser():
    """V15.4: chromium.launch() — immer verfügbar."""
    return 9222


@router.post("/login", response_model=FireworksRegisterResponse)
async def login(request: FireworksRegisterRequest):
    """Login to Fireworks AI account (Playwright + CUA onboarding)."""
    t0 = time.time()
    _require_browser()
    result = await login_fireworks(request.email, request.password)
    return FireworksRegisterResponse(
        status=result["status"],
        account_email=request.email,
        execution_time=f"{time.time()-t0:.2f}s",
        error=result.get("error"),
    )


@router.post("/apikey", response_model=FireworksApiKeyResponse)
async def apikey(request: FireworksApiKeyRequest):
    """Create Fireworks API Key (Playwright PopUpButton + menuitem)."""
    t0 = time.time()
    _require_browser()
    result = await create_api_key(request.key_name)
    return FireworksApiKeyResponse(
        api_key=result.get("api_key"),
        status=result["status"],
        execution_time=f"{time.time()-t0:.2f}s",
        error=result.get("error"),
    )
