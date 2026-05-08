"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SINATOR AGENT-TOOLBOX — Rotation Routes (CDP Edition)            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ENDPOINT:                                                                    ║
║  POST /rotation/full         → Komplette Account-Rotation (GMX + Fireworks) ║
║                                                                              ║
║  KOMPLETTER FLOW (in einem API-Call):                                        ║
║  1. GMX Alias löschen (falls vorhanden)                                     ║
║  2. GMX Alias erstellen (rotiert auf neuen Namen)                           ║
║  3. Fireworks AI Account registrieren (mit neuer Alias-Email)              ║
║  4. GMX Inbox pollinen nach Bestätigungs-URL (max 12 Versuche × 5s)        ║
║  5. Fireworks Account bestätigen (OTP-URL öffnen)                          ║
║  6. Fireworks API-Key erstellen                                             ║
║  7. API-Key im Pool speichern (JSON)                                        ║
║                                                                              ║
║  ALLE OPERATIONEN nutzen dieselbe Browser-Session:                           ║
║  Chrome ist bereits gestartet mit GMX-Session.                               ║
║  GMX-Inbox ist erreichbar. Fireworks wird im gleichen Tab geöffnet.         ║
║                                                                              ║
║  TYPISCHE LAUFZEIT: ~3-5 minuten (GMX-Rotation ~45s,                         ║
║  Fireworks-Registrierung ~10s, OTP-Polling variabel,                          ║
║  Bestätigung ~10s, API-Key ~5s)                                              ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import time
import logging
import asyncio

from fastapi import APIRouter, HTTPException

