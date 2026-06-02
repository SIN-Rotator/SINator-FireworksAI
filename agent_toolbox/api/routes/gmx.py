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
║  ⚡ ALIAS-VORGÄNGE DELEGIERT (2026-05-12):                                    ║
║  /alias/delete, /alias/create, /alias/rotate sind jetzt an die               ║
║  standalone gmx-alias-tool FastAPI auf port 8001 delegiert.                   ║
║  Session-Check, Inbox und OTP bleiben lokal.                                  ║
║                                                                              ║
║  WARUM KEIN PLAYWRIGHT PAGE?                                                 ║
║  Playwright's page interface crashed bei GMX Navigator SPA mit:              ║
║    ValueError: list.remove(x): x not in list                                 ║
║  Lösung: Alle GMX-Operationen verwenden raw CDP websocket.                   ║
║  V15.4+: chromium.launch() — CDP-Port 9222 fix, kein BrowserManager nötig.  ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
Docs: gmx.doc.md
"""
import time
import logging
from typing import Optional, Dict, Any

import httpx
from fastapi import APIRouter, HTTPException

# V15.4: chromium.launch() — kein browser_manager für cdp_port nötig
GMX_CDP_PORT = 9222
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

GMX_ALIAS_API_URL = "http://localhost:8001"


async def _call_alias_api(method: str, path: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Helper: Call the standalone gmx-alias-tool API on port 8001."""
    async with httpx.AsyncClient(timeout=120.0) as http:
        r = await http.request(method, f"{GMX_ALIAS_API_URL}{path}", json=data)
        r.raise_for_status()
        return r.json()


