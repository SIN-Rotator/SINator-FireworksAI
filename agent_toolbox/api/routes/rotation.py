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
        #  STEP 1: GMX Alias Rotation
        # ════════════════════════════════════════════════════════════════════════
        #
        # Lösche alten Alias (falls vorhanden) und erstelle einen neuen.
        # rotate_alias() liefert den neuen Alias-Namen zurück.
        #
        # GMX FreeMail beschränkt: NUR EIN Alias gleichzeitig.
        # → Alten Alias löschen bevor neuen erstellen.
        #
        # rotate_alias() intern:
        # 1. Navigiere zu navigator.gmx.net/mail_settings/email_addresses
        # 2. Lösche existierenden Alias (falls vorhanden, mit Bestätigungs-Dialog)
        # 3. Generiere neuen Namen: {adjektiv}-{substantiv}-{3stellig}@gmx.de
        # 4. Erstelle neuen Alias im Formular
        # 5. Erfolg bestätigen
        #
        # Ergebnis: alias_result = {status, created_alias, ...}
        #
        logger.info("=== GMX Alias Rotation ===")
        gmx_svc = get_gmx_service()
        alias_result = await gmx_svc.rotate_alias(
            new_alias_name=request.new_alias_name,
            cdp_port=cdp_port,
        )

        if alias_result["status"] in ("success", "partial"):
            gmx_alias = alias_result.get("created_alias")
            steps_completed.append("gmx_alias_rotated")
            if alias_result["status"] == "partial":
                steps_failed.append("gmx_delete_failed")
            logger.info(f"✅ GMX Alias: {gmx_alias} (status={alias_result['status']})")
        else:
            steps_failed.append("gmx_alias_rotation_failed")
            return RotationResponse(
                status="failed",
                gmx_alias=None,
                fireworks_account=None,
                api_key=None,
                api_key_name=None,
                steps_completed=steps_completed,
                steps_failed=steps_failed + alias_result.get("steps_failed", []),
                execution_time=f"{time.time()-t0:.2f}s",
                error=alias_result.get("error") or "GMX Alias Rotation fehlgeschlagen",
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
            gmx_password="ZOE.jerry2024",
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