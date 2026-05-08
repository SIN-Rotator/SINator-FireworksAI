#!/usr/bin/env python3
"""
End-to-End Rotation Test (ohne HTTP Server)
Testet alle Schritte der Rotation mit dem aktuellen Browser-Tab.
"""
import asyncio
import time
from agent_toolbox.core.gmx_service import get_gmx_service
from agent_toolbox.core.fireworks_service import get_fireworks_service

async def test_rotation():
    t0 = time.time()
    gmx_svc = get_gmx_service()
    fw_svc = get_fireworks_service()
    cdp_port = 9222
    password = "SinatorTest2024!"

    steps_completed = []
    steps_failed = []
    gmx_alias = None
    confirm_url = None

    try:
        # STEP 1: GMX Alias Rotation
        print("=== STEP 1: GMX Alias Rotation ===")
        alias_result = await gmx_svc.rotate_alias(cdp_port=cdp_port)
        print(f"Alias result: {alias_result}")
        if alias_result["status"] in ("success", "partial"):
            gmx_alias = alias_result.get("created_alias")
            steps_completed.append("gmx_alias_rotated")
            print(f"✅ GMX Alias: {gmx_alias}")
        else:
            steps_failed.append("gmx_alias_rotation_failed")
            print(f"❌ GMX Alias Rotation fehlgeschlagen: {alias_result.get('error')}")
            return

        # STEP 2: Fireworks Registration
        print("\n=== STEP 2: Fireworks Registration ===")
        reg_result = await fw_svc.register(email=gmx_alias, password=password, cdp_port=cdp_port)
        print(f"Registration result: {reg_result}")
        if reg_result["status"] == "success":
            steps_completed.append("fireworks_registered")
            print(f"✅ Fireworks Account registriert: {gmx_alias}")
        else:
            steps_failed.append("fireworks_registration_failed")
            print(f"❌ Fireworks Registration fehlgeschlagen: {reg_result.get('error')}")
            return

        # STEP 3: OTP Polling
        print("\n=== STEP 3: OTP Polling ===")
        otp_result = await gmx_svc.read_otp(sender_filter="fireworks", max_retries=24, retry_delay=5, cdp_port=cdp_port)
        print(f"OTP result: {otp_result}")
        if otp_result["status"] == "success" and otp_result.get("otp_url"):
            confirm_url = otp_result["otp_url"]
            steps_completed.append("otp_url_received")
            print(f"✅ OTP-URL: {confirm_url[:80]}...")
        else:
            steps_failed.append("otp_not_found")
            print(f"❌ OTP nicht gefunden: {otp_result.get('error')}")
            return

        # STEP 4: Confirm Fireworks Account
        print("\n=== STEP 4: Fireworks Confirmation ===")
        confirm_result = await fw_svc.confirm(confirm_url=confirm_url, email=gmx_alias, password=password, cdp_port=cdp_port)
        print(f"Confirm result: {confirm_result}")
        if confirm_result["status"] == "success" and confirm_result.get("account_confirmed"):
            steps_completed.append("fireworks_confirmed")
            print("✅ Fireworks Account bestätigt")
        else:
            steps_failed.append("fireworks_confirmation_failed")
            print(f"❌ Bestätigung fehlgeschlagen: {confirm_result.get('error')}")
            return

        # STEP 5: API Key Creation
        print("\n=== STEP 5: API Key Creation ===")
        key_result = await fw_svc.create_api_key(key_name="sinator-test-key", cdp_port=cdp_port, email=gmx_alias, password=password)
        print(f"API Key result: {key_result}")
        if key_result["status"] == "success" and key_result.get("api_key"):
            steps_completed.append("api_key_created")
            print(f"✅ API-Key: {key_result['api_key'][:15]}...")
        else:
            steps_failed.append("api_key_creation_failed")
            print(f"❌ API-Key Erstellung fehlgeschlagen: {key_result.get('error')}")
            return

        elapsed = time.time() - t0
        print(f"\n🎉 FULL ROTATION SUCCESS in {elapsed:.1f}s")
        print(f"Completed steps: {steps_completed}")

    except Exception as e:
        elapsed = time.time() - t0
        print(f"\n❌ Rotation failed with exception: {e}")
        print(f"Completed steps before failure: {steps_completed}")

if __name__ == "__main__":
    asyncio.run(test_rotation())
