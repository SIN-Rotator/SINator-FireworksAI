"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SINATOR AGENT-TOOLBOX — Fireworks Routes (CDP Edition)           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ENDPOINTS:                                                                   ║
║  POST /fireworks/register  → Fireworks Account registrieren                 ║
║  POST /fireworks/confirm   → Fireworks Account bestätigen                   ║
║  POST /fireworks/apikey    → Fireworks API-Key erstellen                    ║
║                                                                              ║
║  ARCHITEKTUR:                                                                 ║
║  Alle Fireworks-Operationen nutzen RAW CDP (kein Playwright Page).           ║
║  BrowserManager.start() öffnet Chrome + CDP-Port; FireworksService          ║
║  verbindet sich direkt via websocket.                                        ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import time
import logging

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


def _require_browser():
    """Prüft ob Browser läuft und gibt CDP-Port zurück."""
    browser_mgr = get_browser_manager()
    if not browser_mgr.is_running:
        raise HTTPException(status_code=400, detail="Browser nicht gestartet. POST /browser/start zuerst aufrufen.")
    return browser_mgr.cdp_port


@router.post("/register", response_model=FireworksRegisterResponse)
async def register_fireworks(request: FireworksRegisterRequest):
    """
    Registriert einen neuen Fireworks AI Account.

    Nutzt den GMX Alias (z.B. echo-falcon@gmx.de) als Email für die
    Fireworks-Registrierung. Nach der Registrierung wird eine
    Bestätigungs-Email an den GMX Alias gesendet.

    Args:
        email: GMX Alias Email
        password: Passwort für den Fireworks Account

    Returns:
        status: "success" | "failed" | "error"
        account_email: Registrierte Email
        steps_completed: Liste der abgeschlossenen Schritte
    """
    t0 = time.time()
    cdp_port = _require_browser()

    try:
        result = await get_fireworks_service().register(
            email=request.email,
            password=request.password,
            cdp_port=cdp_port,
        )
        return FireworksRegisterResponse(
            status=result["status"],
            account_email=result.get("account_email", request.email),
            execution_time=f"{time.time()-t0:.2f}s",
            error=result.get("error"),
        )
    except Exception as e:
        logger.error(f"Fireworks Registrierung fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/confirm", response_model=FireworksConfirmResponse)
async def confirm_fireworks(request: FireworksConfirmRequest):
    """
    Bestätigt den Fireworks Account via OTP-URL.

    Die confirm_url kommt typischerweise aus:
    1. GMX OTP-Polling: POST /gmx/otp/read
    2. Manuell: Aus der GMX Bestätigungs-Email extrahiert

    Das gleiche Browser-Fenster wird genutzt (eingeloggte GMX-Session + Fireworks).

    Args:
        confirm_url: Bestätigungs-URL aus der GMX Email
        email: Account Email (für Login falls nötig)
        password: Account Passwort

    Returns:
        status: "success" | "failed" | "error"
        account_confirmed: True wenn Bestätigung erfolgreich
    """
    t0 = time.time()
    cdp_port = _require_browser()

    try:
        result = await get_fireworks_service().confirm(
            confirm_url=request.confirm_url,
            email=request.email,
            password=request.password,
            first_name=request.first_name,
            last_name=request.last_name,
            cdp_port=cdp_port,
        )
        return FireworksConfirmResponse(
            status=result["status"],
            account_confirmed=result.get("account_confirmed", False),
            execution_time=f"{time.time()-t0:.2f}s",
            error=result.get("error"),
        )
    except Exception as e:
        logger.error(f"Fireworks Bestätigung fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/apikey", response_model=FireworksApiKeyResponse)
async def create_fireworks_apikey(request: FireworksApiKeyRequest):
    """
    Erstellt einen neuen Fireworks API-Key.

    Navigiert zum Settings → API Keys und generiert einen neuen Key.
    Der Key wird im Response zurückgegeben — der Agent sollte ihn
    anschliessend im Pool speichern via POST /pool/add.

    Args:
        key_name: Name für den API-Key (default: "sinator-key")

    Returns:
        status: "success" | "failed" | "error"
        api_key: Der generierte API-Key (fw-... oder sk-...)
        key_name: Name des Keys
    """
    t0 = time.time()
    cdp_port = _require_browser()

    try:
        result = await get_fireworks_service().create_api_key(
            key_name=request.key_name,
            cdp_port=cdp_port,
        )
        return FireworksApiKeyResponse(
            status=result["status"],
            api_key=result.get("api_key"),
            key_name=result.get("key_name", request.key_name),
            execution_time=f"{time.time()-t0:.2f}s",
            error=result.get("error"),
        )
    except Exception as e:
        logger.error(f"Fireworks API-Key-Erstellung fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))