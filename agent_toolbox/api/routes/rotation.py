"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SINATOR AGENT-TOOLBOX — Rotation Routes (CDP Edition)            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ENDPOINT:                                                                    ║
║  POST /rotation/full         → Komplette Account-Rotation (GMX + Fireworks) ║
║                                                                              ║
║  FLOW (4 SCHRITTE):                                                          ║
║  0. GMX Session 确保 — Login falls Session korrupt                           ║
║  1. GMX Alias löschen (falls vorhanden) + neuen Alias erstellen             ║
║  2. Fireworks register() — 12-Phasen E2E:                                   ║
║     • Fireworks Cookies + LocalStorage clearen                              ║
║     • /signup Page → Cookie Banner dismissen                                ║
║     • Email → Next → 2x Password → Create Account                          ║
║     • GMX OTP Polling (30x6s = 180s)                                        ║
║     • OTP URL aus detail-body-iframe extrahieren                            ║
║     • Account verifiziert → Sign In Flow                                    ║
║     • FirstName/LastName + Terms of Service                                 ║
║     • Use Case Selection → $5 Credits Submit                                ║
║     • Navigate zu API-Keys → Create + Generate Key                          ║
║     • Key extrahieren (fw-... Pattern)                                       ║
║  3. API-Key im Pool speichern (optional)                                     ║
║                                                                              ║
║  ALLE OPERATIONEN nutzen dieselbe Browser-Session:                           ║
║  Chrome Profile 901, CDP Port 9222, gleicher Tab für GMX + Fireworks.       ║
║                                                                              ║
║  TYPISCHE LAUFZEIT: ~2-5 minuten                                             ║
║  (Flow 0: ~10s, GMX Alias ~30s, Fireworks ~60-180s je nach Email-Delay)     ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import time
import logging
import asyncio
from typing import Optional, Dict, Any

import httpx
from fastapi import APIRouter, HTTPException

from agent_toolbox.core.browser_manager import get_browser_manager
from agent_toolbox.core.gmx_service import get_gmx_service
from agent_toolbox.core.fireworks_service import get_fireworks_service
from agent_toolbox.core.pool_manager import get_pool_manager
from agent_toolbox.api.schemas import RotationRequest, RotationResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rotation", tags=["Account Rotation"])

GMX_ALIAS_API_URL = "http://localhost:8001"