from agent_toolbox.core.browser_manager import get_browser_manager
from agent_toolbox.core.gmx_service import get_gmx_service
from agent_toolbox.core.fireworks_service import get_fireworks_service
from agent_toolbox.core.pool_manager import get_pool_manager
from agent_toolbox.api.schemas import RotationRequest, RotationResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rotation", tags=["Account Rotation"])


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

    Dies ist der HAUPT-Endpunkt für die Agent Toolbox. Er orchestriert
    den gesamten Flow von GMX Alias über Fireworks Registration bis
    zum gespeicherten API-Key.

    Beispiel:
        curl -X POST http://localhost:8000/api/v1/rotation/full \\
          -H "Content-Type: application/json" \\
          -d '{"fireworks_password": "MeinPasswort123!"}'

    Args:
        new_alias_name: Optionaler GMX Alias-Name. Wenn None → auto-generiert.
        fireworks_password: Passwort für neuen Fireworks Account (required).
        gmx_alias_name: Optional → alter Alias-Name (wird vor Rotation gelöscht).
        save_to_pool: Ob der API-Key im Pool gespeichert werden soll.

    Returns:
        status: "success" | "partial" | "failed" | "error"
        gmx_alias: Neue GMX Alias-Email
        fireworks_account: Registrierte Fireworks Email
        api_key: Generierter Fireworks API-Key
        steps_completed: Alle erfolgreichen Schritte
        steps_failed: Fehlgeschlagene Schritte
    """
    t0 = time.time()
    cdp_port = _require_browser()
    steps_completed = []
    steps_failed = []

    gmx_alias = None
    fireworks_account = None
    api_key = None
    api_key_name = "sinator-key"

    try:
        # ════════════════════════════════════════════════════════════════════════
        #  STEP 1: GMX Alias Rotation (delete old + create new)
        # ════════════════════════════════════════════════════════════════════════
        logger.info("=== STEP 1: GMX Alias Rotation ===")
        gmx_svc = get_gmx_service()
        alias_result = await gmx_svc.rotate_alias(
            new_alias_name=request.new_alias_name,
            cdp_port=cdp_port,
        )

        if alias_result["status"] == "success":
            gmx_alias = alias_result.get("created_alias")
            steps_completed.append("gmx_alias_rotated")
            logger.info(f"✅ GMX Alias erstellt: {gmx_alias}")
        elif alias_result["status"] == "partial":
            gmx_alias = alias_result.get("created_alias")
            steps_completed.append("gmx_alias_rotated")
            steps_failed.append("gmx_delete_failed")
            logger.warning(f"⚠️ GMX Alias erstellt aber altes Löschen fehlgeschlagen: {gmx_alias}")
        else:
            steps_failed.append("gmx_alias_rotation_failed")
            return RotationResponse(
                status="failed",
                gmx_alias=None,
                fireworks_account=None,
                api_key=None,
                steps_completed=steps_completed,
                steps_failed=steps_failed + alias_result.get("steps_failed", []),
                execution_time=f"{time.time()-t0:.2f}s",
                error=alias_result.get("error") or "GMX Alias Rotation fehlgeschlagen",
            )

        # ════════════════════════════════════════════════════════════════════════
        #  STEP 2: Fireworks AI Registration
        # ════════════════════════════════════════════════════════════════════════
        logger.info("=== STEP 2: Fireworks Registration ===")
        fw_svc = get_fireworks_service()
        reg_result = await fw_svc.register(
            email=gmx_alias,
            password=request.fireworks_password,
            cdp_port=cdp_port,
        )

        if reg_result["status"] == "success":
            fireworks_account = gmx_alias
            steps_completed.append("fireworks_registered")
            logger.info(f"✅ Fireworks Account registriert: {fireworks_account}")
        elif reg_result["status"] == "failed":
            steps_failed.append("fireworks_registration_failed")
            return RotationResponse(
                status="partial",
                gmx_alias=gmx_alias,
                fireworks_account=None,
                api_key=None,
                steps_completed=steps_completed,
                steps_failed=steps_failed,
                execution_time=f"{time.time()-t0:.2f}s",
                error=reg_result.get("error") or "Fireworks Registration fehlgeschlagen",
            )
        else:
            steps_failed.append("fireworks_registration_error")
            return RotationResponse(
                status="error",
                gmx_alias=gmx_alias,
                fireworks_account=None,
                api_key=None,
                steps_completed=steps_completed,
                steps_failed=steps_failed,
                execution_time=f"{time.time()-t0:.2f}s",
                error=reg_result.get("error"),
            )

        # ════════════════════════════════════════════════════════════════════════
        #  STEP 3: GMX OTP Polling (Bestätigungs-URL aus Email extrahieren)
        # ════════════════════════════════════════════════════════════════════════
        logger.info("=== STEP 3: GMX OTP Polling ===")
        otp_result = await gmx_svc.read_otp(
            sender_filter="fireworks",
            max_retries=12,
            retry_delay=5,
            cdp_port=cdp_port,
        )

        if otp_result["status"] == "success" and otp_result.get("otp_url"):
            confirm_url = otp_result["otp_url"]
            steps_completed.append("otp_url_received")
            logger.info(f"✅ OTP-URL gefunden: {confirm_url[:60]}...")
        elif otp_result["status"] == "not_found":
            steps_failed.append("otp_not_found")
            logger.warning("⚠️ OTP nicht gefunden nach 12 Versuchen (60s)")
            return RotationResponse(
                status="partial",
                gmx_alias=gmx_alias,
                fireworks_account=fireworks_account,
                api_key=None,
                steps_completed=steps_completed,
                steps_failed=steps_failed,
                execution_time=f"{time.time()-t0:.2f}s",
                error=f"OTP nicht gefunden nach {otp_result['execution_time']} — Account nicht bestätigt. Bitte OTP manuell in GMX-Inbox prüfen.",
            )
        else:
            steps_failed.append("otp_polling_error")
            return RotationResponse(
                status="error",
                gmx_alias=gmx_alias,
                fireworks_account=fireworks_account,
                api_key=None,
                steps_completed=steps_completed,
                steps_failed=steps_failed,
                execution_time=f"{time.time()-t0:.2f}s",
                error=otp_result.get("error"),
            )

        # ════════════════════════════════════════════════════════════════════════
        #  STEP 4: Fireworks Account Bestätigen (OTP-URL öffnen)
        # ════════════════════════════════════════════════════════════════════════
        logger.info("=== STEP 4: Fireworks Account Bestätigung ===")
        confirm_result = await fw_svc.confirm(
            confirm_url=confirm_url,
            email=gmx_alias,
            password=request.fireworks_password,
            cdp_port=cdp_port,
        )

        if confirm_result["status"] == "success" and confirm_result.get("account_confirmed"):
            steps_completed.append("fireworks_confirmed")
            logger.info("✅ Fireworks Account bestätigt")
        elif confirm_result["status"] == "failed":
            steps_failed.append("fireworks_confirmation_failed")
            logger.warning("⚠️ Fireworks Bestätigung fehlgeschlagen (URL ungültig oder abgelaufen?)")
        else:
            steps_failed.append("fireworks_confirmation_error")
            return RotationResponse(
                status="error",
                gmx_alias=gmx_alias,
                fireworks_account=fireworks_account,
                api_key=None,
                steps_completed=steps_completed,
                steps_failed=steps_failed,
                execution_time=f"{time.time()-t0:.2f}s",
                error=confirm_result.get("error") or "Fireworks Bestätigung fehlgeschlagen",
            )

        # ════════════════════════════════════════════════════════════════════════
        #  STEP 5: Fireworks API-Key erstellen
        # ════════════════════════════════════════════════════════════════════════
        logger.info("=== STEP 5: Fireworks API-Key erstellen ===")
        key_result = await fw_svc.create_api_key(
            key_name=api_key_name,
            cdp_port=cdp_port,
        )

        if key_result["status"] == "success" and key_result.get("api_key"):
            api_key = key_result["api_key"]
            steps_completed.append("api_key_created")
            logger.info(f"✅ API-Key erstellt: {api_key[:12]}...")
        else:
            steps_failed.append("api_key_creation_failed")
            return RotationResponse(
                status="partial",
                gmx_alias=gmx_alias,
                fireworks_account=fireworks_account,
                api_key=None,
                steps_completed=steps_completed,
                steps_failed=steps_failed,
                execution_time=f"{time.time()-t0:.2f}s",
                error=key_result.get("error") or "API-Key konnte nicht erstellt werden",
            )

        # ════════════════════════════════════════════════════════════════════════
        #  STEP 6: API-Key im Pool speichern
        # ════════════════════════════════════════════════════════════════════════
        if request.save_to_pool and api_key:
            logger.info("=== STEP 6: API-Key im Pool speichern ===")
            pool = get_pool_manager()
            pool.add_key(
                api_key=api_key,
                alias_email=gmx_alias,
                key_name=api_key_name,
            )
            steps_completed.append("api_key_saved_to_pool")
            logger.info(f"✅ API-Key im Pool gespeichert für {gmx_alias}")

        elapsed = time.time() - t0
        logger.info(f"🎉 ROTATION COMPLETE in {elapsed:.1f}s")
        return RotationResponse(
            status="success",
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
            steps_completed=steps_completed,
            steps_failed=steps_failed,
            execution_time=f"{elapsed:.2f}s",
            error=str(e),
        )