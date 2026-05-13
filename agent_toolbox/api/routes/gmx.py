"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SINATOR AGENT-TOOLBOX — GMX Routes (CDP Edition)              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ENDPOINTS:                                                                   ║
║  POST /gmx/session/check       → GMX Session prüfen                         ║
║  POST /gmx/email-addresses     → E-Mail-Adressen-Seite öffnen               ║
║  POST /gmx/alias/delete        → Existierenden Alias löschen                ║
║  POST /gmx/alias/create        → Neuen Alias erstellen                      ║
║  POST /gmx/inbox/open          → GMX Inbox öffnen                           ║
║  POST /gmx/otp/read            → OTP aus GMX Inbox lesen                    ║
║                                                                              ║
║  WARUM KEIN PLAYWRIGHT PAGE?                                                 ║
║  Playwright's page interface crashed bei GMX Navigator SPA mit:              ║
║    ValueError: list.remove(x): x not in list                                 ║
║  Lösung: Alle GMX-Operationen verwenden raw CDP websocket.                   ║
║  Der BrowserManager stellt den CDP-Port bereit; GmxService öffnet            ║
║  eine temporäre CDP-Verbindung für jede Operation.                             ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import time
import logging

from fastapi import APIRouter, HTTPException

from agent_toolbox.core.browser_manager import get_browser_manager
from agent_toolbox.core.gmx_service import get_gmx_service
from agent_toolbox.api.schemas import (
    GmxSessionCheckResponse,
    GmxEmailAddressesResponse,
    GmxAliasDeleteResponse,
    GmxAliasResponse,
    GmxInboxOpenResponse,
    GmxOtpResponse,
    GmxAliasRotateRequest,
    GmxAliasRotateResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/gmx", tags=["GMX Services"])


def _require_browser():
    """
    Prüft ob der Browser läuft und gibt den CDP-Port zurück.
    
    Raises:
        HTTPException: Wenn Browser nicht gestartet
    """
    browser_mgr = get_browser_manager()
    if not browser_mgr.is_running:
        raise HTTPException(
            status_code=400,
            detail="Browser nicht gestartet. POST /browser/start zuerst aufrufen."
        )
    return browser_mgr.cdp_port


@router.post("/session/check", response_model=GmxSessionCheckResponse)
async def check_session():
    """
    Prüft ob eine GMX-Session aktiv ist.
    
    FLOW:
    1. Lädt GMX Homepage mit kopiertem Chrome-Profil
    2. Prüft "Sie sind eingeloggt" / "Zum Postfach"
    3. Klickt "Zum Postfach" und prüft ob navigator.gmx.net/mail erreichbar
    
    Returns:
        status: "logged_in" | "not_logged_in" | "error"
        current_url: Aktuelle URL nach Navigation
        session_active: True wenn Session gültig
        sid: GMX session ID (wenn extrahiert)
    """
    t0 = time.time()
    cdp_port = _require_browser()
    
    try:
        result = await get_gmx_service().check_session(cdp_port=cdp_port)
        return GmxSessionCheckResponse(
            status=result["status"],
            current_url=result.get("current_url", ""),
            session_active=result.get("session_active", False),
            execution_time=f"{time.time()-t0:.2f}s",
            error=result.get("error"),
        )
    except Exception as e:
        logger.error(f"Session-Check endpoint fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/ensure", response_model=GmxSessionCheckResponse)
async def ensure_gmx_session(
    email: str = "opensin@gmx.de",
    password: str = "ZOE.jerry2024",
):
    """
    Flow 0: Stellt GMX Session wieder her oder macht Fresh Login.
    
    FLOW:
    1. Check ob GMX Inbox erreichbar (Session OK → Flow 1 weiter)
    2. Falls nicht: Logout → Login (3x Profil-Icon) → Email → Passwort
    
    Args:
        email: GMX login email (default: opensin@gmx.de)
        password: GMX login password (default: ZOE.jerry2024)
    
    Returns:
        status: "success" | "partial" | "error"
        action: "session_active" | "login_completed" | "login_attempted" | "failed"
        current_url: Aktuelle URL nach Login
        sid: GMX session ID (wenn verfügbar)
    """
    t0 = time.time()
    cdp_port = _require_browser()
    
    try:
        result = await get_gmx_service().ensure_gmx_session(
            email=email,
            password=password,
            cdp_port=cdp_port,
        )
        return GmxSessionCheckResponse(
            status=result["status"],
            current_url=result.get("current_url", ""),
            session_active=result.get("status") == "success",
            execution_time=f"{time.time()-t0:.2f}s",
            error=result.get("error"),
        )
    except Exception as e:
        logger.error(f"ensure_gmx_session endpoint fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/email-addresses", response_model=GmxEmailAddressesResponse)
async def open_email_addresses():
    """
    Navigiert zur E-Mail-Adressen-Verwaltungsseite (Alias-Seite).
    
    FLOW:
    1. Session check (Homepage → Postfach)
    2. Extract sid aus URL
    3. Navigate bap.navigator.gmx.net/mail_settings?sid=...
    4. CDP Click auf "E-Mail-Adressen" bei (80, 290)
    
    Returns:
        status: "success" | "not_logged_in" | "error"
        current_url: URL der Alias-Verwaltungsseite
    """
    t0 = time.time()
    cdp_port = _require_browser()
    
    try:
        result = await get_gmx_service().open_email_addresses_page(cdp_port=cdp_port)
        return GmxEmailAddressesResponse(
            status=result["status"],
            current_url=result.get("current_url"),
            title=result.get("title"),
            execution_time=f"{time.time()-t0:.2f}s",
            error=result.get("error"),
        )
    except Exception as e:
        logger.error(f"Email-Addresses endpoint fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alias/delete", response_model=GmxAliasDeleteResponse)
async def delete_alias():
    """
    Löscht einen existierenden GMX Alias.
    
    WICHTIG: GMX FreeMail erlaubt nur EINEN Alias gleichzeitig.
    Vor dem Erstellen eines neuen Aliases MUSS der existierende gelöscht werden.
    
    FLOW:
    1. Öffne E-Mail-Adressen Seite
    2. Finde existierenden Alias (via Text-Scan im Shadow DOM)
    3. Klicke Lösch-Button (via JS Shadow-DOM traversal)
    4. Bestätige Lösch-Dialog
    
    Returns:
        status: "success" | "no_alias" | "not_logged_in" | "error"
        deleted: True wenn gelöscht oder keiner vorhanden
        alias: Der gelöschte Alias (wenn gefunden)
    """
    t0 = time.time()
    cdp_port = _require_browser()
    
    try:
        result = await get_gmx_service().delete_existing_alias(cdp_port=cdp_port)
        return GmxAliasDeleteResponse(
            status=result["status"],
            deleted=result.get("deleted", False),
            alias=result.get("alias"),
            execution_time=f"{time.time()-t0:.2f}s",
            error=result.get("error"),
        )
    except Exception as e:
        logger.error(f"Alias-Delete endpoint fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alias/rotate", response_model=GmxAliasRotateResponse)
async def rotate_alias(request: GmxAliasRotateRequest = None):
    """
    ATOMISCHE Alias-Rotation: Löscht existierenden Alias und erstellt einen neuen.
    
    Dies ist der KERN-Endpunkt für kontinuierliche Account-Rotation. Beide
    Operationen (delete + create) teilen sich eine CDP-Verbindung für maximale
    Geschwindigkeit und Session-Stabilität.
    
    Args:
        request.new_alias_name: Optionaler Alias-Name. Wenn None, wird generiert.
        
    Returns:
        status: "success" | "partial" | "failed" | "error"
        deleted_alias: Die gelöschte Alias-Email (oder None)
        created_alias: Die erstellte Alias-Email (oder None)
        created_alias_name: Der verwendete Name
        steps_completed: Liste der erfolgreichen Schritte
        steps_failed: Liste der fehlgeschlagenen Schritte
    """
    t0 = time.time()
    cdp_port = _require_browser()
    
    new_alias_name = request.new_alias_name if request else None
    
    try:
        result = await get_gmx_service().rotate_alias(
            new_alias_name=new_alias_name,
            cdp_port=cdp_port,
        )
        return GmxAliasRotateResponse(
            status=result["status"],
            deleted_alias=result.get("deleted_alias"),
            created_alias=result.get("created_alias"),
            created_alias_name=result.get("created_alias_name"),
            steps_completed=result.get("steps_completed", []),
            steps_failed=result.get("steps_failed", []),
            execution_time=f"{time.time()-t0:.2f}s",
            error=result.get("error"),
        )
    except Exception as e:
        logger.error(f"Alias-Rotate endpoint fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alias/create", response_model=GmxAliasResponse)
async def create_alias(alias_name: str = None):
    """
    Erstellt einen neuen GMX Alias.
    
    Generiert automatisch einen Namen im Format {adj}-{noun}@gmx.de
    wenn keiner angegeben wird.
    
    FLOW:
    1. Session check
    2. Alias-Seite öffnen
    3. Existierenden Alias löschen (wenn vorhanden)
    4. Formular füllen (Alias-Name + Domain @gmx.de)
    5. "Hinzufügen" klicken
    6. Erfolg prüfen (Text-Scan)
    
    Args:
        alias_name: Optionaler Alias-Name (ohne @gmx.de). Wenn None, wird generiert.
        
    Returns:
        status: "success" | "failed" | "not_logged_in" | "error"
        alias_email: Die vollständige Alias-Email
        alias_name: Der verwendete Alias-Name
        steps_completed: Liste der abgeschlossenen Schritte
    """
    t0 = time.time()
    cdp_port = _require_browser()
    
    try:
        result = await get_gmx_service().create_alias(alias_name=alias_name, cdp_port=cdp_port)
        return GmxAliasResponse(
            status=result["status"],
            alias_email=result.get("alias_email"),
            alias_name=result.get("alias_name"),
            steps_completed=result.get("steps_completed", []),
            execution_time=f"{time.time()-t0:.2f}s",
            error=result.get("error"),
        )
    except Exception as e:
        logger.error(f"Alias-Create endpoint fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/inbox/open", response_model=GmxInboxOpenResponse)
async def open_inbox():
    """
    Öffnet die GMX Inbox.
    
    Returns:
        status: "success" | "not_logged_in" | "error"
        current_url: URL der Inbox
    """
    t0 = time.time()
    cdp_port = _require_browser()
    
    try:
        result = await get_gmx_service().open_inbox(cdp_port=cdp_port)
        return GmxInboxOpenResponse(
            status=result["status"],
            current_url=result.get("current_url"),
            execution_time=f"{time.time()-t0:.2f}s",
        )
    except Exception as e:
        logger.error(f"Inbox-Open endpoint fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/otp/read", response_model=GmxOtpResponse)
async def read_otp(sender_filter: str = "fireworks", max_retries: int = 12):
    """
    Liest OTP-URL aus der GMX Inbox (polling).
    
    Sucht nach Emails vom angegebenen Absender und extrahiert
    Bestätigungs-URLs (z.B. für Fireworks AI Account-Aktivierung).
    
    Args:
        sender_filter: Absender-Filter (default: "fireworks")
        max_retries: Maximale Polling-Versuche (default: 12)
        
    Returns:
        status: "success" | "not_found" | "not_logged_in" | "error"
        otp_url: Die extrahierte Bestätigungs-URL
    """
    t0 = time.time()
    cdp_port = _require_browser()
    
    try:
        result = await get_gmx_service().read_otp(
            sender_filter=sender_filter,
            max_retries=max_retries,
            cdp_port=cdp_port,
        )
        return GmxOtpResponse(
            status=result["status"],
            otp_url=result.get("otp_url"),
            execution_time=f"{time.time()-t0:.2f}s",
            error=result.get("error"),
        )
    except Exception as e:
        logger.error(f"OTP-Read endpoint fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))