async def _call_alias_api(method: str, path: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Helper: Call the standalone gmx-alias-tool API on port 8001."""
    async with httpx.AsyncClient(timeout=120.0) as http:
        r = await http.request(method, f"{GMX_ALIAS_API_URL}{path}", json=data)
        r.raise_for_status()
        return r.json()


async def _rotate_alias_via_api(alias_name: Optional[str] = None) -> Dict[str, Any]:
    """Rotate GMX alias via the external gmx-alias-tool API.

    Maps the external API response to the format expected by the rotation flow.
    External API returns 'alias_email' for the created alias.
    """
    result = await _call_alias_api("POST", "/alias/rotate", {"alias_name": alias_name})
    # Normalize response: external API uses 'alias_email', flow expects 'created_alias'
    if result.get("status") in ("success", "partial"):
        result["created_alias"] = result.get("alias_email")
    return result


def _require_browser():
    """Prüft ob Browser läuft."""
    browser_mgr = get_browser_manager()
    if not browser_mgr.is_running:
        raise HTTPException(status_code=400, detail="Browser nicht gestartet. POST /browser/start zuerst aufrufen.")
    return browser_mgr.cdp_port


@router.post("/full", response_model=RotationResponse)
async def full_rotation(request: RotationRequest):
    """
    KOMPLETTE Account-Rotation in einem API-Call.

    Das ist der HAUPT-Endpunkt. Er orchestriert GMX Alias + Fireworks E2E.

    register() macht jetzt 12 Phasen intern (siehe fireworks_service.py Doku):
    1. Fireworks Cookies/LocalStorage clearen (nur Fireworks-Domain!)
    2. /signup laden + Cookie Banner dismissen (CDP coordinate click)
    3. Email eingeben + Next klicken
    4. Password + Confirm-Password eingeben + Create Account klicken
    5. GMX OTP Polling (12 retries × 5s)
    6. OTP URL öffnen → Account verifiziert
    7. Sign In Flow (Sign In → Email Login → Email+Password → Next)
    8. FirstName/LastName + Terms of Service Checkbox
    9. Use Case Checkboxes (Flexible capacity, Conversational AI)
    10. "Submit to get $5 Credits" klicken
    11. Loading polling (15s + 5×2s)
    12. Navigate zu API-Keys → Create → Name → Generate → Key extrahieren

    Args:
        new_alias_name: Optionaler GMX Alias-Name. Wenn None → auto-generiert.
        fireworks_password: Passwort für neuen Fireworks Account (required).
        save_to_pool: Ob der API-Key im Pool gespeichert werden soll (default: true).

    Returns:
        status: "success" | "partial" | "failed" | "error"
        gmx_alias: Neue GMX Alias-Email
        fireworks_account: Registrierte Fireworks Email (= gmx_alias)
        api_key: Generierter Fireworks API-Key (fw-...)
        api_key_name: Name des API-Keys (erster Alias-Bestandteil)
        steps_completed: Alle erfolgreichen Schritte (aus register())
        steps_failed: Fehlgeschlagene Schritte
        execution_time: Gesamtdauer in Sekunden
        error: Fehlermeldung falls status != "success"
    """
    t0 = time.time()
    cdp_port = _require_browser()
    steps_completed = []
    steps_failed = []

    gmx_alias = None
    fireworks_account = None
    api_key = None
    api_key_name = None

    try:
        # ════════════════════════════════════════════════════════════════════════
        #  STEP 0: GMX Session确保 / Login
        # ════════════════════════════════════════════════════════════════════════
        #
        # Flow 0: Stellt GMX Session sicher, otherwise fresh login.
        # Prüft ob navigator.gmx.net/mail?sid= erreichbar.
        # Falls nicht: Logout → Login → Email → Passwort
        #
        logger.info("=== Flow 0: GMX Session Check ===")
        gmx_svc = get_gmx_service()
        session_result = await gmx_svc.ensure_gmx_session(
            email="opensin@gmx.de",
            password="ZOE.jerry2024",
            cdp_port=cdp_port,
        )
        
        if session_result["status"] == "success":
            steps_completed.append("gmx_session_active")
            logger.info(f"✅ GMX Session OK: {session_result.get('sid', '')[:20]}...")
        else:
            steps_failed.append("gmx_session_failed")
            logger.error(f"❌ GMX Session fehlgeschlagen: {session_result}")
            return RotationResponse(
                status="error",
                gmx_alias=None,
                fireworks_account=None,
                api_key=None,
                api_key_name=None,
                steps_completed=steps_completed,
                steps_failed=steps_failed,
                execution_time=f"{time.time()-t0:.2f}s",
                error=f"GMX Session failed: {session_result.get('error', 'unknown')}",
            )

        # ════════════════════════════════════════════════════════════════════════
        #  STEP 1: GMX Alias Rotation (via gmx_alias_tool.py subprocess)
        # ════════════════════════════════════════════════════════════════════════
        #
        # gmx_alias_tool.py rotate — verifiziert, funktioniert 100%.
        # CUA-Delete-Dialog wird zuverlässig gehandlet.
        #
        logger.info("=== GMX Alias Rotation (gmx_alias_tool.py) ===")
        alias_result_str = await asyncio.create_subprocess_shell(
            "python3 tools/gmx_alias_tool.py rotate",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await alias_result_str.communicate()
        output = stdout.decode()

        created_alias = None
        for line in output.split('\n'):
            if 'Created:' in line:
                created_alias = line.split('Created:')[1].strip().split('@gmx.de')[0] + '@gmx.de'
                break

        if created_alias:
            gmx_alias = created_alias
            steps_completed.append("gmx_alias_rotated")
            logger.info(f"✅ GMX Alias: {gmx_alias}")
        else:
            logger.error(f"gmx_alias_tool.py rotate failed:\n{output}")
            steps_failed.append("gmx_alias_rotation_failed")
            return RotationResponse(
                status="failed",
                gmx_alias=None,
                fireworks_account=None,
                api_key=None,
                api_key_name=None,
                steps_completed=steps_completed,
                steps_failed=steps_failed,
                execution_time=f"{time.time()-t0:.2f}s",
                error="GMX Alias Rotation fehlgeschlagen",
            )

        # ════════════════════════════════════════════════════════════════════════
        #  STEP 2: Fireworks E2E (register() — 12 Phasen intern)
        # ════════════════════════════════════════════════════════════════════════
        #
        # Die neue register() Methode macht ALLES in einem Aufruf:
        # - Account erstellen auf /signup
        # - GMX OTP polling (findet Bestätigungs-URL in GMX-Inbox)
        # - Account verifizieren (OTP URL öffnen)
        # - Sign In Flow (einloggen mit frischem Account)
        # - Account Setup (Name, ToS, Use Cases, $5 Credits)
        # - API Key erstellen und extrahieren
        #
        # WICHTIG: gmx_password ist HARDCODED "ZOE.jerry2024" weil
        # register() GMX-Inbox-Zugriff braucht (nicht für Fireworks-Login).
        #
        logger.info(f"=== Fireworks E2E Registration (alias={gmx_alias}) ===")
        fw_svc = get_fireworks_service()
        reg_result = await fw_svc.register(
            email=gmx_alias,
            password=request.fireworks_password,
            gmx_password="ZOE.jerry2024",
            cdp_port=cdp_port,
        )

        fireworks_account = gmx_alias
        api_key = reg_result.get("api_key")
        api_key_name = reg_result.get("api_key_name") or gmx_alias.split("-")[0] if "-" in gmx_alias else gmx_alias.split("@")[0]

        if reg_result.get("status") == "success":
            steps_completed.append("fireworks_e2e_complete")
            logger.info(f"✅ Fireworks E2E: api_key={api_key[:12] if api_key else 'NONE'}...")
        elif reg_result.get("status") == "partial":
            if api_key:
                steps_completed.append("fireworks_e2e_partial_with_key")
                logger.warning(f"⚠️ Fireworks partial but key received: {api_key[:12]}...")
            else:
                steps_completed.append("fireworks_e2e_partial_no_key")
                logger.warning("⚠️ Fireworks partial, no API key received")
        else:
            steps_failed.append("fireworks_e2e_failed")
            return RotationResponse(
                status="failed",
                gmx_alias=gmx_alias,
                fireworks_account=fireworks_account,
                api_key=api_key,
                api_key_name=api_key_name,
                steps_completed=steps_completed,
                steps_failed=steps_failed,
                execution_time=f"{time.time()-t0:.2f}s",
                error=reg_result.get("error") or "Fireworks E2E Registration fehlgeschlagen",
            )

        # Merge register() steps into our steps list
        steps_completed.extend(reg_result.get("steps_completed", []))
        steps_failed.extend(reg_result.get("steps_failed", []))

        # ════════════════════════════════════════════════════════════════════════
        #  STEP 3: API-Key im Pool speichern
        # ════════════════════════════════════════════════════════════════════════
        #
        # Nur speichern wenn:
        # - save_to_pool=True (default)
        # - api_key ist vorhanden und nicht None/empty
        #
        # Pool speichert: {api_key, alias_email, key_name, created_at}
        #
        if request.save_to_pool and api_key and len(api_key) > 20:
            logger.info("=== Save API Key to Pool ===")
            pool = get_pool_manager()
            pool.add_key(
                api_key=api_key,
                alias_email=gmx_alias,
                key_name=api_key_name,
            )
            steps_completed.append("api_key_saved_to_pool")
            logger.info(f"✅ API-Key im Pool: {api_key[:12]}... für {gmx_alias}")
        elif not api_key or len(str(api_key)) <= 20:
            logger.warning("⚠️ API-Key nicht speicherbar (leer oder zu kurz)")
            steps_failed.append("api_key_invalid")

        elapsed = time.time() - t0
        final_status = "success" if (api_key and len(str(api_key)) > 20) else "partial"

        logger.info(
            f"🎉 ROTATION COMPLETE — status={final_status}, "
            f"gmx_alias={gmx_alias}, api_key={'YES' if api_key else 'NO'}, "
            f"time={elapsed:.1f}s, steps_ok={len(steps_completed)}, "
            f"steps_failed={len(steps_failed)}"
        )

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
        logger.error(f"Rotation failed mit Exception: {e}")
        return RotationResponse(
            status="error",
            gmx_alias=gmx_alias,
            fireworks_account=fireworks_account,
            api_key=None,
            api_key_name=None,
            steps_completed=steps_completed,
            steps_failed=steps_failed,
            execution_time=f"{elapsed:.2f}s",
            error=str(e),
        )