async def _gmx_create_via_api(alias_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """GMX Alias Create via gmx-alias-tool API (localhost:8001)."""
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post("http://localhost:8001/alias/create", json={"alias_name": alias_name})
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success":
                    return data
    except Exception as e:
        logger.warning(f"gmx-alias-tool create API error: {e}")
    return None


async def _gmx_create_fallback(alias_name: Optional[str] = None) -> Dict[str, Any]:
    """Fallback: GMX Alias Create direkt via GmxService."""
    from agent_toolbox.core.config_manager import get_config
    from agent_toolbox.core.gmx_service import GmxService
    cfg = get_config()
    svc = GmxService()
    result = await svc.check_session(cdp_port=9222)
    if result.get("status") != "success":
        logger.warning("GMX session not active for create fallback")
    result = await svc.create_alias(alias_name=alias_name, cdp_port=9222)
    if result.get("status") == "success":
        return result
    raise RuntimeError(f"GMX create fallback failed: {result.get('error', 'unknown')}")


async def _gmx_rotate_via_api_noauth(alias_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """GMX Alias Rotate via gmx-alias-tool API (localhost:8001) — kein Auth nötig."""
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post("http://localhost:8001/alias/rotate", json={"alias_name": alias_name or ""})
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success":
                    return data
    except Exception as e:
        logger.warning(f"gmx-alias-tool rotate API error: {e}")
    return None


async def _gmx_delete_via_api() -> Optional[Dict[str, Any]]:
    """GMX Alias Delete via gmx-alias-tool API (localhost:8001)."""
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post("http://localhost:8001/alias/delete")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") in ("success", "no_alias"):
                    return data
    except Exception as e:
        logger.warning(f"gmx-alias-tool delete API error: {e}")
    return None


async def _gmx_delete_fallback() -> Dict[str, Any]:
    """Fallback: GMX Alias Delete direkt via GmxService."""
    from agent_toolbox.core.config_manager import get_config
    from agent_toolbox.core.gmx_service import GmxService
    cfg = get_config()
    svc = GmxService()
    result = await svc.check_session(cdp_port=9222)
    if result.get("status") != "success":
        logger.warning("GMX session not active for delete fallback")
    return await svc.delete_existing_alias(cdp_port=9222)


def _require_browser():
    """V15.4: chromium.launch() — immer verfügbar. Gibt CDP-Port zurück."""
    return GMX_CDP_PORT


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
    email: Optional[str] = None,
    password: Optional[str] = None,
):
    """
    Flow 0: Stellt GMX Session wieder her oder macht Fresh Login.
    Liest Credentials aus config_manager (kein Frontend-Fallback!).
    
    FLOW:
    1. Check ob GMX Inbox erreichbar (Session OK → Flow 1 weiter)
    2. Falls nicht: Logout → Login über Playwright
    
    Returns:
        status: "success" | "partial" | "error"
        action: "session_active" | "login_completed" | "login_attempted" | "failed"
        current_url: Aktuelle URL nach Login
        sid: GMX session ID (wenn verfügbar)
    """
    from agent_toolbox.core.config_manager import get_config
    cfg = get_config()
    email = email or cfg.gmx_email
    password = password or cfg.gmx_password
    
    t0 = time.time()
    cdp_port = _require_browser()
    
    try:
        result = await get_gmx_service().check_session(cdp_port=cdp_port)
        if result.get("status") == "success":
            logger.info("Session active — no login needed")
        else:
            logger.info("Session inactive — attempting login")
            import asyncio
            from playwright.async_api import async_playwright
            p = await async_playwright().start()
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            from agent_toolbox.core.gmx_service import GmxService
            svc = GmxService()
            await svc._login(page, email=email, password=password)
            await asyncio.sleep(3)
            result = await svc.check_session(cdp_port=cdp_port)
            await browser.close()
            await p.stop()
        
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

    Versucht zuerst die standalone gmx-alias-tool API auf port 8001,
    fallback auf direkte GmxService-Operation.

    Returns:
        status: "success" | "no_alias" | "not_logged_in" | "error"
        deleted: True wenn gelöscht oder keiner vorhanden
        alias: Der gelöschte Alias (wenn gefunden)
    """
    t0 = time.time()

    try:
        result = await _gmx_delete_via_api()
        if result:
            return GmxAliasDeleteResponse(
                status=result["status"],
                deleted=result.get("deleted", False),
                alias=result.get("alias"),
                execution_time=f"{time.time()-t0:.2f}s",
                error=result.get("error"),
            )
        logger.info("gmx-alias-tool API offline, using direct fallback")
        result = await _gmx_delete_fallback()
        return GmxAliasDeleteResponse(
            status=result.get("status", "error"),
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

    Delegiert an die standalone gmx-alias-tool API auf port 8001.

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

    new_alias_name = request.new_alias_name if request else None

    try:
        result = await _gmx_rotate_via_api_noauth(new_alias_name)
        if result:
            return GmxAliasRotateResponse(
                status=result.get("status", "success"),
                deleted_alias=result.get("deleted_alias"),
                created_alias=result.get("alias_email"),
                created_alias_name=result.get("created_alias_name"),
                steps_completed=result.get("steps_completed", []),
                steps_failed=result.get("steps_failed", []),
                execution_time=f"{time.time()-t0:.2f}s",
                error=result.get("error"),
            )
        logger.info("gmx-alias-tool API offline, using direct fallback")
        from agent_toolbox.core.gmx_service import GmxService
        svc = GmxService()
        fb_result = await svc.rotate_alias(new_alias_name=new_alias_name, cdp_port=9222)
        return GmxAliasRotateResponse(
            status=fb_result.get("status", "error"),
            deleted_alias=fb_result.get("deleted_alias"),
            created_alias=fb_result.get("created_alias"),
            created_alias_name=fb_result.get("created_alias_name"),
            steps_completed=fb_result.get("steps_completed", []),
            steps_failed=fb_result.get("steps_failed", []),
            execution_time=f"{time.time()-t0:.2f}s",
            error=fb_result.get("error"),
        )
    except Exception as e:
        logger.error(f"Alias-Rotate endpoint fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alias/create", response_model=GmxAliasResponse)
async def create_alias(alias_name: str = None):
    """
    Erstellt einen neuen GMX Alias.

    Versucht zuerst die standalone gmx-alias-tool API auf port 8001,
    fallback auf direkte GmxService-Operation.

    Args:
        alias_name: Optionaler Alias-Name (ohne @gmx.de). Wenn None, wird generiert.

    Returns:
        status: "success" | "failed" | "not_logged_in" | "error"
        alias_email: Die vollständige Alias-Email
        alias_name: Der verwendete Alias-Name
        steps_completed: Liste der abgeschlossenen Schritte
    """
    t0 = time.time()

    try:
        result = await _gmx_create_via_api(alias_name)
        if result:
            return GmxAliasResponse(
                status=result["status"],
                alias_email=result.get("alias_email"),
                alias_name=result.get("alias_name"),
                steps_completed=result.get("steps_completed", []),
                execution_time=f"{time.time()-t0:.2f}s",
                error=result.get("error"),
            )
        logger.info("gmx-alias-tool API offline, using direct fallback")
        result = await _gmx_create_fallback(alias_name)
        return GmxAliasResponse(
            status="success",
            alias_email=result.get("alias_email"),
            alias_name=result.get("alias_name"),
            steps_completed=["alias_created"],
            execution_time=f"{time.time()-t0:.2f}s",
        )
    except Exception as e:
        logger.error(f"Alias-Create endpoint fehlgeschlagen: {e}")
        return GmxAliasResponse(
            status="error",
            alias_email=None,
            alias_name=alias_name,
            execution_time=f"{time.time()-t0:.2f}s",
            error=str(e),
        )


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
