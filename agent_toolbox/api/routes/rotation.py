"""Full account rotation orchestrator — spawns tools/rotate.py as subprocess.

Docs: rotation.doc.md
"""
import time
import logging
import asyncio
import re
from pathlib import Path

from fastapi import APIRouter

from agent_toolbox.api.schemas import RotationRequest, RotationResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rotation", tags=["rotation"])

ROTATE_SCRIPT = Path(__file__).parent.parent.parent.parent / "tools" / "rotate.py"


@router.post("/full", response_model=RotationResponse)
async def full_rotation(request: RotationRequest):
    """
    Rotation via chromium.launch() (V15.4 ONE Browser).
    Dashboard bleibt offen, Rotation läuft im gleichen Chromium.
    """
    # macOS HDMI/Display-Fix: Kein AppleScript-set-bounds mehr.
    # Die festen Pixelkoordinaten und make-new-window haben auf externen
    # HDMI-Monitoren beim Rotations-Start den WindowServer-Reset ausgelöst
    # und die Display-Verbindung zum Absturz gebracht.
    # Fenstergröße wird über --window-size beim chromium.launch() gesetzt.
    t0 = time.time()

    from agent_toolbox.core.config_manager import get_config
    cfg = get_config()
    fireworks_pw = request.fireworks_password or cfg.fireworks_password
    cmd = [
        "python3", str(ROTATE_SCRIPT),
        "--gmx-email", cfg.gmx_email,
        "--gmx-password", cfg.gmx_password,
        "--password", fireworks_pw,
        "--cdp-port", "9222",
    ]
    if request.new_alias_name:
        cmd.append(request.new_alias_name)

    logger.info(f"Running rotate.py --cdp-port 9222")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(ROTATE_SCRIPT.parent.parent),
        )

        output_lines = []
        gmx_alias = None
        api_key = None
        api_key_name = None

        async for line_bytes in proc.stdout:
            line = line_bytes.decode("utf-8", errors="replace").rstrip()
            output_lines.append(line)
            logger.info(line)

            m = re.search(r'✅ GMX Alias:\s*(\S+@gmx\.de)', line)
            if m:
                gmx_alias = m.group(1)
                api_key_name = gmx_alias.split("@")[0].split("-")[0]

            m = re.search(r'✅ API Key:\s*(fw_\w+)', line)
            if m:
                api_key = m.group(1)

        await proc.wait()
        elapsed = time.time() - t0

        steps_completed = []
        steps_failed = []

        if gmx_alias:
            steps_completed.append("gmx_alias_rotated")
        else:
            steps_failed.append("gmx_alias_rotation_failed")

        if api_key:
            steps_completed.append("api_key_created")
        else:
            steps_failed.append("api_key_creation_failed")

        if any("Login + Onboarding OK" in l for l in output_lines[-20:]):
            steps_completed.append("fireworks_login")
        else:
            steps_failed.append("fireworks_login_failed")

        final_status = "success" if api_key else ("partial" if gmx_alias else "failed")

        return RotationResponse(
            status=final_status,
            gmx_alias=gmx_alias,
            fireworks_account=gmx_alias,
            api_key=api_key,
            api_key_name=api_key_name,
            steps_completed=steps_completed,
            steps_failed=steps_failed,
            execution_time=f"{elapsed:.2f}s",
        )

    except Exception as e:
        elapsed = time.time() - t0
        logger.error(f"Rotation failed: {e}")
        return RotationResponse(
            status="error",
            steps_failed=["subprocess_error"],
            execution_time=f"{elapsed:.2f}s",
            error=str(e),
        )
